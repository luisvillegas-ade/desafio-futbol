"""Genera entrega/validacion/ con la salida textual de los verificadores.

Nada se edita a mano: cada archivo es la salida (stdout) de los verificadores
sobre la corrida recién exportada con `python -m plataforma.main --exportar`.

Uso (desde desafio-futbol/, tras la corrida + --exportar):
    python scripts/validar_entrega.py --acelerar 6 \
        --comando "python -m plataforma.main --modo interactivo --reset"
    python scripts/validar_entrega.py --acelerar 6 --combinado vercel.txt ...

Escribe verificar.txt (evaluacion/verificar.py sobre salida/registro.jsonl),
verificar-cadena.txt (verificador de cadena sobre entrega/registro-auditoria.json)
y nota.md (comando, aceleración, fecha). Con --combinado escribe un único
archivo con las dos salidas más la nota.
"""
import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
DESTINO = BASE / "entrega" / "validacion"


def correr(*args) -> str:
    env = dict(os.environ, PYTHONUTF8="1")
    r = subprocess.run([sys.executable, *args], cwd=BASE, env=env,
                       capture_output=True, text=True, encoding="utf-8")
    return f"$ python {' '.join(args)}\n{r.stdout}{r.stderr}(exit {r.returncode})\n"


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--log", default="salida/registro.jsonl")
    p.add_argument("--registro", default="entrega/registro-auditoria.json")
    p.add_argument("--acelerar", required=True)
    p.add_argument("--comando", required=True,
                   help="comando de la plataforma usado en la corrida")
    p.add_argument("--extra", default="",
                   help="otros detalles de la corrida (juez, sim, URL)")
    p.add_argument("--combinado", help="nombre de archivo único de salida")
    a = p.parse_args()

    verif = correr("evaluacion/verificar.py", "--log", a.log)
    cadena = correr("-m", "plataforma.auditoria.verificar_cadena", a.registro)
    nota = (f"# Validación de la corrida exportada\n\n"
            f"- Generado: {datetime.now().isoformat(timespec='seconds')} "
            f"por `scripts/validar_entrega.py`\n"
            f"- Simulador: `python simulador/servidor.py --escenario "
            f"datos/escenario_practica.json --acelerar {a.acelerar}`\n"
            f"- Plataforma: `{a.comando}`\n"
            f"- Export: `python -m plataforma.main --exportar`\n"
            + (f"- {a.extra}\n" if a.extra else ""))
    DESTINO.mkdir(parents=True, exist_ok=True)
    if a.combinado:
        (DESTINO / a.combinado).write_text(
            nota + "\n" + verif + "\n" + cadena, encoding="utf-8")
        print(f"  entrega/validacion/{a.combinado}")
    else:
        (DESTINO / "verificar.txt").write_text(verif, encoding="utf-8")
        (DESTINO / "verificar-cadena.txt").write_text(cadena, encoding="utf-8")
        (DESTINO / "nota.md").write_text(nota, encoding="utf-8")
        print("  entrega/validacion/{verificar.txt,verificar-cadena.txt,nota.md}")
    print(verif)
    print(cadena)


if __name__ == "__main__":
    main()
