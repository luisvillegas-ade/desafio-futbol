"""Despacho de órdenes: paralelo por proveedor, firma HMAC y reintentos.

Cada expediente aprobado dispara un worker por proveedor.

Regla de firma (modo interactivo): solo firma el juez que APROBÓ la medida en
la consola, y solo mientras siga de turno con margen seguro (la firma se
evalúa cuando el proveedor RECIBE la orden). Si ese juez salió de turno —o
entró al buffer previo al cambio— el expediente se re-eleva al juez entrante
y el worker espera una nueva aprobación: nadie firma en nombre de otro.
En modo auto (sólo pruebas) firma el juez de turno seguro, como orden marco.

Confirmación CONSOLIDADA: un único loop (`_monitor`) consulta la lista completa
de órdenes de cada proveedor (~4 req por ciclo). Esto es deliberado: el
simulador serializa cada request con un lock global (`avanzar`), y hacer polling
individual por orden saturaba el servidor y demoraba todo el pipeline ~10x.

Casos borde:
- vence_min entero y posterior al actual: se corta el ciclo en ahora >= fin_min.
- orden_id único por proveedor: ord-<exp_num>-<pid>-r<intento>; los reemplazos
  tras reclamo agregan -rep<n> para no chocar con la orden levantada.
- FibraValle solo acepta dominio: traducción por capacidades.
"""
import hashlib
import hmac
import threading
import time

from .. import config, db
from . import expediente as ex

TERMINALES = ("aplicada", "fallida", "vencida", "levantada")


def firmar(clave: str, mensaje: str) -> str:
    return hmac.new(clave.encode(), mensaje.encode(), hashlib.sha256).hexdigest()


class Dispatcher:
    def __init__(self, cliente, reloj, turnos, modo_auto=True):
        self.cliente = cliente
        self.reloj = reloj
        self.turnos = turnos
        self.modo_auto = modo_auto
        self.proveedores = {}
        self._refrescar_proveedores()
        self._ultimo_despacho = {}  # exp_id -> (tipo, objetivo) ya despachado
        self._aprob_evt = {}        # exp_id -> Event (nueva aprobación judicial)
        self._lock = threading.Lock()
        # seguimiento consolidado de órdenes
        self._espera = {}       # (pid, orden_id) -> Event
        self._resultado = {}    # (pid, orden_id) -> dict orden terminal
        self._estados = {}      # (pid, orden_id) -> último estado visto
        self._seguimiento = threading.Lock()
        threading.Thread(target=self._monitor, daemon=True,
                         name="Thread-MonitorOrdenes").start()

    def _refrescar_proveedores(self) -> None:
        """Carga /proveedores reintentando hasta ~30 s: el sim puede todavía
        no estar escuchando cuando arranca la plataforma."""
        espera = 0.5
        while espera <= 32:
            st, provs = self.cliente.get("/proveedores")
            if st == 200 and provs:
                self.proveedores = {p["id"]: p for p in provs}
                return
            time.sleep(espera)
            espera *= 2
        print("[dispatcher] sin /proveedores: no se puede despachar",
              flush=True)

    # -- despacho -----------------------------------------------------------

    def _evento(self, exp_id: str) -> threading.Event:
        with self._seguimiento:
            return self._aprob_evt.setdefault(exp_id, threading.Event())

    def notificar_aprobacion(self, exp_id: str) -> None:
        """Despierta a los workers que esperan una nueva firma judicial."""
        self._evento(exp_id).set()

    def despachar_expediente(self, exp: dict) -> None:
        """Dispara un worker por proveedor para la tupla del expediente."""
        if not self.proveedores:
            self._refrescar_proveedores()
        tipo = exp["tipo_bloqueo_recomendado"] or "dominio"
        objetivo = exp["ip_servidor"] if tipo == "ip" else exp["host_stream"]
        medida = (tipo, objetivo)
        with self._lock:
            if self._ultimo_despacho.get(exp["id"]) == medida:
                return          # misma medida ya en curso (re-aprobación)
            self._ultimo_despacho[exp["id"]] = medida
        for pid, p in self.proveedores.items():
            t_pid, obj_pid = tipo, objetivo
            if t_pid not in p["capacidades"]:
                t_pid, obj_pid = "dominio", exp["host_stream"]
            threading.Thread(
                target=self._ciclo_proveedor,
                args=(exp["id"], pid, t_pid, obj_pid), daemon=True).start()

    def despachar_puntual(self, exp_id: str, pid: str, tipo: str,
                          objetivo: str, firmante: str = None) -> None:
        """Orden única a un proveedor (reemplazo por dominio tras reclamo).

        `firmante` = juez que aprobó el acto (modo interactivo). El orden_id
        lleva -rep<n> para no colisionar con la orden recién levantada.
        """
        n = db.q1("SELECT COUNT(*) c FROM ordenes WHERE expediente_id=? "
                  "AND proveedor_id=?", (exp_id, pid))["c"]
        serie = f"-rep{n}" if n else ""
        threading.Thread(
            target=self._ciclo_proveedor,
            args=(exp_id, pid, tipo, objetivo),
            kwargs={"serie": serie, "firmante": firmante}, daemon=True).start()

    def _contexto_firma(self, exp_id: str, firmante):
        """Devuelve (juzgado, juez) habilitado para firmar ahora, o None.

        Interactivo: solo el juez que aprobó la medida, y solo si sigue de
        turno con margen seguro. Si no puede firmar, el expediente se
        re-eleva al juez que sí podría (el entrante dentro del buffer) y se
        espera una nueva aprobación judicial.
        """
        if self.modo_auto:
            _, jz, juez = self.turnos.esperar_firma_segura()
            if jz is None:
                db.actuacion(
                    exp_id, "despacho",
                    f"Sin juez de turno a min {self.reloj.ahora():.1f}: "
                    f"orden no librada", self.reloj.ahora())
                return None
            return jz, juez
        ev = self._evento(exp_id)
        while True:
            ahora = self.reloj.ahora()
            if ahora >= self.reloj.fin_min or self.reloj.finalizado:
                return None
            exp = db.q1("SELECT estado, juez_asignado, aprobada_por "
                        "FROM expedientes WHERE id=?", (exp_id,))
            if exp is None or exp["estado"] in ("archivado", "cerrado"):
                return None
            jid = firmante or exp["aprobada_por"]
            _, jz, j = self.turnos.juez_seguro(ahora)
            if jid and j and j["id"] == jid:
                return jz, j
            if j is None:
                db.actuacion(exp_id, "despacho",
                             "Sin juez disponible para firmar: orden no "
                             "librada", ahora)
                return None
            # el firmante no puede firmar ahora: re-elevar al juez que sí
            with db.bloqueo():
                exp2 = db.q1("SELECT estado, juez_asignado FROM expedientes "
                             "WHERE id=?", (exp_id,))
                if exp2 and (exp2["estado"] != "elevado"
                             or exp2["juez_asignado"] != j["id"]):
                    ex.set_estado(exp_id, "elevado")
                    db.ejecutar(
                        "UPDATE expedientes SET juez_asignado=?, "
                        "aprobada_por=NULL, aprobada_min=NULL WHERE id=?",
                        (j["id"], exp_id))
                    db.actuacion(
                        exp_id, "pase",
                        f"La aprobación vigente no podía ejecutarse dentro "
                        f"del turno: expediente transferido a {j['id']} "
                        f"para nueva firma", ahora)
            firmante = None
            ev.clear()
            ev.wait(1.0)

    def _ciclo_proveedor(self, exp_id: str, pid: str, tipo: str,
                         objetivo: str, intento: int = 0, serie: str = "",
                         firmante: str = None) -> None:
        vence = int(self.reloj.fin_min)
        base = f"ord-{exp_id.split('-')[-1]}-{pid}{serie}"
        while intento < config.INTENTOS_MAX:
            if self.reloj.ahora() >= vence:
                return
            ctx = self._contexto_firma(exp_id, firmante)
            if ctx is None:
                return
            jz, juez = ctx
            firmante = juez["id"]
            if self.reloj.ahora() >= vence:
                return
            orden_id = f"{base}-r{intento}"
            orden = {"orden_id": orden_id, "expediente_id": exp_id, "tipo": tipo,
                     "objetivo": objetivo, "vence_min": vence,
                     "juzgado_id": jz["id"], "juez_id": juez["id"]}
            msg = f"{orden_id}|{tipo}|{objetivo}|{vence}|{juez['id']}"
            orden["firma"] = firmar(juez["clave_firma_demo"], msg)

            key = (pid, orden_id)
            ev = threading.Event()
            with self._seguimiento:
                self._espera[key] = ev

            st, resp = self.cliente.post(f"/proveedores/{pid}/ordenes", orden)
            minuto = self.reloj.ahora()
            if st != 202:
                with self._seguimiento:
                    self._espera.pop(key, None)
                db.actuacion(exp_id, "despacho",
                             f"Orden {orden_id} rechazada por {pid} "
                             f"({st}): {resp.get('error')}", minuto)
                if st == 422 and "vence" in str(resp.get("error")):
                    return
                intento += 1
                continue
            hu = db.huella_orden(
                {"orden_id": orden_id, "expediente_id": exp_id,
                 "proveedor_id": pid, "tipo": tipo, "objetivo": objetivo,
                 "vence_min": vence, "juzgado_id": jz["id"],
                 "juez_id": juez["id"], "firma": orden["firma"]})
            db.ejecutar(
                "INSERT OR IGNORE INTO ordenes(orden_id,expediente_id,proveedor_id,"
                "tipo,objetivo,vence_min,juzgado_id,juez_id,firma,estado,intento,"
                "minuto_envio,huella) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (orden_id, exp_id, pid, tipo, objetivo, vence, jz["id"],
                 juez["id"], orden["firma"], "recibida", intento, minuto, hu))
            db.actuacion(
                exp_id, "firma_orden" if intento == 0 else "despacho",
                f"Orden {orden_id} ({tipo} -> {objetivo}, vence {vence}) firmada "
                f"por {juez['id']} y despachada a {pid} — huella {hu[:24]}",
                minuto)

            resultado = self._esperar(exp_id, key, ev)
            if resultado == "fallida":
                intento += 1
                continue
            return

    def _esperar(self, exp_id: str, key, ev: threading.Event) -> str:
        """Espera a que el monitor vea la orden en estado terminal.

        Sin timeout real fijo: la demora del proveedor corre en minutos de
        partido (FibraValle tarda hasta ~8 min, 480 s a x1) así que se sale
        solo por estado terminal, por cierre de la ventana del sim
        (fin_min + gracia) o si el expediente fue archivado. El monitor
        consolidado despierta el Event; como respaldo se consulta directo
        cada ~15 s reales por si el monitor se atrasó.
        """
        pid, orden_id = key
        corte = self.reloj.fin_min + 5.0     # misma gracia que el simulador
        o = {}
        estado = "recibida"
        ultimo_directo = 0.0
        while True:
            if ev.wait(timeout=1.0):
                with self._seguimiento:
                    o = self._resultado.pop(key, {})
                estado = o.get("estado", "fallida")
                break
            if self.reloj.ahora() >= corte:
                estado = "vencida"
                break
            exp = db.q1("SELECT estado FROM expedientes WHERE id=?", (exp_id,))
            if exp is None or exp["estado"] in ("archivado", "cerrado"):
                return "abortada"
            if time.monotonic() - ultimo_directo > 15:
                ultimo_directo = time.monotonic()
                try:
                    st, o2 = self.cliente.get(
                        f"/proveedores/{pid}/ordenes/{orden_id}")
                    if st == 200 and o2.get("estado") in TERMINALES:
                        o, estado = o2, o2["estado"]
                        break
                except Exception:
                    pass
        with self._seguimiento:
            self._espera.pop(key, None)
        if estado == "aplicada":
            db.actuacion(exp_id, "confirmacion",
                         f"{pid} aplicó {orden_id} en el minuto "
                         f"{o.get('aplicada_min')}", self.reloj.ahora())
        elif estado == "fallida":
            db.actuacion(exp_id, "despacho",
                         f"{pid} reportó falla en {orden_id} "
                         f"({o.get('motivo', 'error interno')}). Reenviando.",
                         self.reloj.ahora())
        elif estado in ("vencida", "levantada"):
            db.actuacion(exp_id, "vencimiento" if estado == "vencida"
                         else "levantamiento",
                         f"{orden_id} en {pid} quedó '{estado}' "
                         f"(min {self.reloj.ahora():.1f})",
                         self.reloj.ahora())
        return estado

    # -- monitor consolidado -------------------------------------------------

    def _monitor(self) -> None:
        while True:
            try:
                self._monitor_ciclo()
            except Exception as e:
                print(f"[monitor] error: {e}", flush=True)
            time.sleep(config.MONITOR_SEGUNDOS)

    def _monitor_ciclo(self) -> None:
        for pid in self.proveedores:
            st, ordenes = self.cliente.get(f"/proveedores/{pid}/ordenes")
            if st != 200:
                continue
            for o in ordenes:
                key = (pid, o["orden_id"])
                estado = o["estado"]
                with self._seguimiento:
                    previo = self._estados.get(key)
                    esperando = key in self._espera or previo is not None
                if not esperando:
                    continue
                if estado != previo:
                    db.ejecutar(
                        "UPDATE ordenes SET estado=?, minuto_aplicada=? "
                        "WHERE orden_id=? AND proveedor_id=?",
                        (estado, o.get("aplicada_min"), o["orden_id"], pid))
                    with self._seguimiento:
                        self._estados[key] = estado
                if estado in TERMINALES:
                    with self._seguimiento:
                        ev = self._espera.get(key)
                        if ev is not None:
                            self._resultado[key] = o
                            ev.set()
