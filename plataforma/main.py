"""Orquestador principal de la plataforma.

Uso (desde desafio-futbol/):
    python -m plataforma.main [--servidor URL] [--modo auto|interactivo]
                              [--puerto-ui 8090] [--reset] [--sin-ui] [--exportar]

Hilos:
  - Thread-Poller:      /estado, /detecciones, /reclamos (cada POLL_SEGUNDOS)
  - Thread-RelojTurnos: transfiere expedientes pendientes al juez entrante
  - workers dispatcher: un thread por (expediente, proveedor) bajo demanda
  - Thread-WebUI:       consola judicial + transparencia (puerto 8090)
"""
import argparse
import json
import threading
import time

from . import config, db
from .auditoria import exportar
from .cliente_sim import ClienteSim
from .motor import reclamos as mod_reclamos
from .motor.dispatcher import Dispatcher
from .motor.poller import Poller
from .motor.reloj import Reloj
from .motor.turnos import Turnos
from .motor.verificador import Verificador


def hilo_turnos(reloj, turnos, detener):
    """Transfiere los expedientes pendientes de firma al juez entrante."""
    ultimo = None
    while not detener.is_set():
        ahora = reloj.ahora()
        t, jz, j = turnos.de_turno(ahora)
        if t and j["id"] != ultimo:
            if ultimo is not None:
                db.ejecutar(
                    "UPDATE expedientes SET juez_asignado=? WHERE estado IN "
                    "('detectado','elevado')", (j["id"],))
                db.actuacion(
                    None, "cambio_turno",
                    f"Cambio de turno en minuto {ahora:.2f}: entra {j['id']}. "
                    f"Expedientes pendientes transferidos.", ahora)
            ultimo = j["id"]
        time.sleep(0.5)


def main() -> None:
    p = argparse.ArgumentParser(description="Plataforma de bloqueo en vivo")
    p.add_argument("--servidor", default=config.SERVIDOR)
    p.add_argument("--modo", choices=["auto", "interactivo"], default="auto",
                   help="auto: firma inmediata (orden marco). interactivo: el "
                        "juez aprueba desde la web")
    p.add_argument("--puerto-ui", type=int, default=config.PUERTO_UI)
    p.add_argument("--reset", action="store_true", help="borra la BD al arrancar")
    p.add_argument("--sin-ui", action="store_true")
    p.add_argument("--exportar", action="store_true",
                   help="exporta entrega/ y sale")
    args = p.parse_args()

    if args.reset and config.DB_PATH.exists():
        config.DB_PATH.unlink()
        print("[main] base de datos reiniciada")
    if args.exportar:
        db.conectar()
        exportar.exportar()
        return

    cliente = ClienteSim(args.servidor, timeout=config.TIMEOUT_HTTP)
    reloj = Reloj()
    turnos = Turnos(reloj)
    verificador = Verificador(cliente)
    dispatcher = Dispatcher(cliente, reloj, turnos)
    gestor = mod_reclamos.GestorReclamos(cliente, reloj, turnos, dispatcher)

    poller = Poller(cliente, reloj, turnos, verificador, dispatcher, gestor,
                    modo_auto=(args.modo == "auto"))
    detener = threading.Event()
    t_turnos = threading.Thread(target=hilo_turnos, args=(reloj, turnos, detener),
                                daemon=True, name="Thread-RelojTurnos")
    poller.start()
    t_turnos.start()

    if not args.sin_ui:
        from .juez.servidor_ui import ServidorUI
        ServidorUI(reloj, turnos, dispatcher, args.puerto_ui).start()
        print(f"[main] consola judicial: http://127.0.0.1:{args.puerto_ui} "
              f"(laura/martin, clave demo)")

    db.actuacion(None, "plataforma_iniciada",
                 f"Plataforma iniciada en modo {args.modo} contra {args.servidor}",
                 0.0)
    print(f"[main] modo={args.modo} servidor={args.servidor} — Ctrl+C para salir")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[main] deteniendo…")
        detener.set()
        poller.detener.set()


if __name__ == "__main__":
    main()
