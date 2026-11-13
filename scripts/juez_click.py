"""Herramienta de pruebas (no entregable): hace los clics del juez de turno.

Simula el trabajo humano en la consola judicial a máxima velocidad para
verificar el circuito interactivo de punta a punta sin clics manuales:
login del juez de turno -> aprobar expedientes elevados -> hacer lugar a
reclamos elevados. Al cambio de turno re-loguea con el juez entrante.

Uso (con la plataforma corriendo en --modo interactivo):
    python scripts/juez_click.py [--forzar-ip tv.verpartido-hd.test] [--lote]

--lote: usa POST /exp/aprobar-todo (firma en lote) en vez de un clic por
expediente.
"""
import json
import sqlite3
import sys
import time
import urllib.parse
import urllib.request

UI = "http://127.0.0.1:8090"
SIM = "http://127.0.0.1:8080"
DB = "plataforma/datos_app/plataforma.db"
USUARIO = {"jueza-laura-ficticia": "laura", "juez-martin-ejemplo": "martin"}

op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor())


def post(ruta, datos=None):
    return op.open(UI + ruta, urllib.parse.urlencode(datos or {}).encode())


def turno():
    try:
        with urllib.request.urlopen(SIM + "/estado", timeout=3) as r:
            return json.load(r).get("jueces_de_turno", [])
    except Exception:
        return []


def db_q(sql, params=()):
    c = sqlite3.connect(DB)
    try:
        return c.execute(sql, params).fetchall()
    finally:
        c.close()


def main():
    forzar = None
    if "--forzar-ip" in sys.argv:
        forzar = sys.argv[sys.argv.index("--forzar-ip") + 1]
    lote = "--lote" in sys.argv
    logueado = None
    ya_forzado = False
    while True:
        jueces = turno()
        usuario = USUARIO.get(jueces[0]) if jueces else None
        if usuario and usuario != logueado:
            try:
                post("/login", {"usuario": usuario, "password": "demo"})
                print(f"[juez] login como {usuario}", flush=True)
                logueado = usuario
            except Exception as e:
                print(f"[juez] login {usuario}: {e}", flush=True)
        if usuario:
            if forzar and not ya_forzado:
                for (exp_id,) in db_q(
                        "SELECT id FROM expedientes WHERE host_stream=? "
                        "AND estado='elevado'", (forzar,)):
                    try:
                        post(f"/exp/{exp_id}/forzar-ip")
                        print(f"[juez] forzar-ip en {exp_id}", flush=True)
                        ya_forzado = True
                    except Exception as e:
                        print(f"[juez] forzar-ip {exp_id}: {e}", flush=True)
            elevados = db_q("SELECT id FROM expedientes WHERE estado='elevado'")
            if lote and elevados:
                try:
                    post("/exp/aprobar-todo")
                    print(f"[juez] aprobar-todo ({len(elevados)})", flush=True)
                except Exception as e:
                    print(f"[juez] aprobar-todo: {e}", flush=True)
                elevados = []
            for (exp_id,) in elevados:
                try:
                    post(f"/exp/{exp_id}/aprobar")
                    print(f"[juez] aprobado {exp_id}", flush=True)
                except Exception as e:
                    print(f"[juez] aprobar {exp_id}: {e}", flush=True)
            for (rid,) in db_q(
                    "SELECT id FROM reclamos WHERE estado='elevado'"):
                try:
                    post(f"/reclamo/{rid}/hacer-lugar")
                    print(f"[juez] hizo lugar a {rid}", flush=True)
                except Exception as e:
                    print(f"[juez] resolver {rid}: {e}", flush=True)
        time.sleep(0.3)


if __name__ == "__main__":
    main()
