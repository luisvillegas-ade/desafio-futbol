"""Módulo de reclamos (CCC): verificación, levantamiento firmado y reemplazo.

El objeto /reclamos del API NO trae orden_id: hay que ubicar la orden activa
del proveedor indicado que afecta el dominio reclamado:
- tipo dominio: objetivo == dominio
- tipo ip:      dominio figura en dns_pasivo[objetivo]

Tras levantar, si la afectación vino de un bloqueo por IP se reemplaza por un
bloqueo por dominio del host pirata del mismo expediente.
"""
import json

from .. import db
from .dispatcher import firmar


class GestorReclamos:
    def __init__(self, cliente, reloj, turnos, dispatcher):
        self.cliente = cliente
        self.reloj = reloj
        self.turnos = turnos
        self.dispatcher = dispatcher
        self._dns_cache = {}

    def _dominios_en_ip(self, ip: str):
        if ip not in self._dns_cache:
            st, resp = self.cliente.get(f"/dns-pasivo?ip={ip}")
            self._dns_cache[ip] = resp.get("dominios", []) if st == 200 else []
        return self._dns_cache[ip]

    def procesar(self, r: dict) -> None:
        dominio, pid = r["dominio"], r["proveedor"]
        db.ejecutar(
            "INSERT OR IGNORE INTO reclamos(id,dominio,proveedor,mensaje,minuto,estado)"
            " VALUES(?,?,?,?,?,'recibido')",
            (r["id"], dominio, pid, r.get("mensaje", ""), r["minuto"]))

        st, ordenes = self.cliente.get(f"/proveedores/{pid}/ordenes")
        if st != 200:
            return
        afectantes = [o for o in ordenes if o["estado"] == "aplicada"
                      and self._afecta(o, dominio)]
        for orden in afectantes:
            self._levantar(r, orden)

    def _afecta(self, orden: dict, dominio: str) -> bool:
        if orden["tipo"] == "dominio":
            return orden["objetivo"] == dominio
        return dominio in self._dominios_en_ip(orden["objetivo"])

    def _levantar(self, r: dict, orden: dict) -> None:
        _, jz, juez = self.turnos.esperar_firma_segura()
        pid, oid = r["proveedor"], orden["orden_id"]
        firma = firmar(juez["clave_firma_demo"], f"LEVANTAR|{oid}|{juez['id']}")
        st, resp = self.cliente.post(
            f"/proveedores/{pid}/ordenes/{oid}/levantar",
            {"juez_id": juez["id"], "firma": firma,
             "motivo": f"Reclamo {r['id']} de {r['dominio']}: "
                      f"orden {oid} afecta un sitio legítimo."})
        ahora = self.reloj.ahora()
        if st != 200:
            db.actuacion(orden.get("expediente_id"), "reclamo",
                         f"Reclamo {r['id']}: levantamiento de {oid} rechazado "
                         f"({st}): {resp.get('error')}", ahora)
            return
        exp_id = orden.get("expediente_id")
        db.ejecutar("UPDATE ordenes SET estado='levantada' WHERE orden_id=? "
                    "AND proveedor_id=?", (oid, pid))
        db.ejecutar("UPDATE reclamos SET estado='orden_levantada', orden_id=?, "
                    "resolucion_min=? WHERE id=?", (oid, ahora, r["id"]))
        db.actuacion(exp_id, "levantamiento",
                     f"Reclamo {r['id']} ({r['dominio']}): orden {oid} levantada "
                     f"en {pid} por {juez['id']}", ahora)
        # Reemplazo por bloqueo más preciso si la afectación vino de una IP.
        if orden["tipo"] == "ip" and exp_id:
            exp = db.q1("SELECT * FROM expedientes WHERE id=?", (exp_id,))
            if exp:
                db.actuacion(exp_id, "despacho",
                             f"Reemplazo por bloqueo de dominio "
                             f"{exp['host_stream']} en {pid} tras reclamo {r['id']}",
                             ahora)
                self.dispatcher.despachar_puntual(
                    exp_id, pid, "dominio", exp["host_stream"])
