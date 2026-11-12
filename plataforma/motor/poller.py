"""Loop de polling + pool de trabajadores.

El poller SOLO hace fetch HTTP (cada POLL_SEGUNDOS) y encola detecciones: con
aceleración alta el simulador publica más rápido de lo que un thread serial
puede procesar, así que el procesamiento (DNS, evidencias, despacho) corre en
TRABAJADORES threads paralelos.

Cursores:
- detecciones: `minuto_actual` de la respuesta como próximo `desde` (contrato API).
- reclamos: NO usar `minuto_actual` (viene redondeado a 2 decimales y puede
  saltar reclamos). Cursor = max(minuto) de reclamos ya vistos + dedup por id.

El get-or-create de expedientes y el disparo del despacho van bajo un lock por
tupla (host,ip) para que dos detecciones del mismo stream en paralelo no
dupliquen expediente ni ordenes.
"""
import queue
import threading
import time

from .. import config, db
from . import expediente as ex

TRABAJADORES = 4


class Poller(threading.Thread):
    def __init__(self, cliente, reloj, turnos, verificador, dispatcher,
                 gestor_reclamos, modo_auto: bool):
        super().__init__(daemon=True, name="Thread-Poller")
        self.cliente = cliente
        self.reloj = reloj
        self.turnos = turnos
        self.verificador = verificador
        self.dispatcher = dispatcher
        self.reclamos = gestor_reclamos
        self.modo_auto = modo_auto
        self.detener = threading.Event()
        self.cola = queue.Queue()
        self.cola_reclamos = queue.Queue()
        self._locks = {}          # tupla (host,ip) -> Lock
        self._locks_guard = threading.Lock()

        for i in range(TRABAJADORES):
            threading.Thread(target=self._trabajador, daemon=True,
                             name=f"Thread-Trabajo-{i}").start()
        threading.Thread(target=self._trabajador_reclamos, daemon=True,
                         name="Thread-Reclamos").start()

    def _lock_tupla(self, host: str, ip: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault((host, ip), threading.Lock())

    def run(self) -> None:
        cursor_det = db.cursor_get("detecciones", -1.0)
        cursor_rec = db.cursor_get("reclamos", -1.0)
        vistos = set()
        while not self.detener.is_set():
            try:
                cursor_det, cursor_rec = self._ciclo(
                    cursor_det, cursor_rec, vistos)
            except Exception as e:
                print(f"[poller] error: {e}", flush=True)
            time.sleep(config.POLL_SEGUNDOS)

    def _ciclo(self, cursor_det, cursor_rec, vistos):
        st, estado = self.cliente.get("/estado")
        if st == 200:
            self.reloj.actualizar(estado)

        st, det = self.cliente.get(f"/detecciones?desde={cursor_det}")
        if st == 200:
            for d in det["detecciones"]:
                self.cola.put(d)
            cursor_det = det["minuto_actual"]
            db.cursor_set("detecciones", cursor_det)

        st, rec = self.cliente.get(f"/reclamos?desde={cursor_rec}")
        if st == 200:
            for r in rec["reclamos"]:
                if r["id"] in vistos:
                    continue
                vistos.add(r["id"])
                # nunca procesar acá: un levantamiento puede esperar firma y
                # congelaría el polling de detecciones
                self.cola_reclamos.put(r)
                cursor_rec = max(cursor_rec, r["minuto"])
            db.cursor_set("reclamos", cursor_rec)
        return cursor_det, cursor_rec

    def _trabajador_reclamos(self) -> None:
        while True:
            r = self.cola_reclamos.get()
            try:
                self.reclamos.procesar(r)
            except Exception as e:
                print(f"[reclamos] error con {r.get('id')}: {e}", flush=True)

    def _trabajador(self) -> None:
        while True:
            det = self.cola.get()
            try:
                self._procesar_deteccion(det)
            except Exception as e:
                print(f"[trabajador] error con {det.get('id')}: {e}", flush=True)

    def _procesar_deteccion(self, det: dict) -> None:
        res = self.verificador.clasificar(det)
        marca = det.get("marca_de_agua_extraida") or "<sin marca>"
        if res != "pirata":
            db.actuacion(
                None, "deteccion_descartada",
                f"{det['id']} {det['host_stream']} ({det['ip_servidor']}): "
                f"{res} — marca {marca}", det["minuto"])
            return

        lock = self._lock_tupla(det["host_stream"], det["ip_servidor"])
        with lock:
            tipo, objetivo, dominios, ajenos = \
                self.verificador.analizar_colateral(det)
            _, _, juez = self.turnos.de_turno(self.reloj.ahora())
            exp, nuevo = ex.obtener_o_crear(
                det, tipo, juez["id"] if juez else None)
            ex.agregar_evidencia(exp["id"], det, dominios, bool(ajenos), True)
            db.actuacion(
                exp["id"], "deteccion",
                f"{det['id']} — señal oficial pirata en {det['host_stream']} "
                f"({det['ip_servidor']}, ASN {det.get('asn')}), marca {marca}",
                det["minuto"])
            if nuevo:
                riesgo = (f"Riesgo colateral: {len(ajenos)} dominio(s) "
                          "ajeno(s) en la IP"
                          if ajenos else "Riesgo colateral nulo (IP dedicada)")
                db.actuacion(
                    exp["id"], "peritaje",
                    f"{riesgo}. Medida sugerida: bloqueo por {tipo} -> "
                    f"{objetivo} hasta min {int(self.reloj.fin_min)}",
                    det["minuto"])
                ex.set_estado(exp["id"], "elevado")

            if self.modo_auto and not ex.tiene_ordenes_activas(exp["id"]):
                ex.set_estado(exp["id"], "en_ejecucion")
                self.dispatcher.despachar_expediente(exp)
