"""Puente web desplegada -> motor local (solo con DATABASE_URL Postgres).

La web en Vercel no alcanza el simulador (está en la LAN del evento): solo
registra decisiones en `decisiones_web`. Este módulo, llamado desde
Thread-Reclamos, publica el reloj del partido para la web y ejecuta cada
decisión con las mismas funciones que usa la consola local.
"""
import json
import time

from .. import db
from . import expediente as ex


def publicar_reloj(reloj) -> None:
    db.cursor_set("reloj_min", reloj.ahora())
    db.cursor_set("reloj_wall", time.time())
    db.cursor_set("reloj_acel", reloj._acel)
    db.cursor_set("reloj_fin", reloj.fin_min)
    db.cursor_set("reloj_finalizado", 1.0 if reloj.finalizado else 0.0)


def procesar(dispatcher, gestor) -> None:
    for d in db.q("SELECT * FROM decisiones_web WHERE estado='pendiente' "
                  "ORDER BY id"):
        if db.ejecutar("UPDATE decisiones_web SET estado='procesada' "
                       "WHERE id=? AND estado='pendiente'", (d["id"],)) != 1:
            continue                     # la tomó otro motor
        try:
            _ejecutar(d, dispatcher, gestor)
        except Exception as e:
            db.ejecutar("UPDATE decisiones_web SET estado='error', datos=? "
                        "WHERE id=?", (str(e), d["id"]))
            print(f"[web] error con decisión {d['id']}: {e}", flush=True)


def _ejecutar(d, dispatcher, gestor) -> None:
    if d["tipo"] == "aprobar":
        exp = db.q1("SELECT * FROM expedientes WHERE id=?", (d["objetivo"],))
        if exp and exp["estado"] == "aprobado":
            ex.set_estado(exp["id"], "en_ejecucion")
            dispatcher.notificar_aprobacion(exp["id"])
            dispatcher.despachar_expediente(dict(exp))
    elif d["tipo"] == "hacer_lugar":
        if db.ejecutar("UPDATE reclamos SET estado='elevado' WHERE id=? "
                       "AND estado='aceptado_web'", (d["objetivo"],)) == 1:
            gestor.resolver(d["objetivo"], d["juez_id"])
    elif d["tipo"] == "reclamo_ciudadano":
        gestor.procesar_ciudadano(d["objetivo"],
                                  json.loads(d["datos"] or "{}")
                                  .get("mensaje", ""))
