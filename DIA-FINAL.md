# Checklist — viernes 13 (día del partido final)

Cierre de entregas **13:00** (repo propio `luisvillegas-ade/desafio-futbol`,
rama `main`; la org clona a la hora de cierre — lo que se suba después NO
cuenta). Objetivo: tener **todo listo antes de las 10:00** por si los
horarios se alinean con el otro desafío de QualyData.

## Antes del partido

- [ ] **Video ≤ 3 min GRABADO y SUBIDO a Hacki** (la entrega formal es en
      Hacki: link del repo + video). Guión: `GRABAR-VIDEO.md`. Grabar el
      jueves por la noche — es práctica, no el partido final.
- [ ] `netstat -ano | grep ":8080" | grep LISTEN` → **un solo PID**
      (sims zombie = cero órdenes). Igual para `:8090`.
- [ ] `python -m compileall -q plataforma` → sin errores.

## El partido (la org da la URL del simulador)

```powershell
set PYTHONUTF8=1
python -m plataforma.main --modo interactivo --reset --servidor http://<ip-asignada>:8080
```

- [ ] **Modo `interactivo`, nunca `auto`** — regla de la org.
- [ ] Consola `http://127.0.0.1:8090` → login `laura`/`demo` → aprobar cada
      expediente apenas aparezca (atajo `A`). Al min 50 → login `martin`/`demo`.
- [ ] Si aparecen reclamos en la bandeja → "Hacer lugar".
- [ ] Al terminar (fin + 5 min de gracia): `python evaluacion/verificar.py --log salida/registro.jsonl`
- [ ] `python -m plataforma.auditoria.verificar_cadena` → INTEGRIDAD OK.

## Exportar y pushear (antes de las 13:00, ideal 10:00)

```powershell
python -m plataforma.main --exportar          # regenera entrega/*.json DEL PARTIDO FINAL
git add entrega/ && git commit -m "chore: entrega del partido final" && git push origin main
```

- [ ] `entrega/` contiene lo generado en el partido FINAL (no el de práctica).
- [ ] Repo en Hacki cargado (link) + video subido.

## Si algo falla en vivo

| Síntoma | Acción |
|---|---|
| 0 órdenes, expedientes mudos | Sim zombie en :8080 → `netstat` y matar PID extra, o re-apuntar `--servidor` |
| Órdenes "sin juez de turno" | Chequear que el minuto del sim avanza (`curl .../estado`) |
| El juez no ve botones | No está de turno (ver header) o no es rol `juez` |
| Plataforma colgada | `salida/plataforma.log` — relanzar con `--modo interactivo` SIN `--reset` (conserva la DB y la cadena) |
