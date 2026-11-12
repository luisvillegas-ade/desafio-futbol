"""Servidor HTTP de la consola judicial y el portal de transparencia.

Rutas:
  GET  /login, POST /login, GET /salir          — sesión del juez (cookie)
  GET  /                                        — bandeja de expedientes
  GET  /exp/<id>                                — detalle del expediente
  POST /exp/<id>/aprobar                        — firma y despacho (solo de turno)
  POST /exp/<id>/forzar-ip                      — aprobar forzando tipo IP (demo reclamos)
  POST /exp/<id>/rechazar                       — archivar
  GET  /transparencia                           — público, sin login
"""
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .. import config, db
from . import templates as T
from ..motor import expediente as ex

SESIONES = {}  # sid -> juez dict {"id","nombre"}


class ServidorUI(threading.Thread):
    def __init__(self, reloj, turnos, dispatcher, puerto: int):
        super().__init__(daemon=True, name="Thread-WebUI")
        self.reloj = reloj
        self.turnos = turnos
        self.dispatcher = dispatcher
        self.puerto = puerto
        self.httpd = None

    def run(self) -> None:
        ui = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            # -- helpers ----------------------------------------------------
            def _html(self, s: str, estado=200):
                b = s.encode("utf-8")
                self.send_response(estado)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(b)))
                self.end_headers()
                self.wfile.write(b)

            def _redirect(self, ruta: str):
                self.send_response(303)
                self.send_header("Location", ruta)
                self.end_headers()

            def _sesion(self):
                from http.cookies import SimpleCookie
                c = SimpleCookie(self.headers.get("Cookie"))
                sid = c["sid"].value if "sid" in c else None
                return SESIONES.get(sid)

            # -- rutas GET ---------------------------------------------------
            def do_GET(self):
                partes = [p for p in urlparse(self.path).path.split("/") if p]
                if partes == ["login"]:
                    return self._html(T.login())
                if partes == ["salir"]:
                    self.send_response(303)
                    self.send_header("Location", "/login")
                    self.send_header("Set-Cookie", "sid=; Max-Age=0; Path=/")
                    self.end_headers()
                    return
                if partes == ["transparencia"]:
                    ordenes = db.q("SELECT * FROM ordenes ORDER BY id")
                    return self._html(T.transparencia(ordenes, ui.reloj.ahora()))
                sesion = self._sesion()
                if not sesion:
                    return self._redirect("/login")
                if not partes:
                    exps = db.q("SELECT * FROM expedientes ORDER BY creado_min")
                    ahora = ui.reloj.ahora()
                    t, jz, j = ui.turnos.de_turno(ahora)
                    turno_txt = (f"De turno: {j['nombre']} hasta el minuto "
                                 f"{t['hasta_min']:g}") if t else "Sin juez de turno"
                    return self._html(T.bandeja(exps, sesion, turno_txt, ahora))
                if len(partes) == 2 and partes[0] == "exp":
                    exp = db.q1("SELECT * FROM expedientes WHERE id=?", (partes[1],))
                    if not exp:
                        return self._html(T.pagina("404", "No existe"), 404)
                    ev = db.q("SELECT * FROM evidencias WHERE expediente_id=?", (exp["id"],))
                    ac = db.q("SELECT * FROM actuaciones WHERE expediente_id=? ORDER BY n", (exp["id"],))
                    oc = db.q("SELECT * FROM ordenes WHERE expediente_id=?", (exp["id"],))
                    return self._html(T.detalle(dict(exp), ev, ac, oc))
                self._html(T.pagina("404", "No existe"), 404)

            # -- rutas POST --------------------------------------------------
            def do_POST(self):
                partes = [p for p in urlparse(self.path).path.split("/") if p]
                largo = int(self.headers.get("Content-Length", "0"))
                cuerpo = parse_qs(self.rfile.read(largo).decode())
                if partes == ["login"]:
                    u = cuerpo.get("usuario", [""])[0]
                    p = cuerpo.get("password", [""])[0]
                    datos = config.USUARIOS_JUEZ.get(u)
                    if not datos or datos["password"] != p:
                        return self._html(T.login("Usuario o contraseña incorrectos"), 403)
                    juez = ui.turnos.jueces.get(datos["juez_id"])
                    sesion = {"juez_id": datos["juez_id"],
                              "nombre": juez[1]["nombre"] if juez else datos["juez_id"]}
                    sid = secrets.token_hex(16)
                    SESIONES[sid] = sesion
                    self.send_response(303)
                    self.send_header("Location", "/")
                    self.send_header("Set-Cookie", f"sid={sid}; Path=/; HttpOnly")
                    self.end_headers()
                    return
                sesion = self._sesion()
                if not sesion:
                    return self._redirect("/login")
                if len(partes) == 3 and partes[0] == "exp":
                    exp_id, accion = partes[1], partes[2]
                    return self._accion(exp_id, accion, sesion)
                self._html(T.pagina("404", "No existe"), 404)

            def _accion(self, exp_id, accion, sesion):
                exp = db.q1("SELECT * FROM expedientes WHERE id=?", (exp_id,))
                if not exp:
                    return self._redirect("/")
                ahora = ui.reloj.ahora()
                t, jz, j = ui.turnos.de_turno(ahora)
                if accion == "rechazar":
                    ex.set_estado(exp_id, "archivado")
                    db.actuacion(exp_id, "dictamen",
                                 f"Orden rechazada por {sesion['juez_id']} — "
                                 f"expediente archivado", ahora)
                    return self._redirect(f"/exp/{exp_id}")
                if accion in ("aprobar", "forzar-ip"):
                    if not t or t["juez_id"] != sesion["juez_id"]:
                        db.actuacion(exp_id, "dictamen",
                                     f"Intento de firma de {sesion['juez_id']} "
                                     f"rechazado: no está de turno", ahora)
                        return self._redirect(f"/exp/{exp_id}")
                    if accion == "forzar-ip":
                        db.ejecutar("UPDATE expedientes SET "
                                    "tipo_bloqueo_recomendado='ip' WHERE id=?",
                                    (exp_id,))
                        exp = db.q1("SELECT * FROM expedientes WHERE id=?", (exp_id,))
                    ex.set_estado(exp_id, "aprobado")
                    db.actuacion(exp_id, "dictamen",
                                 f"Orden cautelar aprobada por {sesion['juez_id']} "
                                 f"({'forzando IP' if accion=='forzar-ip' else 'según peritaje'})",
                                 ahora)
                    ex.set_estado(exp_id, "en_ejecucion")
                    ui.dispatcher.despachar_expediente(dict(exp))
                    return self._redirect(f"/exp/{exp_id}")
                self._html(T.pagina("404", "No existe"), 404)

        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.puerto), H)
        self.httpd.serve_forever()
