"""Cliente HTTP robusto hacia el simulador (stdlib, urllib).

Devuelve siempre (status, json). Los errores de transporte se reintentan;
los errores HTTP (4xx/5xx) se devuelven con su cuerpo para que el motor decida.
"""
import json
import time
import urllib.error
import urllib.request


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
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
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
