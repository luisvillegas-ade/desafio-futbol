"""Módulo de reclamos (CCC): verificación, levantamiento firmado y reemplazo.

El objeto /reclamos del API NO trae orden_id: hay que ubicar la orden activa
del proveedor indicado que afecta el dominio reclamado:
- tipo dominio: objetivo == dominio
- tipo ip:      dominio figura en dns_pasivo[objetivo]

Modo interactivo: el reclamo queda 'elevado' en la bandeja del juez de turno;
solo cuando ese juez hace lugar (un clic) se firma el levantamiento CON SU
CLAVE y se despacha el reemplazo por dominio firmado por el mismo juez.
Nadie firma sin login + aprobación, como manda el reglamento.

Modo auto (solo pruebas): levanta directo con el juez de turno seguro.

Tras levantar, si la afectación vino de un bloqueo por IP se reemplaza por un
bloqueo por dominio del host pirata del mismo expediente.
"""
from .. import db
from .dispatcher import firmar

ESTADOS_ACTIVOS = ("recibida", "aplicada")


class GestorReclamos:
    def __init__(self, cliente, reloj, turnos, dispatcher, modo_auto=True):
        self.cliente = cliente
        self.reloj = reloj
        self.turnos = turnos
        self.dispatcher = dispatcher
        self.modo_auto = modo_auto
        self._dns_cache = {}

    def _dominios_en_ip(self, ip: str):
        if ip not in self._dns_cache:
            st, resp = self.cliente.get(f"/dns-pasivo?ip={ip}")
            self._dns_cache[ip] = resp.get("dominios", []) if st == 200 else []
        return self._dns_cache[ip]

    # -- ingreso de reclamos -------------------------------------------------

    def procesar_ciudadano(self, dominio: str, mensaje: str) -> int:
        """Reclamo por vía pública: no sabemos qué ISP bloquea el dominio,
        así que se relevan las 4 listas y se dispone cada orden que lo afecte.

        Devuelve cuántas órdenes se elevaron/levantaron (0 = desestimado)."""
        ahora = self.reloj.ahora()
        n = 0
        for pid in ("aurora", "andina", "cumbre", "valle"):
            st, ordenes = self.cliente.get(f"/proveedores/{pid}/ordenes")
            if st != 200:
                continue
            afectantes = [o for o in ordenes if o["estado"] in ESTADOS_ACTIVOS
                          and self._afecta(o, dominio)]
            for orden in afectantes:
                n += 1
                rid = f"WEB-{ahora:.3f}-{pid}-{n}"
                r = {"id": rid, "dominio": dominio, "proveedor": pid,
                     "mensaje": mensaje, "minuto": ahora}
                db.ejecutar(
                    "INSERT OR IGNORE INTO reclamos(id,dominio,proveedor,"
                    "mensaje,minuto,estado) VALUES(?,?,?,?,?,'recibido')",
                    (rid, dominio, pid, mensaje, ahora))
                self._disponer(r, orden)
        if not n:
            rid = f"WEB-{ahora:.3f}-des"
            db.ejecutar(
                "INSERT OR IGNORE INTO reclamos(id,dominio,proveedor,"
                "mensaje,minuto,estado) VALUES(?,?,?,?,?,'desestimado')",
                (rid, dominio, "—", f"{mensaje} (sin medida vigente que lo "
                    "afecte)", ahora))
            db.actuacion(None, "reclamo",
                         f"Reclamo público {rid} por {dominio}: desestimado, "
                         f"ninguna medida vigente lo afecta", ahora)
        return n

    def procesar(self, r: dict) -> None:
        dominio, pid = r["dominio"], r["proveedor"]
        db.ejecutar(
            "INSERT OR IGNORE INTO reclamos(id,dominio,proveedor,mensaje,minuto,estado)"
            " VALUES(?,?,?,?,?,'recibido')",
            (r["id"], dominio, pid, r.get("mensaje", ""), r["minuto"]))

        st, ordenes = self.cliente.get(f"/proveedores/{pid}/ordenes")
        if st != 200:
            return
        afectantes = [o for o in ordenes if o["estado"] in ESTADOS_ACTIVOS
                      and self._afecta(o, dominio)]
        if not afectantes:
            db.ejecutar("UPDATE reclamos SET estado='desestimado' WHERE id=?",
                        (r["id"],))
            return
        for orden in afectantes:
            self._disponer(r, orden)

    def _afecta(self, orden: dict, dominio: str) -> bool:
        if orden["tipo"] == "dominio":
            return orden["objetivo"] == dominio
        return dominio in self._dominios_en_ip(orden["objetivo"])

    def _disponer(self, r: dict, orden: dict) -> None:
        """Auto: levanta ya con el juez de turno seguro. Interactivo: eleva
        a la bandeja del juez de turno (firma tras su clic)."""
        if not self.modo_auto:
            db.ejecutar("UPDATE reclamos SET estado='elevado' WHERE id=?",
                        (r["id"],))
            motivo = r.get("mensaje") or "sitio legítimo afectado"
            db.actuacion(
                orden.get("expediente_id"), "reclamo",
                f"Reclamo {r['id']} ({r['dominio']}): {motivo} — la orden "
                f"{orden['orden_id']} en {r['proveedor']} lo afecta. Elevado "
                f"al juez de turno para levantamiento y reemplazo por dominio.",
                self.reloj.ahora())
            return
        _, jz, juez = self.turnos.esperar_firma_segura()
        if jz is None:
            db.actuacion(
                orden.get("expediente_id"), "reclamo",
                f"Reclamo {r['id']}: no hay juez de turno para firmar el "
                f"levantamiento de {orden['orden_id']}", self.reloj.ahora())
            return
        self._levantar(r, orden, juez)

    # -- resolución judicial --------------------------------------------------

    def resolver(self, rid: str, juez_id: str) -> bool:
        """El juez de turno hace lugar al reclamo `rid` (un clic): firma el
        levantamiento con SU clave y ordena el reemplazo por dominio."""
        r = db.q1("SELECT * FROM reclamos WHERE id=?", (rid,))
        if not r or r["estado"] != "elevado":
            return False
        jz, juez = self.turnos.juez_por_id(juez_id)
        if juez is None:
            return False
        st, ordenes = self.cliente.get(
            f"/proveedores/{r['proveedor']}/ordenes")
        afectantes = [o for o in ordenes if o["estado"] in ESTADOS_ACTIVOS
                      and self._afecta(o, r["dominio"])] if st == 200 else []
        if not afectantes:
            db.ejecutar(
                "UPDATE reclamos SET estado='desestimado' WHERE id=?", (rid,))
            db.actuacion(None, "reclamo",
                         f"Reclamo {rid} desestimado por {juez_id}: ya no hay "
                         f"medida vigente que afecte {r['dominio']}",
                         self.reloj.ahora())
            return True
        for orden in afectantes:
            self._levantar(r, orden, juez)
        return True

    def _levantar(self, r: dict, orden: dict, juez: dict) -> None:
        pid, oid = r["proveedor"], orden["orden_id"]
        firma = firmar(juez["clave_firma_demo"], f"LEVANTAR|{oid}|{juez['id']}")
        st, resp = self.cliente.post(
            f"/proveedores/{pid}/ordenes/{oid}/levantar",
            {"juez_id": juez["id"], "firma": firma,
             "motivo": f"Reclamo {r['id']} de {r['dominio']}: "
                      f"orden {oid} afecta un sitio legítimo."})
        ahora = self.reloj.ahora()
        exp_id = orden.get("expediente_id")
        if st != 200:
            db.actuacion(exp_id, "reclamo",
                         f"Reclamo {r['id']}: levantamiento de {oid} rechazado "
                         f"({st}): {resp.get('error')}", ahora)
            return
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
                # la resolución judicial habilita firmar el reemplazo con el
                # mismo juez mientras siga de turno
                db.ejecutar(
                    "UPDATE expedientes SET aprobada_por=?, aprobada_min=? "
                    "WHERE id=?", (juez["id"], ahora, exp_id))
                db.actuacion(exp_id, "despacho",
                             f"Reemplazo por bloqueo de dominio "
                             f"{exp['host_stream']} en {pid} tras reclamo {r['id']}",
                             ahora)
                self.dispatcher.despachar_puntual(
                    exp_id, pid, "dominio", exp["host_stream"],
                    firmante=juez["id"])
