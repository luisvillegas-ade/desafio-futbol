# Desafío Fútbol — Estado técnico del proyecto (handoff de sesión)

**Hackathon Argentina Space 2026 · Track Datos y Streaming · Salta**
Partido final: **viernes 13**. Plan maestro: `PLAN.md`. Este archivo es la
bitácora técnica: qué está hecho, qué se verificó, y las trampas del simulador
ya descubiertas. Leer esto ANTES de tocar código.

---

## 1. Estado actual (post-correcciones de auditoría, vie 13)

| Componente | Estado |
|---|---|
| Motor completo (`plataforma/`) | ✅ Hecho y verificado |
| Detecciones → expediente → firma → 4 ISPs → vencimiento | ✅ 7/7 fases, residual 7.3 % (interactivo + demo reclamos) |
| Daño colateral / falsos positivos / fuera de turno / IP post-partido | ✅ **0** en todo |
| **Firma personal del juez (regla de la org)** | ✅ `aprobada_por`: firma solo quien clickeó y sigue de turno; si no, el expediente se re-eleva al entrante y espera su clic |
| **Reclamos a la bandeja del juez** | ✅ quedan `elevado` + botón "hacer lugar": el juez firma el levantamiento con SU clave + reemplazo por dominio |
| Reintentos Cumbre (35 % falla) | ✅ `orden_id` único `ord-<n>-<pid>-rep<m>-r<i>` (antes colisionaban → 409) |
| Buffer de cambio de turno (min 50) | ✅ verificado + re-elevación determinística en el borde |
| Dispatcher sin timeout real | ✅ espera estado terminal o cierre del sim (era `ev.wait(30)`, mataba workers a x6/x1) |
| `dominio_base()` con TLDs compuestos | ✅ `.com.ar`/`.org.ar`/`.gob.ar`/`.co.uk` (antes colateral masivo) |
| Bandeja aislada por turno + roles | ✅ juez fuera de turno = solo lectura; operador no ve "archivar"; anti doble-clic; reclamos en hilo propio (no bloquean poller) |
| **Cadena de custodia ampliada** | ✅ hash cubre `timestamp_iso`+`expediente_id`+`n`; huella SHA-256 por evidencia y por orden citada en cadena; `verificar_cadena.py` las recomputa + chequea cobertura. Tamper test: detecta captura/timestamp/juez alterados |
| **Cierre de circuito** | ✅ `hilo_cierre`: actuación `vencimiento` + `cerrado`/`archivo`/`cerrado_min` a fin+5 de gracia |
| Detalle peritaje + evidencia + badge | ✅ "por qué esta medida" en humano, `captura_meta` (formato/duración/página), promo con URL completa, sello `✓ cadena íntegra` |
| Bandeja ágil (velocidad) | ✅ beep + banner + atajo `A` cuando hay pendientes de firma |
| Race condition `expedientes.id` entre workers | ✅ fix: `db.bloqueo()` en `obtener_o_crear` |
| README + propuesta normativa (7 puntos) | ✅ actualizados (interactivo = partido final; auto = solo pruebas internas) |
| Video ≤ 3 min | ⬜ Pendiente (guion: `GRABAR-VIDEO.md`) |
| Repo público propio + push | ⬜ Pendiente |

---

## 2. Cómo correr

```bash
# Terminal 1 — simulador (OBLIGATORIO PYTHONUTF8 en Windows: el print de
# arranque usa '≈' y rompe con cp1252)
set PYTHONUTF8=1
python simulador/servidor.py --escenario datos/escenario_practica.json --acelerar 6

# Terminal 2 — plataforma (desde la carpeta desafio-futbol/)
python -m plataforma.main --modo interactivo --reset   # PARTIDO FINAL: el juez aprueba en la web
python -m plataforma.main --modo auto --reset          # solo pruebas internas
# Consola judicial: http://127.0.0.1:8090 — clave 'demo' para todos:
#   jueces laura/martin (firman solo de turno), secretario, operador, admin.
# Público: /transparencia, /reclamar, /monitor

# Terminal 3 — cuando el sim llega a fin_min + 5 de gracia:
python evaluacion/verificar.py --log salida/registro.jsonl
python -m plataforma.auditoria.verificar_cadena        # cadena en DB viva
python -m plataforma.main --exportar                   # escribe entrega/
```

Flags útiles: `--acelerar 60` (partido en ~2 min para iterar), `--inicio-min 45`
(probar el cambio de turno), `--inicio-min 40`, `--sin-ui`, `--exportar`
(exporta `entrega/` y sale), `--servidor URL`.

**Test del circuito interactivo**: `python scripts/juez_click.py --forzar-ip
tv.verpartido-hd.test` (con plataforma en `interactivo`) — hace login como el
juez de turno, aprueba expedientes elevados, hace lugar a reclamos y re-loguea
al entrante en el cambio de turno. `scripts/test_reclamo.py` hace solo el
`forzar-ip` (provoca colateral → reclamos → demo del circuito de levantamiento).
Jugando perfecto el sim **nunca emite reclamos** (ver quirks abajo).

---

## 3. Arquitectura (`plataforma/`, stdlib puro, Python 3.9+)

```
main.py                Orquestador + hilos. Flags: --modo/--servidor/--reset/--sin-ui/--exportar
config.py              Constantes + usuarios demo por rol (juez laura/martin,
                       secretario, operador, admin — clave 'demo'). SERVIDOR
                       default http://127.0.0.1:8080
cliente_sim.py         Cliente HTTP (urllib). Fuerza localhost→127.0.0.1 (ver quirks)
db.py                  SQLite única + lock global + WAL + synchronous=OFF.
                       actuacion(): append-only; hash = sha256(hash_prev|exp_id|
                       n|tipo|detalle|minuto|timestamp_iso). huella_evidencia/
                       huella_orden: sha256 canónico de cada fila probatoria,
                       citado dentro de la cadena (actuación 'evidencia' /
                       'firma_orden'). Columnas nuevas: expedientes.aprobada_por/
                       aprobada_min, evidencias.captura_meta/huella, ordenes.huella.
motor/reloj.py         Cachea /estado y extrapola el minuto entre polls (usa `acelerar`).
motor/turnos.py        esperar_firma_segura(): si falta < MARGEN_TURNO_MIN (0.6)
                       para el fin del turno, duerme hasta el borde y devuelve
                       el juez ENTRANTE. Toda firma pasa por acá (órdenes,
                       reintentos y levantamientos de reclamos).
motor/verificador.py   clasificar(): pirata / licenciatario / descartada.
                       analizar_colateral(): dns-pasivo → ip|dominio.
                       dominio_base(): TLDs compuestos (.com.ar, .co.uk...).
motor/expediente.py    Un expediente por tupla (host_stream, ip_servidor);
                       juez_asignado al crear. agregar_evidencia() guarda
                       captura_meta + huella y asienta actuación 'evidencia'.
motor/poller.py        Thread fetch (/estado,/detecciones,/reclamos cada 0.5 s)
                       + cola + 4 workers en paralelo + lock por tupla.
                       Reclamos van a Thread-Reclamos (no bloquean detecciones).
motor/dispatcher.py    Worker por (expediente, proveedor): firma → POST →
                       espera confirmación SIN timeout real fijo. La firma usa
                       el juez de expedientes.aprobada_por si sigue de turno;
                       si no, re-eleva (estado elevado + juez_asignado nuevo)
                       y espera la aprobación del entrante. Monitor
                       CONSOLIDADO: 4 GET/ciclo, no uno por orden.
motor/reclamos.py      Reclamo → estado 'elevado' en la bandeja del juez de
                       turno (interactivo); resolver() con el juez_id de
                       sesión: firma LEVANTAR + reemplazo por dominio
                       (orden_id 'rep'). En auto resuelve directo.
juez/servidor_ui.py    ThreadingHTTPServer: login por roles (cookie), bandeja
                       con dependencia, detalle con acciones por rol (aprobar/
                       forzar-ip/rechazar/pase/revision/archivar), informe
                       imprimible /exp/<id>/informe. Público: /transparencia,
                       /reclamar, /monitor (+/monitor/datos JSON live).
juez/templates.py      HTML server-side (dark, autorefresh 4 s) + informe judicial.
juez/monitor.py        Tablero TUI bento en vivo (grafo orquestador→agentes→ISPs).
auditoria/exportar.py  entrega/expediente-ejemplo.json + registro-auditoria.json
datos_app/plataforma.db  SSOT (se crea sola; --reset la borra)
```

Modos: `interactivo` (default, partido final) = queda `elevado` hasta que el
juez de turno apruebe en la web — la firma solo puede hacerla quien clickeó.
`auto` = firma inmediata tras peritaje, SOLO para pruebas internas (la "orden
marco" es el punto 1 de la propuesta normativa, no un atajo del MVP).
`hilo_cierre` (main.py): al llegar a fin+5 de gracia asienta 'vencimiento' en
cada expediente y los pasa a cerrado/archivo/cerrado_min.

---

## 4. Quirks del simulador YA VERIFICADOS (no redescubrir)

1. **`localhost` en Windows = ~2 s por request.** El sim bindea `0.0.0.0` (IPv4);
   `localhost` resuelve ::1 primero y el connect espera timeout. `ClienteSim`
   reescribe a `127.0.0.1`. Este fue el bug que producía lag de 20+ min.
2. **`juez_de_turno` se evalúa cuando el proveedor RECIBE la orden**, no al
   firmarla. El buffer de `turnos.py` cubre la latencia del POST.
3. **Cursor de reclamos**: `/reclamos` devuelve `minuto_actual` redondeado a 2
   decimales → puede saltar reclamos. Cursor = `max(r.minuto)` vistos + dedup
   por `id`. En detecciones sí se usa `minuto_actual` (contrato de la API).
4. **`vence_min` debe ser entero y > minuto actual.** Reintentos con
   `ahora >= fin_min` se cortan (serían 422 y además no suman cobertura).
5. **`orden_id` único por proveedor** → `ord-<exp_num>-<pid>-r<intento>`.
6. **El objeto reclamo del API NO trae `orden_id`** → se ubica la orden activa
   del proveedor cuyo objetivo afecta al dominio (`dns_pasivo` para tipo ip).
7. **Los reclamos solo nacen de NUESTRO daño colateral.** Si nunca bloqueamos
   legítimos, el feed de reclamos queda vacío. Para el video hay que provocar
   uno con "forzar IP" (test_reclamo.py).
8. **`verificar.py` no exige el tipo recomendado**: un bloqueo por dominio
   cuenta igual para la fase y jamás genera colateral → ante duda (DNS 404),
   dominio. Igual elegimos `ip` en IPs dedicadas porque es la narrativa correcta.
9. **Trampa probable del escenario final**: marca de licenciatario
   (`LP26-PRA-LIC-*`) en dominio NO autorizado = pirata (retransmisión ilegal).
   `verificador.clasificar` ya lo cubre: autorizado solo si el host es el
   dominio declarado o subdominio de él.
10. **"Dominio ajeno"** = distinto dominio registrable (últimas 2 etiquetas):
    `espejo.pelotaya.test` comparte base con el stream → mismo operador →
    bloqueo por IP correcto.
11. El sim corre `avanzar()` cada 0.1 s con lock global; monitor consolidado
    (4 req/ciclo) evita saturar — el polling por orden saturaba el pipeline.
12. **SIMS ZOMBIE EN EL MISMO PUERTO**: Windows permite que varios simuladores
    bindeen `0.0.0.0:8080` a la vez y las respuestas se reparten entre ellos.
    Un sim viejo `finalizado` responde `minuto_actual` ~1700 → `de_turno` da
    None → los workers esperan firma para siempre → 0 órdenes, `en_ejecucion`
    muda. Síntoma: 0/7 fases con `ordenes recibidas: 0`. Antes de cada corrida:
    `netstat -ano | grep ":8080" | grep LISTEN` debe dar UN solo PID.
    `demo.py` ya detecta puerto ocupado y ofrece frenarlo. Además el motor ahora
    es resiliente: `esperar_firma_segura` devuelve None pasado el último turno
    y el worker asienta "sin juez de turno" en vez de colgar.
12. **Race `expedientes.id` (vie 13, arreglado):** dos workers de tuplas
    distintas podían hacer `COUNT(*)+1` a la vez → mismo id → `UNIQUE
    constraint failed` y la detección se perdía (se recuperaba con la
    siguiente detección del stream, pero era riesgo latente). Fix:
    `db.bloqueo()` (contextmanager sobre el RLock global) envolviendo
    todo `obtener_o_crear`. Verificado: 20 creates concurrentes → 20 ids
    únicos, 0 errores.

---

## 5. Resultados de corridas verificadas

**×60 desde min 0, modo INTERACTIVO + juez_click --forzar-ip (vie 13, post-auditoría):**
```
fases_piratas_bloqueadas: 7 de 7     visibilidad_residual: 7.3 %
primer bloqueo por fase: 0.6–7.2 min   clientes cubiertos: 100 % todas
colateral/falsos_positivos/rechazos/fuera_de_turno/ip_post_partido: 0
ordenes: 33 recibidas / 31 aplicadas / 2 fallidas (Cumbre, reintentos rep OK)
reclamos: 3/3 elevados a bandeja → "hacer lugar" del juez → levantados <1 min
cadena de custodia: INTEGRIDAD OK — 180 actuaciones, 38 evidencias, 33 órdenes
expedientes: los 7 → cerrado/archivo/cerrado_min=110.015 (vencimiento asentado)
```

**Smoke interactivo + reclamos (vie 13, post-fix race):** modo `interactivo`
+ `test_reclamo.py` → forzar-ip sobre `tv.verpartido-hd.test` → 3 reclamos de
`panaderia-la-espiga.test` → las 3 órdenes IP levantadas firmadas (0.1–0.5 min)
y reemplazadas por `dominio`. `verificar.py`: `reclamos 3 / resueltos 3`.
El colateral resultante (3 bloqueos / 4 dominios legítimos) es deliberado:
es la demo del módulo de reclamos, no un defecto.

**×30 con `--inicio-min 40` (ensayo de cambio de turno):**
```
fases_piratas_bloqueadas: 6 de 7     visibilidad_residual: 30.1 %
```
El "6/7" es estructural del flag, NO un bug: `pelotaya fase 1` corre min 2–36
y el sim arranca en 40 — la fase ya estaba cerrada. Ojo: el sim SÍ emite
detecciones tardías de fases vencidas (EXP-3 se creó y despachó igual);
`verificar.py` solo cuenta bloqueos dentro de la ventana de la fase. Todo lo
controlable quedó en cero y el cambio de turno (min 50) anduvo perfecto:
órdenes <50 firma Laura, >50 firma Martín. En el partido final (min 0) no aplica.

---

## 6. Pendiente (Hito 4, viernes 13)

- [ ] **Video ≤ 3 min**: corrida de práctica en interactivo. Guión:
      `GRABAR-VIDEO.md` — login laura, aprobación 1 clic, Cumbre reintenta,
      cambio de turno min 50, forzar-ip → reclamo → "hacer lugar" firmado,
      verificar.py + verificar_cadena.py.
- [ ] **Repo público propio**: `git fetch` de origin (qualydata-org) ya hecho;
      crear repo público bajo la cuenta del participante y pushear; NO pushear
      al repo de la organización.
- [x] Regenerar `entrega/expediente-ejemplo.json` + `registro-auditoria.json`
      (`--exportar` tras la corrida 7/7 interactiva del vie 13 — nueva cadena).
- [x] README: modo interactivo como partido final + archivos propios documentados.
- [x] Propuesta normativa: 7 puntos (agregados transparencia/custodia y turno
      judicial; plazos alineados a los 5 min de gracia del sim).
- [ ] Commits periódicos + congelar al cierre (viernes 13:00).

## 7. Decisiones de diseño ya tomadas (no reabrir sin motivo)

- Cero dependencias externas (stdlib) — portabilidad garantizada día 3.
- SQLite única con lock global (carga baja, cero problemas de concurrencia).
- Dispatcher con un thread por (expediente, proveedor) + monitor consolidado.
- **Interactivo = modo del partido final** (regla de la org: el juez inicia
  sesión y aprueba; nadie firma en su nombre). `auto` queda para pruebas
  internas; la "orden marco" vive en la propuesta normativa (punto 1).
- Firma ligada al clic: `expedientes.aprobada_por`; si el aprobante sale de
  turno antes de despachar, el expediente se re-eleva al entrante.
- Estructura de archivos como en PLAN.md §3; `plataforma/datos_app/juzgados_local.json`
  no se duplicó: se lee `datos/juzgados.json` directo (las claves finales son
  las mismas según README del desafío).
