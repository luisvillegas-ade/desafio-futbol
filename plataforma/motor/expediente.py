"""Expedientes judiciales: uno por tupla (host_stream, ip_servidor).

Un stream que cambia de IP o de host genera un expediente nuevo (ampliación
cautelar por mudanza de infraestructura, fase_n incremental del mismo stream).
"""
import hashlib
import json

from .. import db
from .verificador import dominio_base


def obtener_o_crear(det: dict, tipo_rec: str, juez_id: str = None):
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
            "asn,tipo_bloqueo_recomendado,estado,dependencia,juez_asignado,"
            "creado_min) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (exp_id, stream_id, fase, det["host_stream"], det["ip_servidor"],
             det.get("asn"), tipo_rec, "detectado", "pericia", juez_id,
             det["minuto"]))
        return dict(db.q1("SELECT * FROM expedientes WHERE id=?", (exp_id,))), True


def agregar_evidencia(exp_id: str, det: dict, dominios_dns, riesgo: bool,
                      marca_valida: bool) -> None:
    cap = det.get("captura") or {}
    b64 = cap.get("contenido_b64", "")
    sha = hashlib.sha256(b64.encode()).hexdigest()
    meta = {"formato": cap.get("formato"),
            "duracion_seg": cap.get("duracion_seg"),
            "capturada_min": cap.get("capturada_min"),
            "pagina": det.get("pagina")}
    promo = json.dumps(det.get("promocion") or [], ensure_ascii=False)
    doms = json.dumps(dominios_dns)
    ev = {"expediente_id": exp_id, "deteccion_id": det["id"],
          "minuto": det["minuto"], "stream_url": det.get("stream_url"),
          "captura_sha256": sha,
          "marca_extraida": det.get("marca_de_agua_extraida") or "",
          "marca_valida": 1 if marca_valida else 0,
          "dominios_en_ip": doms, "promocion": promo,
          "riesgo_colateral_detectado": 1 if riesgo else 0}
    hu = db.huella_evidencia(ev)
    db.ejecutar(
        "INSERT INTO evidencias(expediente_id,deteccion_id,minuto,stream_url,"
        "captura_b64,captura_sha256,marca_extraida,marca_valida,dominios_en_ip,"
        "promocion,riesgo_colateral_detectado,captura_meta,huella) "
        "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (exp_id, det["id"], det["minuto"], det.get("stream_url"), b64, sha,
         ev["marca_extraida"], ev["marca_valida"], doms, promo,
         ev["riesgo_colateral_detectado"],
         json.dumps(meta, ensure_ascii=False), hu))
    db.actuacion(
        exp_id, "evidencia",
        f"Evidencia {det['id']} acreditada y custodiada: captura "
        f"{meta['formato'] or '?'} {meta['duracion_seg'] or '?'} s "
        f"(sha256 {sha[:20]}…), huella {hu[:24]}", det["minuto"])


_DEP_POR_ESTADO = {"elevado": "juzgado", "en_ejecucion": "despacho",
                   "cerrado": "archivo", "archivado": "archivo"}


def set_estado(exp_id: str, estado: str) -> None:
    dep = _DEP_POR_ESTADO.get(estado)
    if dep:
        db.ejecutar("UPDATE expedientes SET estado=?, dependencia=? WHERE id=?",
                    (estado, dep, exp_id))
    else:
        db.ejecutar("UPDATE expedientes SET estado=? WHERE id=?",
                    (estado, exp_id))


def pase(exp_id: str, dependencia: str, actor: str, minuto: float) -> None:
    """Traslada el expediente a otra dependencia (mesa de pases)."""
    prev = db.q1("SELECT dependencia FROM expedientes WHERE id=?", (exp_id,))
    db.ejecutar("UPDATE expedientes SET dependencia=? WHERE id=?",
                (dependencia, exp_id))
    db.actuacion(exp_id, "pase",
                 f"Pase {prev['dependencia'] if prev else '?'} -> {dependencia} "
                 f"por {actor}", minuto)


def tiene_ordenes_activas(exp_id: str) -> bool:
    return bool(db.q1(
        "SELECT 1 x FROM ordenes WHERE expediente_id=? "
        "AND estado IN ('recibida','aplicada') LIMIT 1", (exp_id,)))
