# Juzgado Digital de Bloqueo en Vivo

**Plataforma judicial para el Desafío Fútbol — Hackathon Argentina Space 2026** · Track Datos y Streaming · Salta, 11 al 13 de noviembre de 2026

Autor: Luis Alberto Villegas ([luisvillegas-ade](https://github.com/luisvillegas-ade)) · Demo en línea: https://desafio-futbol-two.vercel.app · Consigna original de la organización: [CONSIGNA-ORIGINAL.md](CONSIGNA-ORIGINAL.md)

> **Aviso.** Todos los datos de este repositorio son ficticios: proveedores de internet, juzgados, jueces, partidos, dominios e IPs. Los dominios terminan en `.test` o `.example`, las IPs son de documentación (RFC 5737) y los ASN son del rango privado. No se bloquea nada real: todo ocurre dentro del simulador. Este material no es asesoramiento legal.

---

## Nuestra solución

Una plataforma en **Python 3.9+ estándar, cero dependencias externas**, que corre el circuito completo contra el simulador: detección → expediente judicial con evidencia → firma del juez de turno → despacho paralelo a los 4 proveedores → confirmación → vencimiento automático, más el módulo de reclamos (levantamiento firmado + reemplazo por dominio) y un portal público de transparencia.

**Por qué stdlib puro:** el partido final corre en una máquina que no conocemos; sin `pip install` no hay nada que pueda fallar. Todo el código de la plataforma está en `plataforma/` y fue escrito durante el hackathon; `simulador/`, `datos/`, `evaluacion/` y `ejemplos/` son el material provisto por la organización.

### Cómo correr

**Camino fácil (recomendado):** doble click en `JUGAR.bat`, o un solo comando:

```powershell
python demo.py                  # interactivo (usted es el juez) a x6 (~17 min)
python demo.py --acelerar 60    # ~2 min, para iterar
python demo.py --modo auto      # solo para pruebas internas (ver nota abajo)
```

`demo.py` arranca simulador + plataforma, abre el navegador en la consola
judicial y, al terminar el partido (más los 5 min de gracia), corre
`verificar.py` y muestra el puntaje. Si los puertos 8080/8090 están ocupados
por corridas viejas, pregunta si los frena. `JUGAR.bat` es el atajo de
doble click: misma función, acepta los mismos flags (`JUGAR.bat --acelerar 60`).

**Modo de ejecución:** `--modo interactivo` es el modo por defecto y el del
partido final: el juez inicia sesión y **aprueba con un clic** cada orden —
nadie firma en su nombre (regla del enunciado). `--modo auto` queda como
herramienta de pruebas internas: firma sin intervención humana bajo la
narrativa de "orden marco" de la propuesta normativa.

**Manual** (tres terminales):

```powershell
# Terminal 1 — simulador (Windows: PYTHONUTF8=1, el print usa '≈')
$env:PYTHONUTF8=1; python simulador/servidor.py --escenario datos/escenario_practica.json --acelerar 6

# Terminal 2 — plataforma (desde la raíz del repo)
python -m plataforma.main --modo interactivo --reset   # el juez aprueba cada orden en la web
python -m plataforma.main --modo interactivo --reset --servidor http://<ip>:8080   # partido final

# Consola judicial: http://127.0.0.1:8090  (clave demo para todos)
#   Jueces:     laura / martin   (firman solo estando de turno)
#   Secretaría: secretario       (pases, devolución a pericia, archivo)
#   Fiscalía:   operador         (pases, revisión, informes)
#   Admin:      admin            (visión completa del sistema)
# Monitor en vivo:  http://127.0.0.1:8090/monitor        (público)
# Transparencia:    http://127.0.0.1:8090/transparencia  (público)
# Reclamos web:     http://127.0.0.1:8090/reclamar       (público)

# Terminal 3 — cuando el partido termina (+5 min de gracia)
python evaluacion/verificar.py --log salida/registro.jsonl

# Cadena de custodia (verificable sin confiar en la plataforma):
python -m plataforma.auditoria.verificar_cadena                          # DB viva
python -m plataforma.auditoria.verificar_cadena entrega/registro-auditoria.json

# Exportar los entregables del día 3
python -m plataforma.main --exportar   # escribe entrega/expediente-ejemplo.json y registro-auditoria.json
```

**Pruebas automatizadas del circuito interactivo** (no hace falta clickear a
mano para iterar): `python scripts/juez_click.py --forzar-ip tv.verpartido-hd.test`
hace login como el juez de turno, aprueba los expedientes elevados, hace lugar
a los reclamos de la bandeja y re-loguea al juez entrante en el cambio de turno.
`scripts/test_reclamo.py` hace solo el paso de `forzar-ip` sobre el expediente
de IP compartida para provocar los reclamos de la demo.

Flags de la plataforma: `--modo auto|interactivo` · `--servidor URL` · `--reset` (borra la BD) · `--sin-ui` · `--exportar` · `--puerto-ui`.

Flags útiles del simulador: `--acelerar 60` (partido en ~2 min para iterar) · `--inicio-min 40` (probar el cambio de turno judicial del minuto 50).

### En línea (vidriera opcional)

Consola judicial, portal de transparencia, monitor y SICRE desplegados en Vercel con base Neon/Postgres (São Paulo): **https://desafio-futbol-two.vercel.app** (jueces de demo `laura` / `martin`; la clave se entrega aparte).

```
celular del juez ──► Vercel (FastAPI, solo registra la decisión en Neon/Postgres)
                                      │  el motor local la lee, firma y despacha
simulador (LAN)  ◄── motor local (plataforma/, stdlib) ◄──┘  con DATABASE_URL=postgres://...
```

La web **solo registra decisiones**: quien firma y despacha al simulador es siempre el motor local (`plataforma/motor/decisiones_web.py`, leído por el hilo de reclamos). Sin `DATABASE_URL` nada de esto se activa: **el partido oficial corre 100 % local con SQLite**, tal como está verificado arriba. `requirements.txt` (fastapi/uvicorn/psycopg) es solo para `plataforma/api/`; el motor sigue sin dependencias.

### Qué hace (pipeline)

1. **Detección y verificación pericial** (`motor/verificador.py`): polling de `/detecciones` con cursor persistente; contrasta la marca de agua contra `/partido`, excluye licenciatarios en sus dominios autorizados (marca `LIC` en dominio ajeno = pirata retransmitiendo) y consulta `/dns-pasivo` para medir el riesgo colateral de cada IP.
2. **Expediente digital** (`motor/expediente.py` + `db.py`): un expediente por tupla `(host_stream, ip_servidor)`; un cambio de IP/host abre una ampliación cautelar (fase nueva del mismo stream). Cada actuación se numera y encadena con hash SHA-256 (cadena de custodia, append-only).
3. **Regla IP vs. dominio:** si la IP aloja dominios ajenos al infractor (CDN/hosting compartido) → orden por `dominio`; si es dedicada → orden por `ip`. Si el DNS pasivo no responde, se elige `dominio` (nunca genera daño colateral).
4. **Firma judicial con turnos** (`motor/turnos.py`): si falta menos de ~0.6 min para el fin del turno (cambio en el minuto 50), la firma espera al borde y la orden sale firmada por el juez entrante — cero órdenes fuera de turno.
5. **Despacho paralelo y reintentos** (`motor/dispatcher.py`): un worker por `(expediente, proveedor)`; monitor consolidado (4 consultas por ciclo, no una por orden). FibraValle solo acepta `dominio` — se traduce la orden para ese proveedor. Las fallas de Cumbre (~35 %) se reintentan con `orden_id` nuevo (`ord-<exp>-<prov>-rep<n>-r<i>`) y firma recalculada con el juez que aprobó si sigue de turno; si no, el expediente se re-eleva al entrante. La espera de confirmación no tiene timeout real fijo: aguanta hasta el estado terminal o el cierre del simulador.
6. **Reclamos** (`motor/reclamos.py`): polling de `/reclamos` en hilo propio (no bloquea el feed de detecciones). Ubica la orden activa que afecta al dominio reclamado y, en modo interactivo, **la eleva a la bandeja del juez de turno**: con un clic ("hacer lugar") el juez firma el levantamiento y la plataforma despacha el reemplazo por `dominio` más preciso.
7. **Consola judicial por roles** (`juez/`): el expediente circula por dependencias `pericia → secretaría → juzgado → despacho → archivo` y cada pase queda asentado como actuación `pase` en la cadena de custodia. El juez firma solo estando de turno y la firma queda ligada a **su** clic (`aprobada_por`): si aprobó cerca del borde del turno, el expediente se re-eleva al juez entrante y espera su aprobación — nadie firma en nombre de otro. Secretaría y fiscalía hacen pases, devuelven a revisión técnica y archivan; el admin ve todo. Botones: aprobar / forzar-IP / rechazar / **iniciar revisión** (re-peritaje en vivo) / archivar / **emitir informe** imprimible (`/exp/<id>/informe`). La bandeja avisa con alerta sonora, banner y el atajo `A` cuando hay actuaciones esperando firma. Superficies públicas: `/transparencia`, `/reclamar` (procedimiento sumario digital) y `/monitor` (tablero en vivo).

### Resultados en el escenario de práctica

`verificar.py` sobre la última corrida completa **en modo interactivo**
(desde minuto 0, aceleración ×6, el juez firma desde la consola web —
`scripts/juez_click.py --lote`, con «Aprobar todo» — incluyendo la demo de
reclamos con `forzar-ip` sobre la IP compartida). Salidas textuales
completas en `entrega/validacion/`:

```
fases piratas bloqueadas: 7 de 7      visibilidad residual: 3,2 %
falsos positivos / rechazos / órdenes fuera de turno: 0
reclamos (provocados para la demo): 3/3 resueltos por levantamiento
colateral de la demo: 3 bloqueos IP sobre 4 sitios legítimos, todos levantados
cadena de custodia: ÍNTEGRA (180 actuaciones, 38 evidencias, 33 órdenes)
```

Comparación con el cliente de referencia de la organización
(`ejemplos/cliente_minimo.py`), mismo escenario y mismo evaluador:

| | Cliente de ejemplo (org) | Esta plataforma |
|---|---|---|
| Fases piratas bloqueadas | 1 de 7 | **7 de 7** |
| Visibilidad residual promedio | 86,6 % | **3,2 %** |
| Firma | sin juez | juez de turno, desde la consola |
| Órdenes fuera de turno / falsos positivos | — | 0 / 0 |

### Supuestos y decisiones de diseño

- **SQLite como SSOT por defecto** (`plataforma/datos_app/plataforma.db`) con un lock global: la carga es baja y elimina cualquier problema de concurrencia. Con `DATABASE_URL=postgres://...` el mismo `db.py` usa Postgres (Neon) para la vidriera en línea; la foliación de actuaciones es atómica en ambos backends y los hashes son idénticos.
- **`vence_min` entero = `fin_min` del partido**: los bloqueos por IP vencen solos al terminar (propuesta normativa, punto 4). Al vencer la ventana (fin + 5 min de gracia) la plataforma asienta la actuación `vencimiento` en cada expediente y los pasa a `cerrado`/`archivo`.
- **Firma judicial personal**: en `modo interactivo` la orden solo se firma con la clave del juez que hizo clic aprobando, y solo si sigue de turno con margen seguro; de lo contrario se re-eleva al entrante. `modo auto` queda para pruebas internas (la "orden marco" es un punto de la propuesta normativa, no un atajo del MVP).
- Las claves de firma se leen de `datos/juzgados.json` (las del material del desafío; no hay secretos reales en el repo).
- **`dominio_base()` maneja TLDs compuestos** (`.com.ar`, `.org.ar`, `.gob.ar`, `.co.uk`): `panaderia.com.ar` y `pirata.com.ar` no se confunden como mismo operador — sin esto, un CDN argentino generaría daño colateral masivo.

### Entregables y archivos propios

Código escrito durante el hackathon (todo stdlib):

- `plataforma/` — el sistema completo (motor, consola judicial, auditoría).
- `demo.py` + `JUGAR.bat` — lanzador todo-en-uno (sim + plataforma + navegador + puntaje).
- `scripts/juez_click.py`, `scripts/test_reclamo.py` — pruebas automatizadas del circuito interactivo y de reclamos.
- `GRABAR-VIDEO.md` — guion paso a paso del video ≤ 3 min.
- `AGENTS.md` — bitácora técnica completa (quirks del simulador verificados, arquitectura, resultados).
- `plataforma/api/` + `api/index.py` + `vercel.json` + `requirements.txt` — capa web opcional (FastAPI) para Vercel/Neon; `PLAN-VERCEL.md` es su plan. El motor no la importa.

Entregables del día 3:

- `entrega/propuesta-normativa.md` — 1 página, 7 puntos.
- `entrega/expediente-ejemplo.json` y `entrega/registro-auditoria.json` — exportados de una corrida real con `--exportar`.

---

---

La consigna completa del desafío, tal como la publicó la organización, está en [CONSIGNA-ORIGINAL.md](CONSIGNA-ORIGINAL.md).
