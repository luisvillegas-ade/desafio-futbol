"""Consola judicial desplegable (Vercel + Postgres): MODO_WEB / SOLO_WEB.

Reutiliza templates.py, db.py y motor/turnos.py. Requiere DATABASE_URL
postgres://... (la misma base que el motor local). Esta capa SOLO registra
decisiones: firma y despacho al simulador los hace siempre el motor local
(ver motor/decisiones_web.py), que además publica el reloj del partido.

Env: DATABASE_URL, SESION_SECRET (firma la cookie), CLAVE_ACCESO (reemplaza
la clave 'demo' de config.USUARIOS).
"""
import hashlib
import hmac
import json
import os
import secrets
import time
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from .. import config, db
from ..auditoria.verificar_cadena import verificar as verificar_cadena
from ..juez import monitor as M
from ..juez import templates as T
from ..motor import expediente as ex
from ..motor.turnos import Turnos

if not db.PG:
    raise RuntimeError("plataforma.api requiere DATABASE_URL=postgres://...")

SESION_SECRET = os.environ.get("SESION_SECRET") or secrets.token_hex(16)
CLAVE_ACCESO = os.environ.get("CLAVE_ACCESO", "")
DURACION_SESION = 12 * 3600


class RelojWeb:
    """Reloj del partido publicado por el motor local en `cursores`."""

    def _c(self, k, d=0.0):
        return db.cursor_get(k, d)

    def ahora(self) -> float:
        m, wall = self._c("reloj_min"), self._c("reloj_wall")
        if not wall or self.finalizado:
            return m
        return m + (time.time() - wall) * self._c("reloj_acel", 1.0) / 60.0

    @property
    def fin_min(self):
        return self._c("reloj_fin", 105.0)

    @property
    def finalizado(self):
        return bool(self._c("reloj_finalizado"))


reloj = RelojWeb()
turnos = Turnos(reloj)
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


# -- helpers -----------------------------------------------------------------

def _html(s, estado=200):
    return HTMLResponse(s, estado)


def _redirect(ruta):
    return RedirectResponse(ruta, 303)


def _firmar_sid(sid):
    return hmac.new(SESION_SECRET.encode(), sid.encode(),
                    hashlib.sha256).hexdigest()[:32]


def _sesion(req: Request):
    v = req.cookies.get("sid", "")
    sid, _, firma = v.partition(".")
    if not sid or not hmac.compare_digest(firma, _firmar_sid(sid)):
        return None
    r = db.q1("SELECT datos, expira FROM sesiones WHERE sid=?", (sid,))
    if not r or r["expira"] < time.time():
        return None
    return json.loads(r["datos"])


def _puede_firmar(sesion):
    if sesion.get("rol") != "juez":
        return False
    t, jz, j = turnos.de_turno(reloj.ahora())
    return bool(t and t["juez_id"] == sesion.get("juez_id"))


async def _form(req: Request):
    return {k: v[0] for k, v in parse_qs((await req.body()).decode()).items()}


def _decision(tipo, objetivo, juez_id=None, datos=None):
    db.ejecutar("INSERT INTO decisiones_web(tipo,objetivo,juez_id,datos,"
                "minuto) VALUES(?,?,?,?,?)",
                (tipo, objetivo, juez_id, json.dumps(datos or {}),
                 reloj.ahora()))


def _expediente_completo(exp_id):
    exp = db.q1("SELECT * FROM expedientes WHERE id=?", (exp_id,))
    if not exp:
        return None
    ev = db.q("SELECT * FROM evidencias WHERE expediente_id=?", (exp_id,))
    ac = db.q("SELECT * FROM actuaciones WHERE expediente_id=? ORDER BY n",
              (exp_id,))
    oc = db.q("SELECT * FROM ordenes WHERE expediente_id=?", (exp_id,))
    rec = db.q("SELECT r.* FROM reclamos r JOIN ordenes o "
               "ON o.orden_id=r.orden_id WHERE o.expediente_id=? "
               "ORDER BY r.minuto", (exp_id,))
    ok, _ = verificar_cadena(ac, ev, oc)
    return dict(exp), ev, ac, oc, rec, ok


# -- públicas ----------------------------------------------------------------

@app.get("/login")
def login_form():
    return _html(T.login())


@app.post("/login")
async def login(req: Request):
    f = await _form(req)
    u, p = f.get("usuario", ""), f.get("password", "")
    datos = config.USUARIOS.get(u)
    clave = CLAVE_ACCESO or (datos or {}).get("password")
    if not datos or not hmac.compare_digest(p, clave or ""):
        return _html(T.login("Usuario o contraseña incorrectos"), 403)
    juez = turnos.jueces.get(datos.get("juez_id")) \
        if datos.get("juez_id") else None
    sesion = {"juez_id": datos.get("juez_id"), "rol": datos["rol"],
              "nombre": juez[1]["nombre"] if juez
                        else datos.get("nombre", u)}
    sid = secrets.token_hex(16)
    db.ejecutar("INSERT INTO sesiones(sid,usuario,expira,datos) "
                "VALUES(?,?,?,?)", (sid, u, time.time() + DURACION_SESION,
                                    json.dumps(sesion)))
    r = _redirect("/")
    r.set_cookie("sid", f"{sid}.{_firmar_sid(sid)}", httponly=True,
                 secure=req.url.scheme == "https", samesite="lax",
                 max_age=DURACION_SESION)
    return r


@app.get("/salir")
def salir(req: Request):
    sid = req.cookies.get("sid", "").partition(".")[0]
    if sid:
        db.ejecutar("DELETE FROM sesiones WHERE sid=?", (sid,))
    r = _redirect("/login")
    r.delete_cookie("sid")
    return r


@app.get("/transparencia")
def transparencia():
    return _html(T.transparencia(db.q("SELECT * FROM ordenes ORDER BY id"),
                                 reloj.ahora()))


@app.get("/monitor")
def monitor():
    return _html(M.pagina())


@app.get("/monitor/datos")
def monitor_datos():
    return Response(M.datos_json(reloj, turnos, "interactivo", None),
                    media_type="application/json; charset=utf-8")


@app.get("/reclamar")
def reclamar_form():
    return _html(T.reclamar())


@app.post("/reclamar")
async def reclamar(req: Request):
    f = await _form(req)
    dominio, mensaje = f.get("dominio", "").strip(), f.get("mensaje", "").strip()
    if not dominio or "." not in dominio:
        return _html(T.reclamar(error="Ingrese un dominio válido."), 400)
    _decision("reclamo_ciudadano", dominio, datos={"mensaje": mensaje})
    return _html(T.reclamar(error="Reclamo registrado: la plataforma releva "
                            "las medidas vigentes y lo eleva al juez de "
                            "turno en segundos."))


# -- consola (requiere sesión) -------------------------------------------------

@app.get("/")
def bandeja(req: Request, msg: str = ""):
    sesion = _sesion(req)
    if not sesion:
        return _redirect("/login")
    ahora = reloj.ahora()
    t, jz, j = turnos.de_turno(ahora)
    turno_txt = (f"De turno: {j['nombre']} hasta el minuto "
                 f"{t['hasta_min']:g}") if t else "Sin juez de turno"
    return _html(T.bandeja(
        db.q("SELECT * FROM expedientes ORDER BY creado_min"), sesion,
        turno_txt, ahora,
        db.q("SELECT * FROM reclamos WHERE estado='elevado' ORDER BY minuto"),
        _puede_firmar(sesion), msg))


@app.get("/exp/{exp_id}")
def detalle(req: Request, exp_id: str, msg: str = ""):
    sesion = _sesion(req)
    if not sesion:
        return _redirect("/login")
    x = _expediente_completo(exp_id)
    if not x:
        return _html(T.pagina("404", "No existe"), 404)
    exp, ev, ac, oc, rec, ok = x
    return _html(T.detalle(exp, ev, ac, oc, rec, sesion,
                           _puede_firmar(sesion), msg, ok))


@app.get("/exp/{exp_id}/informe")
def informe(req: Request, exp_id: str):
    if not _sesion(req):
        return _redirect("/login")
    x = _expediente_completo(exp_id)
    if not x:
        return _html(T.pagina("404", "No existe"), 404)
    exp, ev, ac, oc, rec, ok = x
    return _html(T.informe(exp, ev, ac, oc, rec, ok))


def _aprobar(exp_id, juez_id, ahora, forzar_ip=False) -> bool:
    """Registra la aprobación (misma actuación que la consola local) y deja
    la decisión al motor. El UPDATE condicional es el anti doble clic entre
    instancias serverless."""
    if db.ejecutar("UPDATE expedientes SET estado='aprobado' WHERE id=? "
                   "AND estado IN ('detectado','elevado')", (exp_id,)) != 1:
        return False
    if forzar_ip:
        db.ejecutar("UPDATE expedientes SET tipo_bloqueo_recomendado='ip' "
                    "WHERE id=?", (exp_id,))
    db.ejecutar("UPDATE expedientes SET aprobada_por=?, aprobada_min=? "
                "WHERE id=?", (juez_id, ahora, exp_id))
    db.actuacion(exp_id, "dictamen",
                 f"Orden cautelar aprobada por {juez_id} "
                 f"({'forzando IP' if forzar_ip else 'según peritaje'})",
                 ahora)
    _decision("aprobar", exp_id, juez_id)
    return True


@app.post("/exp/aprobar-todo")
def aprobar_todo(req: Request):
    sesion = _sesion(req)
    if not sesion:
        return _redirect("/login")
    if sesion.get("rol") != "juez":
        return _redirect("/")
    ahora = reloj.ahora()
    if not _puede_firmar(sesion):
        db.actuacion(None, "dictamen",
                     f"Intento de firma en lote de {sesion['juez_id']} "
                     f"rechazado: no está de turno", ahora)
        return _redirect("/?msg=fuera-turno")
    for e in db.q("SELECT id FROM expedientes WHERE estado IN "
                  "('detectado','elevado') AND dependencia='juzgado' "
                  "ORDER BY creado_min"):
        _aprobar(e["id"], sesion["juez_id"], ahora)
    return _redirect("/")


@app.post("/reclamo/{rid}/hacer-lugar")
def hacer_lugar(req: Request, rid: str):
    sesion = _sesion(req)
    if not sesion:
        return _redirect("/login")
    if not _puede_firmar(sesion):
        db.actuacion(None, "reclamo",
                     f"Intento de hacer lugar a {rid} por "
                     f"{sesion.get('nombre', '?')} rechazado: no es juez "
                     f"de turno", reloj.ahora())
        return _redirect("/?msg=fuera-turno")
    if db.ejecutar("UPDATE reclamos SET estado='aceptado_web' WHERE id=? "
                   "AND estado='elevado'", (rid,)) == 1:
        _decision("hacer_lugar", rid, sesion["juez_id"])
    return _redirect("/")


@app.post("/exp/{exp_id}/{accion}")
def accion(req: Request, exp_id: str, accion: str):
    sesion = _sesion(req)
    if not sesion:
        return _redirect("/login")
    exp = db.q1("SELECT * FROM expedientes WHERE id=?", (exp_id,))
    if not exp:
        return _redirect("/")
    ahora = reloj.ahora()
    rol, actor = sesion.get("rol"), sesion.get("nombre", "?")
    volver = _redirect(f"/exp/{exp_id}")
    if accion.startswith("pase-"):
        dep = accion[5:]
        if rol in ("operador", "secretario", "juez", "admin") and dep in (
                "pericia", "secretaria", "juzgado", "despacho", "archivo"):
            ex.pase(exp_id, dep, actor, ahora)
        return volver
    if accion == "archivar":
        if rol in ("juez", "secretario", "admin"):
            ex.set_estado(exp_id, "archivado")
            db.actuacion(exp_id, "dictamen",
                         f"Expediente archivado por {actor}", ahora)
        return volver
    if accion in ("rechazar", "aprobar", "forzar-ip"):
        if rol != "juez":
            return volver
        if not _puede_firmar(sesion):
            db.actuacion(exp_id, "dictamen",
                         f"Intento de firma de {sesion['juez_id']} "
                         f"rechazado: no está de turno", ahora)
            return _redirect(f"/exp/{exp_id}?msg=fuera-turno")
        if accion == "rechazar":
            if db.ejecutar("UPDATE expedientes SET estado='archivado', "
                           "dependencia='archivo' WHERE id=? AND estado IN "
                           "('detectado','elevado')", (exp_id,)) != 1:
                return _redirect(f"/exp/{exp_id}?msg=ya-despachado")
            db.actuacion(exp_id, "dictamen",
                         f"Orden rechazada por {sesion['juez_id']} — "
                         f"expediente archivado", ahora)
            return volver
        if not _aprobar(exp_id, sesion["juez_id"], ahora,
                        accion == "forzar-ip"):
            return _redirect(f"/exp/{exp_id}?msg=ya-despachado")
        return volver
    return _html(T.pagina("404", "No existe"), 404)
