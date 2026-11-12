"""Test de integración del circuito de reclamos (temporal, no es entregable).

Loguea como la jueza Laura en la UI, espera a que exista el expediente de
tv.verpartido-hd.test y le pega a 'forzar-ip': eso bloquea la IP compartida
192.0.2.50 -> daño colateral -> reclamos automáticos -> levantamiento firmado
+ reemplazo por dominio. Después, verificar.py debe mostrar reclamos resueltos.
"""
import json
import sqlite3
import time
import urllib.request
import urllib.parse

UI = "http://127.0.0.1:8090"
op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())


def post(ruta, datos):
    return op.open(UI + ruta, urllib.parse.urlencode(datos).encode())


def main():
    # 1. login
    post("/login", {"usuario": "laura", "password": "demo"})
    print("login ok")

    # 2. esperar el expediente de verpartido (lectura directa de la BD, WAL ok)
    exp_id = None
    for _ in range(60):
        try:
            c = sqlite3.connect("plataforma/datos_app/plataforma.db")
            r = c.execute("SELECT id FROM expedientes WHERE host_stream=?",
                          ("tv.verpartido-hd.test",)).fetchone()
            c.close()
            if r:
                exp_id = r[0]
                break
        except Exception:
            pass
        time.sleep(0.5)
    print("expediente:", exp_id)
    if not exp_id:
        return

    # 3. aprobar forzando IP -> colateral -> reclamos
    r = post(f"/exp/{exp_id}/forzar-ip", {})
    print("forzar-ip:", r.status)
    print("Esperando reclamos y levantamientos...")


if __name__ == "__main__":
    main()
