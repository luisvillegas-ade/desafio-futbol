# Validación de la corrida exportada

- Generado: 2026-11-12T23:44:29 por `scripts/validar_entrega.py`
- Simulador: `python simulador/servidor.py --escenario datos/escenario_practica.json --acelerar 6`
- Plataforma: `python -m plataforma.main --modo interactivo --reset`
- Export: `python -m plataforma.main --exportar`
- Juez: scripts/juez_click.py --forzar-ip tv.verpartido-hd.test --lote (clics HTTP contra la consola, cookies de sesión reales)
