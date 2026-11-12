"""Lanzador todo-en-uno para la demo (no es entregable, es comodidad).

Un solo comando arranca TODO:
  1. simulador del partido (con PYTHONUTF8 ya puesto, funciona en Windows)
  2. plataforma en modo interactivo (el juez aprueba en la web)
  3. abre el navegador en la consola judicial
  4. cuando termina el partido, corre verificar.py y muestra el puntaje

Uso:
    python demo.py                    # partido a x6 (~17 min reales)
    python demo.py --acelerar 60      # ~2 min, para iterar
    python demo.py --inicio-min 40    # arranca en el min 40
    python demo.py --modo auto        # sin clicks del juez, corre solo

Para frenar antes de tiempo: Ctrl+C (mata todo limpio).
Si los puertos 8080/8090 están ocupados por corridas viejas, pregunta si
los frena antes de arrancar.
"""
import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).parent
SIM_URL = "http://127.0.0.1:8080"
UI_URL = "http://127.0.0.1:8090"
PUERTOS = (8080, 8090)


def log(msg):
    print(msg, flush=True)


def esperar_http(url, timeout=15):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            urllib.request.urlopen(url, timeout=2)
            return True
        except Exception:
            time.sleep(0.4)
    return False


def estado():
    try:
        with urllib.request.urlopen(SIM_URL + "/estado", timeout=3) as r:
            return json.load(r)
    except Exception:
        return None


def pids_en_puerto(puerto):
    """PIDs escuchando en TCP :puerto (Windows). Vacío si no hay."""
    try:
        out = subprocess.run(["netstat", "-ano"], capture_output=True,
                             text=True, timeout=10).stdout
    except Exception:
        return set()
    pids = set()
    for linea in out.splitlines():
        partes = linea.split()
        if (len(partes) >= 5 and partes[0] == "TCP"
                and partes[1].endswith(f":{puerto}")
                and partes[-1] == "LISTENING"):
            pids.add(partes[-1])
    return pids


def limpiar_puertos():
    """Si hay procesos viejos en 8080/8090, pregunta y los mata."""
    ocupados = set()
    for p in PUERTOS:
        ocupados |= pids_en_puerto(p)
    ocupados.discard(str(os.getpid()))
    if not ocupados:
        return
    log(f"[demo] puertos 8080/8090 ocupados por PID(s): {', '.join(sorted(ocupados))}")
    log("       (corridas viejas del simulador/plataforma todavía vivas)")
    try:
        resp = input("[demo] ¿los freno? [s/N] ").strip().lower()
    except EOFError:
        resp = ""
    if resp != "s":
        log("[demo] no se frenaron: cerrá las ventanas viejas o volvé a correr "
            "con Enter para abortar.")
        sys.exit(1)
    for pid in ocupados:
        subprocess.run(["taskkill", "/PID", pid, "/F"],
                       capture_output=True)
        log(f"[demo] PID {pid} frenado")
    time.sleep(1)


def main():
    ap = argparse.ArgumentParser(description="Demo todo-en-uno")
    ap.add_argument("--acelerar", type=float, default=6)
    ap.add_argument("--modo", choices=["auto", "interactivo"],
                    default="interactivo")
    ap.add_argument("--inicio-min", type=float, default=None)
    a = ap.parse_args()

    limpiar_puertos()

    env = dict(os.environ, PYTHONUTF8="1")
    log_dir = RAIZ / "salida"
    log_dir.mkdir(exist_ok=True)

    cmd_sim = [sys.executable, "simulador/servidor.py",
               "--escenario", "datos/escenario_practica.json",
               "--acelerar", str(a.acelerar),
               "--log", "salida/registro.jsonl"]
    if a.inicio_min is not None:
        cmd_sim += ["--inicio-min", str(a.inicio_min)]
    cmd_plat = [sys.executable, "-m", "plataforma.main",
                "--modo", a.modo, "--reset"]

    sim_log = open(log_dir / "sim.log", "w", encoding="utf-8")
    plat_log = open(log_dir / "plataforma.log", "w", encoding="utf-8")
    sim = plat = None
    try:
        sim = subprocess.Popen(cmd_sim, cwd=RAIZ, env=env,
                               stdout=sim_log, stderr=subprocess.STDOUT)
        if not esperar_http(SIM_URL + "/estado"):
            log("[demo] el simulador no arranco. Ver salida/sim.log")
            return
        if sim.poll() is not None:
            log("[demo] el simulador murio al arrancar. Ver salida/sim.log")
            return
        log("[demo] simulador corriendo  (log: salida/sim.log)")

        plat = subprocess.Popen(cmd_plat, cwd=RAIZ, env=env,
                                stdout=plat_log, stderr=subprocess.STDOUT)
        if not esperar_http(UI_URL + "/transparencia"):
            log("[demo] la plataforma no levanto la UI. Ver salida/plataforma.log")
            return
        webbrowser.open(UI_URL)
        log(f"[demo] plataforma corriendo (log: salida/plataforma.log)")
        log(f"[demo] consola judicial: {UI_URL}  (laura / martin — clave: demo)")
        if a.modo == "interactivo":
            log("[demo] vos sos el juez: aprobá/rechazá en la web")
        log("[demo] Ctrl+C para frenar todo\n")

        ultimo = -1
        while True:
            e = estado()
            if e is None:
                log("[demo] no responde el simulador; saliendo")
                break
            if plat.poll() is not None:
                log("[demo] la plataforma se cayo. Ver salida/plataforma.log")
                break
            m = int(e["minuto_actual"])
            if m != ultimo:
                jueces = ", ".join(e.get("jueces_de_turno", []))
                log(f"  min {e['minuto_actual']:6.1f} / {e['fin_min']:.0f}"
                    f"   juez de turno: {jueces}")
                ultimo = m
            # esperar fin del partido + 5 min de gracia para que verificar
            # pueda evaluar vencimientos post-partido
            if e["minuto_actual"] >= e["fin_min"] + 5:
                break
            time.sleep(1)

        log("\n[demo] partido terminado — evaluando...\n")
        subprocess.run([sys.executable, "evaluacion/verificar.py",
                        "--log", "salida/registro.jsonl"], cwd=RAIZ, env=env)
    except KeyboardInterrupt:
        log("\n[demo] frenado por el usuario")
    finally:
        for p in (plat, sim):
            if p and p.poll() is None:
                p.terminate()
        sim_log.close()
        plat_log.close()


if __name__ == "__main__":
    main()
