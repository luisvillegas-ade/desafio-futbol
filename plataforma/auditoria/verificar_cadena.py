"""Verificador independiente de la cadena de custodia.

Recalcula cada hash encadenado sin confiar en la plataforma:
    hash_actual = sha256(hash_prev | expediente_id | n | tipo | detalle |
                         minuto | timestamp_iso)
La primera actuación de cada expediente usa hash_prev = "GENESIS".

Además verifica la evidencia referenciada: cada fila de `evidencias` y cada
fila de `ordenes` lleva una `huella` SHA-256 canónica que debe (a) recomputar
igual sobre sus campos y (b) aparecer referenciada en una actuación de la
cadena ('evidencia' para evidencias, 'firma_orden'/'despacho' para órdenes).
Alterar una captura, un dominio DNS, la firma o el juez de una orden cambia la
huella recomputada y delata la manipulación.

Uso:
    python -m plataforma.auditoria.verificar_cadena             # sobre la DB viva
    python -m plataforma.auditoria.verificar_cadena entrega/registro-auditoria.json

Exit 0 = íntegro · Exit 1 = alteración detectada.
"""
import hashlib
import json
import sys

GENESIS = "GENESIS"


def cadena_esperada(act):
    clave = act.get("expediente_id") or "SISTEMA"
    h = (f"{act['hash_prev']}|{clave}|{act['n']}|{act['tipo']}|{act['detalle']}"
         f"|{act['minuto']}|{act['timestamp_iso']}")
    return hashlib.sha256(h.encode()).hexdigest()


def huella_evidencia(e) -> str:
    return hashlib.sha256("|".join(str(e[k]) for k in (
        "expediente_id", "deteccion_id", "minuto", "stream_url",
        "captura_sha256", "marca_extraida", "marca_valida", "dominios_en_ip",
        "promocion", "riesgo_colateral_detectado")).encode()).hexdigest()


def huella_orden(o) -> str:
    return hashlib.sha256("|".join(str(o[k]) for k in (
        "orden_id", "expediente_id", "proveedor_id", "tipo", "objetivo",
        "vence_min", "juzgado_id", "juez_id", "firma")).encode()).hexdigest()


def verificar(actuaciones, evidencias=(), ordenes=()):
    """Devuelve (ok, errores): chequea la cadena por expediente, las huellas
    almacenadas y que cada evidencia/orden quede cubierta por una actuación."""
    cadenas = {}
    for a in actuaciones:
        cadenas.setdefault(a.get("expediente_id") or "SISTEMA", []).append(a)
    errores = []
    for exp_id, acts in cadenas.items():
        acts.sort(key=lambda a: a["n"])
        prev = GENESIS
        for a in acts:
            if a["hash_prev"] != prev:
                errores.append((exp_id, a["n"],
                                f"hash_prev no encadena (dice {a['hash_prev'][:14]}… "
                                f"esperaba {prev[:14]}…)"))
            esperado = cadena_esperada(a)
            if a["hash_actual"] != esperado:
                errores.append((exp_id, a["n"],
                                f"hash_actual alterado (dice {a['hash_actual'][:14]}… "
                                f"recalculado {esperado[:14]}…)"))
            prev = a["hash_actual"]

    # cobertura probatoria: huellas recomputadas vs. almacenadas y citadas
    textos = {}
    for a in actuaciones:
        clave = a.get("expediente_id") or "SISTEMA"
        textos[clave] = textos.get(clave, "") + "\n" + a["detalle"]
    for e in evidencias:
        exp_id = e.get("expediente_id") or "SISTEMA"
        hu = huella_evidencia(e)
        if e.get("huella") and e["huella"] != hu:
            errores.append((exp_id, "—", f"evidencia {e['deteccion_id']}: "
                            f"huella almacenada no recomputa (fila alterada)"))
        if hu[:24] not in textos.get(exp_id, ""):
            errores.append((exp_id, "—", f"evidencia {e['deteccion_id']} sin "
                            "actuación 'evidencia' que la cubra"))
    for o in ordenes:
        exp_id = o.get("expediente_id") or "SISTEMA"
        hu = huella_orden(o)
        if o.get("huella") and o["huella"] != hu:
            errores.append((exp_id, "—", f"orden {o['orden_id']}: huella "
                            "almacenada no recomputa (fila alterada)"))
        if hu[:24] not in textos.get(exp_id, ""):
            errores.append((exp_id, "—", f"orden {o['orden_id']} sin "
                            "actuación que cubra su huella"))
    return not errores, errores


def desde_db():
    from .. import db
    acts = [dict(a) for a in db.q(
        "SELECT expediente_id,n,tipo,detalle,minuto,timestamp_iso,hash_prev,"
        "hash_actual FROM actuaciones ORDER BY id")]
    evs = [dict(e) for e in db.q("SELECT * FROM evidencias")]
    ords = [dict(o) for o in db.q("SELECT * FROM ordenes")]
    return acts, evs, ords


def desde_json(ruta):
    reg = json.load(open(ruta, encoding="utf-8"))
    return (reg["actuaciones"], reg.get("evidencias", []),
            reg.get("ordenes", []))


def main():
    if len(sys.argv) > 1:
        actuaciones, evidencias, ordenes = desde_json(sys.argv[1])
        origen = sys.argv[1]
    else:
        actuaciones, evidencias, ordenes = desde_db()
        origen = "base de datos"
    ok, errores = verificar(actuaciones, evidencias, ordenes)
    n = len(actuaciones)
    if ok:
        print(f"INTEGRIDAD OK — {n} actuacion(es), {len(evidencias)} "
              f"evidencia(s) y {len(ordenes)} orden(es) verificadas en {origen}")
        print("toda alteración posterior a una actuación rompería la cadena")
        sys.exit(0)
    print(f"ALTERACION DETECTADA — {len(errores)} inconsistencia(s) en {origen}:")
    for exp_id, nro, msg in errores:
        print(f"  {exp_id} actuación nº{nro}: {msg}")
    sys.exit(1)


if __name__ == "__main__":
    main()
