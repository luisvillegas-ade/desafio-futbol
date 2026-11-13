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


def hilo_cierre(reloj, detener):
    """Cierra el circuito al vencer la ventana (fin del partido + gracia):

    toda cautelar vence al minuto fin_min — los expedientes no archivados
    pasan a 'cerrado' en dependencia 'archivo' con su cerrado_min, y queda
    asentada la actuación 'vencimiento' en cada cadena.
    """
    cerrado = False
    while not detener.is_set() and not cerrado:
        if reloj.ahora() >= reloj.fin_min + 5.0:
            ahora = reloj.ahora()
            with db.bloqueo():
                exps = db.q("SELECT id FROM expedientes WHERE estado NOT IN "
                            "('archivado','cerrado')")
                for e in exps:
                    db.ejecutar(
                        "UPDATE expedientes SET estado='cerrado', "
                        "dependencia='archivo', cerrado_min=? WHERE id=?",
                        (ahora, e["id"]))
                    db.actuacion(
                        e["id"], "vencimiento",
                        f"Vencieron las medidas cautelares (fin del partido "
                        f"+ 5 min de gracia, min {ahora:.1f}): el expediente "
                        f"pasa a archivo", ahora)
            if exps:
                db.actuacion(
                    None, "vencimiento",
                    f"Cierre del circuito al min {ahora:.1f}: {len(exps)} "
                    f"expediente(s) pasan a archivo", ahora)
            cerrado = True
        time.sleep(1.0)


def main() -> None:
    p = argparse.ArgumentParser(description="Plataforma de bloqueo en vivo")
    p.add_argument("--servidor", default=config.SERVIDOR)
    p.add_argument("--modo", choices=["auto", "interactivo"],
                   default="interactivo",
                   help="interactivo: el juez aprueba y firma desde la web "
                        "(modo de evaluación). auto: firma sola como orden "
                        "marco — solo para pruebas internas")
    p.add_argument("--puerto-ui", type=int, default=config.PUERTO_UI)
    p.add_argument("--reset", action="store_true", help="borra la BD al arrancar")
    p.add_argument("--sin-ui", action="store_true")
    p.add_argument("--red", action="store_true",
                   help="consola en 0.0.0.0 (jueces desde la wifi local); "
                        "por defecto solo 127.0.0.1")
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
    dispatcher = Dispatcher(cliente, reloj, turnos,
                            modo_auto=(args.modo == "auto"))
    gestor = mod_reclamos.GestorReclamos(cliente, reloj, turnos, dispatcher,
                                        modo_auto=(args.modo == "auto"))

    poller = Poller(cliente, reloj, turnos, verificador, dispatcher, gestor,
                    modo_auto=(args.modo == "auto"))
    detener = threading.Event()
    t_turnos = threading.Thread(target=hilo_turnos, args=(reloj, turnos, detener),
                                daemon=True, name="Thread-RelojTurnos")
    t_cierre = threading.Thread(target=hilo_cierre, args=(reloj, detener),
                                daemon=True, name="Thread-Cierre")
    poller.start()
    t_turnos.start()
    t_cierre.start()

    if not args.sin_ui:
        from .juez.servidor_ui import ServidorUI
        ServidorUI(reloj, turnos, dispatcher, args.puerto_ui,
                   modo=args.modo, poller=poller, verificador=verificador,
                   gestor=gestor,
                   host="0.0.0.0" if args.red else "127.0.0.1").start()
        print(f"[main] consola judicial: http://127.0.0.1:{args.puerto_ui} "
              f"(laura/martin, clave demo)")
        if args.red:
            import socket
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.connect(("10.255.255.255", 1))
                ip_lan = s.getsockname()[0]
                s.close()
            except OSError:
                ip_lan = "<ip-de-esta-notebook>"
            print(f"[main] --red: consola en la wifi local: "
                  f"http://{ip_lan}:{args.puerto_ui}")

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
