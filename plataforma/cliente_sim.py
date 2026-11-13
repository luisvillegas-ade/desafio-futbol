"""Cliente HTTP robusto hacia el simulador (stdlib, urllib).

Devuelve siempre (status, json). Los errores de transporte se reintentan;
los errores HTTP (4xx/5xx) se devuelven con su cuerpo para que el motor decida.
"""
import http.client
import json
import os
import socket
import ssl
import time
import urllib.error
import urllib.request

# Si el DNS de la red no resuelve el nombre del simulador (p. ej. sslip.io
# bloqueado), SIMULADOR_IP=a.b.c.d conecta a esa IP manteniendo el nombre
# para SNI, Host y la verificación del certificado.
_IP_FIJA = os.environ.get("SIMULADOR_IP", "").strip()


class _ConexionIPFija(http.client.HTTPSConnection):
    def connect(self):
        sock = socket.create_connection((_IP_FIJA, self.port), self.timeout)
        self.sock = ssl.create_default_context().wrap_socket(
            sock, server_hostname=self.host)


class _HandlerIPFija(urllib.request.HTTPSHandler):
    def https_open(self, req):
        return self.do_open(_ConexionIPFija, req)


_opener = urllib.request.build_opener(
    *([_HandlerIPFija] if _IP_FIJA else []))


class ClienteSim:
    def __init__(self, base: str, timeout: float = 5.0):
        # 'localhost' en Windows tarda ~2 s por request (primero intenta ::1 y
        # el simulador solo escucha IPv4). Forzamos la IP literal.
        self.base = base.rstrip("/").replace("://localhost", "://127.0.0.1")
        self.timeout = timeout

    def _req(self, metodo: str, ruta: str, cuerpo=None, reintentos: int = 3):
        datos = json.dumps(cuerpo).encode("utf-8") if cuerpo is not None else None
        ultimo = None
        for _ in range(reintentos):
            req = urllib.request.Request(
                self.base + ruta, data=datos,
                headers={"Content-Type": "application/json"}, method=metodo)
            try:
                with _opener.open(req, timeout=self.timeout) as resp:
                    crudo = resp.read() or b"{}"
                    return resp.status, json.loads(crudo)
            except urllib.error.HTTPError as e:
                try:
                    return e.code, json.loads(e.read() or b"{}")
                except Exception:
                    return e.code, {}
            except Exception as e:        # error de transporte: reintentar
                ultimo = e
                time.sleep(0.2)
        raise RuntimeError(f"Simulador inalcanzable en {ruta}: {ultimo}")

    def get(self, ruta: str):
        return self._req("GET", ruta)

    def post(self, ruta: str, cuerpo: dict):
        return self._req("POST", ruta, cuerpo)
