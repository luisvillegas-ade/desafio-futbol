"""Configuración central de la plataforma.

Todo es Python 3.9+ stdlib: cero dependencias externas, portabilidad absoluta.
Los valores se pueden pisar por variables de entorno o argumentos de main.py.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent          # desafio-futbol/
DATOS_DIR = BASE_DIR / "datos"
DB_PATH = Path(__file__).resolve().parent / "datos_app" / "plataforma.db"
ENTREGA_DIR = BASE_DIR / "entrega"

# OJO: usar 127.0.0.1, no 'localhost'. En Windows, 'localhost' resuelve primero
# ::1 (IPv6), el simulador escucha solo IPv4 y cada conexión espera ~2 s el
# timeout antes de caer a 127.0.0.1 — eso multiplica por ~600 el costo de cada
# request y atrasa todo el pipeline.
SERVIDOR = os.environ.get("SIMULADOR_URL", "http://127.0.0.1:8080")
PUERTO_UI = int(os.environ.get("PUERTO_UI", "8090"))

POLL_SEGUNDOS = 0.5        # polling de /estado, /detecciones, /reclamos
MONITOR_SEGUNDOS = 0.4     # polling del estado de cada orden en el proveedor
MARGEN_TURNO_MIN = 0.6     # no se firma a menos de este margen del fin del turno
                           # (el flag juez_de_turno se evalúa cuando el proveedor
                           # RECIBE la orden, no cuando se firma)
TIMEOUT_HTTP = 5.0
INTENTOS_MAX = 25          # tope de reenvíos por proveedor (Cumbre falla ~35%)

# Usuarios de demostración (las bases permiten usuarios/claves demo).
# rol=juez: firma cautelares (solo de turno). secretario/operador: tramitación
# y pases del expediente, sin firma. admin: visión completa + tramitación,
# nunca firma. rol=publico (sin login): /transparencia, /reclamar y /monitor.
USUARIOS = {
    "laura":      {"password": "demo", "rol": "juez",
                   "juez_id": "jueza-laura-ficticia"},
    "martin":     {"password": "demo", "rol": "juez",
                   "juez_id": "juez-martin-ejemplo"},
    "secretario": {"password": "demo", "rol": "secretario",
                   "nombre": "Secretaría Ejemplo"},
    "operador":   {"password": "demo", "rol": "operador",
                   "nombre": "Operador Fiscalía"},
    "admin":      {"password": "demo", "rol": "admin",
                   "nombre": "Administración"},
}
