"""Exporta a entrega/: un expediente completo y el registro de auditoría.

Uso:  python -m plataforma.auditoria.exportar
"""
import json

from .. import config, db


def exportar() -> None:
    config.ENTREGA_DIR.mkdir(parents=True, exist_ok=True)

    exp = db.q1(
        "SELECT e.*, COUNT(o.id) n_ord FROM expedientes e "
        "LEFT JOIN ordenes o ON o.expediente_id=e.id "
        "GROUP BY e.id ORDER BY n_ord DESC, e.creado_min LIMIT 1")
    if exp:
        exp = dict(exp)
        exp.pop("n_ord", None)
        expediente_json = {
            "expediente": exp,
            "evidencias": [dict(x) for x in db.q(
                "SELECT * FROM evidencias WHERE expediente_id=?", (exp["id"],))],
            "actuaciones": [dict(x) for x in db.q(
                "SELECT * FROM actuaciones WHERE expediente_id=? ORDER BY n",
                (exp["id"],))],
            "ordenes": [dict(x) for x in db.q(
                "SELECT * FROM ordenes WHERE expediente_id=?", (exp["id"],))],
        }
        (config.ENTREGA_DIR / "expediente-ejemplo.json").write_text(
            json.dumps(expediente_json, ensure_ascii=False, indent=2),
            encoding="utf-8")
        print(f"  entrega/expediente-ejemplo.json  ({exp['id']})")

    registro = {
        "cadena_de_custodia": (
            "hash_actual = sha256(hash_prev|expediente_id|n|tipo|detalle|"
            "minuto|timestamp_iso); cada evidencia y cada orden lleva una "
            "huella SHA-256 canónica citada en la cadena — recomputar con "
            "python -m plataforma.auditoria.verificar_cadena <este archivo>"),
        "actuaciones": [dict(x) for x in db.q(
            "SELECT * FROM actuaciones ORDER BY id")],
        "reclamos": [dict(x) for x in db.q("SELECT * FROM reclamos ORDER BY minuto")],
        "ordenes": [dict(x) for x in db.q("SELECT * FROM ordenes ORDER BY id")],
        "evidencias": [dict(x) for x in db.q("SELECT * FROM evidencias")],
    }
    (config.ENTREGA_DIR / "registro-auditoria.json").write_text(
        json.dumps(registro, ensure_ascii=False, indent=2), encoding="utf-8")
    print("  entrega/registro-auditoria.json")


if __name__ == "__main__":
    exportar()
