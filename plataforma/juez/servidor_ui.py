"""Servidor HTTP de la consola judicial y el portal de transparencia.

Rutas:
  GET  /login, POST /login, GET /salir          — sesión del juez (cookie)
  GET  /                                        — bandeja de expedientes
  GET  /exp/<id>                                — detalle del expediente
  POST /exp/<id>/aprobar                        — firma y despacho (solo de turno)
  POST /exp/<id>/forzar-ip                      — aprobar forzando tipo IP (demo reclamos)
  POST /exp/<id>/rechazar                       — archivar
  GET  /transparencia                           — público, sin login
  GET  /monitor, /monitor/datos                 — monitor en vivo (público)
  GET|POST /reclamar                            — reclamo digital público
  POST /exp/<id>/pase-<dep>                     — movimiento entre dependencias
  POST /exp/<id>/revision                       — re-peritaje (iniciar revisión)
  POST /exp/<id>/archivar                       — archivo definitivo (juez)
  GET  /exp/<id>/informe                        — informe imprimible

Roles (config.USUARIOS): juez (firma solo de turno), secretario y operador
(pases, revisión, informes; sin firma). Público: transparencia, monitor,
reclamar.
"""
import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .. import config, db
from . import templates as T
from . import monitor as M
from ..motor import expediente as ex

SESIONES = {}  # sid -> juez dict {"id","nombre"}


class ServidorUI(threading.Thread):
    def __init__(self, reloj, turnos, dispatcher, puerto: int,
                 modo: str = "auto", poller=None, verificador=None,
                 gestor=None):
        super().__init__(daemon=True, name="Thread-WebUI")
        self.reloj = reloj
        self.turnos = turnos
        self.dispatcher = dispatcher
        self.puerto = puerto
        self.modo = modo
        self.poller = poller
        self.verificador = verificador
        self.gestor = gestor
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

            def _json(self, b: bytes, estado=200):
                self.send_response(estado)
                self.send_header("Content-Type", "application/json; charset=utf-8")
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
                if partes == ["monitor"]:
                    return self._html(M.pagina())
                if partes == ["monitor", "datos"]:
                    return self._json(M.datos_json(ui.reloj, ui.turnos,
                                                   ui.modo, ui.poller))
                if partes == ["reclamar"]:
                    return self._html(T.reclamar())
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
                    return self._html(T.detalle(dict(exp), ev, ac, oc,
                                                self._reclamos_de(exp["id"]),
                                                sesion))
                if len(partes) == 3 and partes[0] == "exp" and partes[2] == "informe":
                    exp = db.q1("SELECT * FROM expedientes WHERE id=?", (partes[1],))
                    if not exp:
                        return self._html(T.pagina("404", "No existe"), 404)
                    ev = db.q("SELECT * FROM evidencias WHERE expediente_id=?", (exp["id"],))
                    ac = db.q("SELECT * FROM actuaciones WHERE expediente_id=? ORDER BY n", (exp["id"],))
                    oc = db.q("SELECT * FROM ordenes WHERE expediente_id=?", (exp["id"],))
                    return self._html(T.informe(dict(exp), ev, ac, oc,
                                                self._reclamos_de(exp["id"])))
                self._html(T.pagina("404", "No existe"), 404)

            def _reclamos_de(self, exp_id):
                return db.q(
                    "SELECT r.* FROM reclamos r JOIN ordenes o "
                    "ON o.orden_id=r.orden_id WHERE o.expediente_id=? "
                    "ORDER BY r.minuto", (exp_id,))

            # -- rutas POST --------------------------------------------------
            def do_POST(self):
                partes = [p for p in urlparse(self.path).path.split("/") if p]
                largo = int(self.headers.get("Content-Length", "0"))
                cuerpo = parse_qs(self.rfile.read(largo).decode())
                if partes == ["login"]:
                    u = cuerpo.get("usuario", [""])[0]
                    p = cuerpo.get("password", [""])[0]
                    datos = config.USUARIOS.get(u)
                    if not datos or datos["password"] != p:
                        return self._html(T.login("Usuario o contraseña incorrectos"), 403)
                    juez = ui.turnos.jueces.get(datos.get("juez_id")) \
                        if datos.get("juez_id") else None
                    sesion = {"juez_id": datos.get("juez_id"),
                              "rol": datos["rol"],
                              "nombre": juez[1]["nombre"] if juez
                                        else datos.get("nombre", u)}
                    sid = secrets.token_hex(16)
                    SESIONES[sid] = sesion
                    self.send_response(303)
                    self.send_header("Location", "/")
                    self.send_header("Set-Cookie", f"sid={sid}; Path=/; HttpOnly")
                    self.end_headers()
                    return
                if partes == ["reclamar"]:
                    dominio = cuerpo.get("dominio", [""])[0].strip()
                    mensaje = cuerpo.get("mensaje", [""])[0].strip()
                    if not dominio or "." not in dominio:
                        return self._html(T.reclamar(
                            error="Ingrese un dominio válido."), 400)
                    if not ui.gestor:
                        return self._html(T.reclamar(
                            error="El módulo de reclamos no está activo."), 503)
                    n = ui.gestor.procesar_ciudadano(dominio, mensaje)
                    return self._html(T.reclamar(exito=n))
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
                rol = sesion.get("rol")
                actor = sesion.get("nombre", "?")

                if accion.startswith("pase-"):
                    if rol not in ("operador", "secretario", "juez", "admin"):
                        return self._redirect(f"/exp/{exp_id}")
                    dep = accion[5:]
                    if dep not in ("pericia", "secretaria", "juzgado",
                                   "despacho", "archivo"):
                        return self._redirect(f"/exp/{exp_id}")
                    ex.pase(exp_id, dep, actor, ahora)
                    return self._redirect(f"/exp/{exp_id}")
                if accion == "archivar":
                    if rol not in ("juez", "secretario", "admin"):
                        return self._redirect(f"/exp/{exp_id}")
                    ex.set_estado(exp_id, "archivado")
                    db.actuacion(exp_id, "dictamen",
                                 f"Expediente archivado por {actor}", ahora)
                    return self._redirect(f"/exp/{exp_id}")
                if accion == "revision":
                    if rol not in ("operador", "secretario", "juez", "admin"):
                        return self._redirect(f"/exp/{exp_id}")
                    return self._revision(exp, actor, ahora)

                if accion == "rechazar":
                    if rol != "juez":
                        return self._redirect(f"/exp/{exp_id}")
                    if not t or t["juez_id"] != sesion["juez_id"]:
                        db.actuacion(exp_id, "dictamen",
                                     f"Intento de firma de {sesion['juez_id']} "
                                     f"rechazado: no está de turno", ahora)
                        return self._redirect(f"/exp/{exp_id}")
                    ex.set_estado(exp_id, "archivado")
                    db.actuacion(exp_id, "dictamen",
                                 f"Orden rechazada por {sesion['juez_id']} — "
                                 f"expediente archivado", ahora)
                    return self._redirect(f"/exp/{exp_id}")
                if accion in ("aprobar", "forzar-ip"):
                    if rol != "juez":
                        return self._redirect(f"/exp/{exp_id}")
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

            def _revision(self, exp, actor, ahora):
                """Re-peritaje: re-consulta DNS pasivo y re-clasifica la medida."""
                exp_id = exp["id"]
                ex.pase(exp_id, "pericia", actor, ahora)
                det = {"id": f"REV-{ahora:.2f}", "host_stream": exp["host_stream"],
                       "ip_servidor": exp["ip_servidor"], "asn": exp["asn"],
                       "minuto": ahora,
                       "marca_de_agua_extraida": "", "captura": {}}
                tipo, objetivo, dominios, ajenos = \
                    ui.verificador.analizar_colateral(det)
                riesgo = (f"{len(ajenos)} dominio(s) ajeno(s) en la IP"
                          if ajenos else "IP dedicada, sin riesgo colateral")
                db.actuacion(
                    exp_id, "revision",
                    f"Revisión ordenada por {actor}: re-peritaje de "
                    f"{exp['ip_servidor']} — {riesgo}. Medida recalculada: "
                    f"{tipo} -> {objetivo}", ahora)
                if tipo != exp["tipo_bloqueo_recomendado"]:
                    db.ejecutar(
                        "UPDATE expedientes SET tipo_bloqueo_recomendado=? "
                        "WHERE id=?", (tipo, exp_id))
                    db.actuacion(
                        exp_id, "revision",
                        f"La medida sugerida cambia: "
                        f"{exp['tipo_bloqueo_recomendado']} -> {tipo}", ahora)
                return self._redirect(f"/exp/{exp_id}")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", self.puerto), H)
        self.httpd.serve_forever()
