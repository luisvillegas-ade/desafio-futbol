"""Despacho de órdenes: paralelo por proveedor, firma HMAC y reintentos.

Cada expediente aprobado dispara un worker por proveedor. El worker firma con
el juez de turno SEGURO (buffer pre-cambio), envía, y espera el resultado.

Confirmación CONSOLIDADA: un único loop (`_monitor`) consulta la lista completa
de órdenes de cada proveedor (~4 req por ciclo). Esto es deliberado: el
simulador serializa cada request con un lock global (`avanzar`), y hacer polling
individual por orden saturaba el servidor y demoraba todo el pipeline ~10x.

`fallida` reintenta con orden_id nuevo firmado por el juez de turno EN ESE
MOMENTO (clave para no quedar fuera de turno tras el minuto 50).

Casos borde:
- vence_min entero y posterior al actual: se corta el ciclo en ahora >= fin_min.
- orden_id único por proveedor: ord-<exp_num>-<pid>-r<intento>.
- FibraValle solo acepta dominio: traducción por capacidades.
"""
import hashlib
import hmac
import threading
import time

from .. import config, db

TERMINALES = ("aplicada", "fallida", "vencida", "levantada")


def firmar(clave: str, mensaje: str) -> str:
    return hmac.new(clave.encode(), mensaje.encode(), hashlib.sha256).hexdigest()


class Dispatcher:
    def __init__(self, cliente, reloj, turnos):
        self.cliente = cliente
        self.reloj = reloj
        self.turnos = turnos
        st, provs = cliente.get("/proveedores")
        self.proveedores = {p["id"]: p for p in provs} if st == 200 else {}
        self._despachados = set()
        self._lock = threading.Lock()
        # seguimiento consolidado de órdenes
        self._espera = {}       # (pid, orden_id) -> Event
        self._resultado = {}    # (pid, orden_id) -> dict orden terminal
        self._estados = {}      # (pid, orden_id) -> último estado visto
        self._seguimiento = threading.Lock()
        threading.Thread(target=self._monitor, daemon=True,
                         name="Thread-MonitorOrdenes").start()

    # -- despacho -----------------------------------------------------------

    def despachar_expediente(self, exp: dict) -> None:
        """Dispara un worker por proveedor para la tupla del expediente."""
        with self._lock:
            if exp["id"] in self._despachados:
                return
            self._despachados.add(exp["id"])
        for pid, p in self.proveedores.items():
            tipo = exp["tipo_bloqueo_recomendado"]
            objetivo = exp["ip_servidor"] if tipo == "ip" else exp["host_stream"]
            if tipo not in p["capacidades"]:
                tipo, objetivo = "dominio", exp["host_stream"]
            threading.Thread(
                target=self._ciclo_proveedor,
                args=(exp["id"], pid, tipo, objetivo), daemon=True).start()

    def despachar_puntual(self, exp_id: str, pid: str, tipo: str,
                          objetivo: str) -> None:
        """Orden única a un proveedor (p.ej. reemplazo por dominio tras reclamo)."""
        threading.Thread(
            target=self._ciclo_proveedor,
            args=(exp_id, pid, tipo, objetivo), daemon=True).start()

    def _ciclo_proveedor(self, exp_id: str, pid: str, tipo: str,
                         objetivo: str, intento: int = 0) -> None:
        vence = int(self.reloj.fin_min)
        while intento < config.INTENTOS_MAX:
            if self.reloj.ahora() >= vence:
                return
            _, jz, juez = self.turnos.esperar_firma_segura()
            if self.reloj.ahora() >= vence:
                return
            orden_id = f"ord-{exp_id.split('-')[-1]}-{pid}-r{intento}"
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
            db.ejecutar(
                "INSERT OR IGNORE INTO ordenes(orden_id,expediente_id,proveedor_id,"
                "tipo,objetivo,vence_min,juzgado_id,juez_id,firma,estado,intento,"
                "minuto_envio) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                (orden_id, exp_id, pid, tipo, objetivo, vence, jz["id"],
                 juez["id"], orden["firma"], "recibida", intento, minuto))
            db.actuacion(
                exp_id, "firma_orden" if intento == 0 else "despacho",
                f"Orden {orden_id} ({tipo} -> {objetivo}, vence {vence}) firmada "
                f"por {juez['id']} y despachada a {pid}", minuto)

            resultado = self._esperar(exp_id, key, ev)
            if resultado == "fallida":
                intento += 1
                continue
            return

    def _esperar(self, exp_id: str, key, ev: threading.Event) -> str:
        """Espera a que el monitor vea la orden en estado terminal."""
        pid, orden_id = key
        # timeout generoso: si el monitor se atrasa, consultamos directo
        if not ev.wait(timeout=30):
            st, o = self.cliente.get(f"/proveedores/{pid}/ordenes/{orden_id}")
            estado = o.get("estado", "fallida") if st == 200 else "fallida"
        else:
            with self._seguimiento:
                o = self._resultado.pop(key, {})
            estado = o.get("estado", "fallida")
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
