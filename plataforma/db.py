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
    dependencia TEXT DEFAULT 'pericia',  -- pericia|secretaria|juzgado|despacho|archivo
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
    riesgo_colateral_detectado INTEGER,
    captura_meta TEXT,                   -- JSON: formato/duracion/pagina de la captura
    huella TEXT                          -- sha256 canónico de la fila probatoria
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
    huella TEXT,                         -- sha256 canónico de la fila (firma+juez+objeto)
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
        cols_e = [r["name"] for r in
                  _conn.execute("PRAGMA table_info(expedientes)")]
        if "dependencia" not in cols_e:
            _conn.execute("ALTER TABLE expedientes ADD COLUMN dependencia "
                          "TEXT DEFAULT 'pericia'")
        if "aprobada_por" not in cols_e:
            _conn.execute("ALTER TABLE expedientes "
                          "ADD COLUMN aprobada_por TEXT")
        if "aprobada_min" not in cols_e:
            _conn.execute("ALTER TABLE expedientes "
                          "ADD COLUMN aprobada_min REAL")
        cols_v = [r["name"] for r in
                  _conn.execute("PRAGMA table_info(evidencias)")]
        if "captura_meta" not in cols_v:
            _conn.execute("ALTER TABLE evidencias "
                          "ADD COLUMN captura_meta TEXT")
        if "huella" not in cols_v:
            _conn.execute("ALTER TABLE evidencias ADD COLUMN huella TEXT")
        cols_o = [r["name"] for r in
                  _conn.execute("PRAGMA table_info(ordenes)")]
        if "huella" not in cols_o:
            _conn.execute("ALTER TABLE ordenes ADD COLUMN huella TEXT")
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


def huella_evidencia(e) -> str:
    """Digest canónico de una fila de `evidencias`: cubre la captura (vía su
    sha256) y todos los campos probatorios. Se referencia en la actuación
    'evidencia' para que la cadena cubra también la evidencia."""
    return hashlib.sha256("|".join(str(e[k]) for k in (
        "expediente_id", "deteccion_id", "minuto", "stream_url",
        "captura_sha256", "marca_extraida", "marca_valida", "dominios_en_ip",
        "promocion", "riesgo_colateral_detectado")).encode()).hexdigest()


def huella_orden(o) -> str:
    """Digest canónico de una fila de `ordenes`: cubre firma, juez firmante,
    objetivo y plazo. Se referencia en la actuación 'firma_orden'/'despacho'."""
    return hashlib.sha256("|".join(str(o[k]) for k in (
        "orden_id", "expediente_id", "proveedor_id", "tipo", "objetivo",
        "vence_min", "juzgado_id", "juez_id", "firma")).encode()).hexdigest()


def actuacion(expediente_id, tipo: str, detalle: str, minuto: float) -> str:
    """Append-only: cada actuación encadena el hash de la anterior del expediente.

    expediente_id=None usa la cadena 'SISTEMA' (eventos de plataforma).
    hash = sha256(hash_prev | expediente_id | n | tipo | detalle | minuto |
                  timestamp_iso) — cubre también el timestamp y el propio
    número de foja, así reordenar o retocar metadatos rompe la cadena.
    """
    with _lock, conectar() as c:
        prev = c.execute(
            "SELECT n, hash_actual FROM actuaciones WHERE expediente_id IS ? "
            "ORDER BY n DESC LIMIT 1", (expediente_id,)).fetchone()
        n = (prev["n"] + 1) if prev else 1
        hprev = prev["hash_actual"] if prev else "GENESIS"
        ts = iso()
        clave = expediente_id or "SISTEMA"
        h = hashlib.sha256(
            f"{hprev}|{clave}|{n}|{tipo}|{detalle}|{minuto}|{ts}"
            .encode()).hexdigest()
        c.execute(
            "INSERT INTO actuaciones(expediente_id,n,tipo,detalle,minuto,timestamp_iso,"
            "hash_prev,hash_actual) VALUES(?,?,?,?,?,?,?,?)",
            (expediente_id, n, tipo, detalle, minuto, ts, hprev, h))
        return h
