"""Verificador independiente de la cadena de custodia.

Recalcula cada hash encadenado sin confiar en la plataforma:
    hash_actual = sha256(hash_prev | tipo | detalle | minuto)
La primera actuación de cada expediente usa hash_prev = "GENESIS".

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
    h = f"{act['hash_prev']}|{act['tipo']}|{act['detalle']}|{act['minuto']}"
    return hashlib.sha256(h.encode()).hexdigest()


def verificar(actuaciones):
    """Devuelve (ok, errores) agrupando por expediente y ordenando por n."""
    cadenas = {}
    for a in actuaciones:
        cadenas.setdefault(a["expediente_id"] or "SISTEMA", []).append(a)
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
    return not errores, errores


def desde_db():
    from .. import db
    return [dict(a) for a in db.q(
        "SELECT expediente_id,n,tipo,detalle,minuto,hash_prev,hash_actual "
        "FROM actuaciones ORDER BY id")]


def desde_json(ruta):
    reg = json.load(open(ruta, encoding="utf-8"))
    return reg["actuaciones"]


def main():
    if len(sys.argv) > 1:
        actuaciones = desde_json(sys.argv[1])
        origen = sys.argv[1]
    else:
        actuaciones = desde_db()
        origen = "base de datos"
    ok, errores = verificar(actuaciones)
    n = len(actuaciones)
    if ok:
        print(f"INTEGRIDAD OK — {n} actuacion(es) verificadas en {origen}")
        print("toda alteración posterior a una actuación rompería la cadena")
        sys.exit(0)
    print(f"ALTERACION DETECTADA — {len(errores)} inconsistencia(s) en {origen}:")
    for exp_id, nro, msg in errores:
        print(f"  {exp_id} actuación nº{nro}: {msg}")
    sys.exit(1)


if __name__ == "__main__":
    main()
