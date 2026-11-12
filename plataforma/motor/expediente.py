"""Expedientes judiciales: uno por tupla (host_stream, ip_servidor).

Un stream que cambia de IP o de host genera un expediente nuevo (ampliación
cautelar por mudanza de infraestructura, fase_n incremental del mismo stream).
"""
import hashlib
import json

from .. import db
from .verificador import dominio_base


def obtener_o_crear(det: dict, tipo_rec: str):
    with db.bloqueo():
        fila = db.q1(
            "SELECT * FROM expedientes WHERE host_stream=? AND ip_servidor=? "
            "AND estado!='archivado'", (det["host_stream"], det["ip_servidor"]))
        if fila:
            return dict(fila), False
        n = db.q1("SELECT COUNT(*) c FROM expedientes")["c"] + 1
        exp_id = f"EXP-2026-{n:06d}"
        stream_id = dominio_base(det["host_stream"])
        fase = db.q1("SELECT COUNT(*) c FROM expedientes WHERE stream_id=?",
                     (stream_id,))["c"] + 1
        db.ejecutar(
            "INSERT INTO expedientes(id,stream_id,fase_n,host_stream,ip_servidor,"
            "asn,tipo_bloqueo_recomendado,estado,creado_min) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (exp_id, stream_id, fase, det["host_stream"], det["ip_servidor"],
             det.get("asn"), tipo_rec, "detectado", det["minuto"]))
        return dict(db.q1("SELECT * FROM expedientes WHERE id=?", (exp_id,))), True


def agregar_evidencia(exp_id: str, det: dict, dominios_dns, riesgo: bool,
                      marca_valida: bool) -> None:
    cap = det.get("captura") or {}
    b64 = cap.get("contenido_b64", "")
    sha = hashlib.sha256(b64.encode()).hexdigest()
    db.ejecutar(
        "INSERT INTO evidencias(expediente_id,deteccion_id,minuto,stream_url,"
        "captura_b64,captura_sha256,marca_extraida,marca_valida,dominios_en_ip,"
        "riesgo_colateral_detectado) VALUES(?,?,?,?,?,?,?,?,?,?)",
        (exp_id, det["id"], det["minuto"], det.get("stream_url"), b64, sha,
         det.get("marca_de_agua_extraida") or "", 1 if marca_valida else 0,
         json.dumps(dominios_dns), 1 if riesgo else 0))


def set_estado(exp_id: str, estado: str) -> None:
    db.ejecutar("UPDATE expedientes SET estado=? WHERE id=?", (estado, exp_id))


def tiene_ordenes_activas(exp_id: str) -> bool:
    return bool(db.q1(
        "SELECT 1 x FROM ordenes WHERE expediente_id=? "
        "AND estado IN ('recibida','aplicada') LIMIT 1", (exp_id,)))
