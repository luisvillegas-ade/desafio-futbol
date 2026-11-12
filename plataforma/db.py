"""Capa de persistencia SQLite (SSOT) + cadena de custodia en `actuaciones`.

Una sola conexión compartida protegida por un lock global: la carga es baja y
evita por completo los problemas de concurrencia de sqlite entre threads.
"""
import hashlib
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime

from . import config

_lock = threading.RLock()
_conn = None

ESQUEMA = """
CREATE TABLE IF NOT EXISTS expedientes (
    id TEXT PRIMARY KEY,                 -- EXP-2026-000001
    stream_id TEXT,
    fase_n INTEGER DEFAULT 1,
    host_stream TEXT,
    ip_servidor TEXT,
    asn INTEGER,
    tipo_bloqueo_recomendado TEXT,       -- 'ip' | 'dominio'
    estado TEXT,                         -- detectado|elevado|aprobado|en_ejecucion|cerrado|archivado
    juez_asignado TEXT,
    creado_min REAL,
    cerrado_min REAL
);

CREATE TABLE IF NOT EXISTS evidencias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expediente_id TEXT REFERENCES expedientes(id),
    deteccion_id TEXT,
    minuto REAL,
    stream_url TEXT,
    captura_b64 TEXT,
    captura_sha256 TEXT,
    marca_extraida TEXT,
    marca_valida INTEGER,
    dominios_en_ip TEXT,                 -- JSON array del DNS pasivo
    promocion TEXT,                      -- JSON: canales de difusión (X/Telegram/Discord)
    riesgo_colateral_detectado INTEGER
);

CREATE TABLE IF NOT EXISTS actuaciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expediente_id TEXT,                  -- NULL = evento de plataforma (cadena propia)
    n INTEGER,
    tipo TEXT,
    detalle TEXT,
    minuto REAL,
    timestamp_iso TEXT,
    hash_prev TEXT,
    hash_actual TEXT
);

CREATE TABLE IF NOT EXISTS ordenes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    orden_id TEXT,
    expediente_id TEXT REFERENCES expedientes(id),
    proveedor_id TEXT,
    tipo TEXT,
    objetivo TEXT,
    vence_min INTEGER,
    juzgado_id TEXT,
    juez_id TEXT,
    firma TEXT,
    estado TEXT,                         -- recibida|aplicada|fallida|vencida|levantada
    intento INTEGER DEFAULT 0,
    minuto_envio REAL,
    minuto_aplicada REAL,
    UNIQUE(orden_id, proveedor_id)
);

CREATE TABLE IF NOT EXISTS reclamos (
    id TEXT PRIMARY KEY,                 -- R-001
    dominio TEXT,
    proveedor TEXT,
    orden_id TEXT,
    mensaje TEXT,
    minuto REAL,
    estado TEXT,                         -- recibido|elevado|orden_levantada|desestimado
    resolucion_min REAL
);

CREATE TABLE IF NOT EXISTS cursores (
    clave TEXT PRIMARY KEY,
    valor REAL
);
"""


def iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def conectar() -> sqlite3.Connection:
    global _conn
    if _conn is None:
        config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        _conn = sqlite3.connect(str(config.DB_PATH), check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA synchronous=OFF")  # velocidad en Windows; la cadena
                                                 # de custodia no depende de fsync
        _conn.executescript(ESQUEMA)
        cols = [r["name"] for r in
                _conn.execute("PRAGMA table_info(evidencias)")]
        if "promocion" not in cols:
            _conn.execute("ALTER TABLE evidencias ADD COLUMN promocion TEXT")
    return _conn


def q(sql, params=()):
    with _lock:
        return conectar().execute(sql, params).fetchall()


def q1(sql, params=()):
    filas = q(sql, params)
    return filas[0] if filas else None


def ejecutar(sql, params=()):
    with _lock, conectar() as c:
        c.execute(sql, params)


@contextmanager
def bloqueo():
    """Sección crítica: hace atómico un bloque leer→escribir entre threads."""
    with _lock:
        yield


def cursor_get(clave: str, defecto: float) -> float:
    r = q1("SELECT valor FROM cursores WHERE clave=?", (clave,))
    return r["valor"] if r else defecto


def cursor_set(clave: str, valor: float) -> None:
    ejecutar(
        "INSERT INTO cursores(clave,valor) VALUES(?,?) "
        "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor", (clave, valor))


def actuacion(expediente_id, tipo: str, detalle: str, minuto: float) -> str:
    """Append-only: cada actuación encadena el hash de la anterior del expediente.

    expediente_id=None usa la cadena 'SISTEMA' (eventos de plataforma).
    """
    with _lock, conectar() as c:
        prev = c.execute(
            "SELECT n, hash_actual FROM actuaciones WHERE expediente_id IS ? "
            "ORDER BY n DESC LIMIT 1", (expediente_id,)).fetchone()
        n = (prev["n"] + 1) if prev else 1
        hprev = prev["hash_actual"] if prev else "GENESIS"
        h = hashlib.sha256(f"{hprev}|{tipo}|{detalle}|{minuto}".encode()).hexdigest()
        c.execute(
            "INSERT INTO actuaciones(expediente_id,n,tipo,detalle,minuto,timestamp_iso,"
            "hash_prev,hash_actual) VALUES(?,?,?,?,?,?,?,?)",
            (expediente_id, n, tipo, detalle, minuto, iso(), hprev, h))
        return h
