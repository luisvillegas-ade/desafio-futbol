# Desafío Fútbol — Estado técnico del proyecto (handoff de sesión)

**Hackathon Argentina Space 2026 · Track Datos y Streaming · Salta**
Partido final: **viernes 13**. Plan maestro: `PLAN.md`. Este archivo es la
bitácora técnica: qué está hecho, qué se verificó, y las trampas del simulador
ya descubiertas. Leer esto ANTES de tocar código.

---

## 1. Estado actual (al cierre del jueves 12)

| Componente | Estado |
|---|---|
| Motor completo (`plataforma/`) | ✅ Hecho y verificado |
| Detecciones → expediente → firma → 4 ISPs → vencimiento | ✅ 7/7 fases, residual **4.7 %** |
| Daño colateral / falsos positivos / fuera de turno / IP post-partido | ✅ **0** en todo |
| Reintentos Cumbre (35 % falla) | ✅ re-firma con juez de turno vigente |
| Buffer de cambio de turno (min 50) | ✅ verificado con `--inicio-min 45` |
| Reclamos (levantar + reemplazo por dominio) | ✅ verificado end-to-end |
| UI juez (login, bandeja, aprobar/forzar-ip/rechazar, /transparencia) | ✅ funcional, estética mínima |
| Cadena de custodia (hash encadenado) + exportador | ✅ `entrega/*.json` regenerados de corrida 7/7 |
| `entrega/propuesta-normativa.md` | ✅ borrador escrito (1 página, 5 puntos) |
| Race condition `expedientes.id` entre workers | ✅ fix: `db.bloqueo()` en `obtener_o_crear` |
| Video ≤ 3 min | ⬜ Pendiente (Hito 4) |
| README de cómo correr (exigencia de entrega) | ⬜ Pendiente — adaptar sección 3 de este archivo |

---

## 2. Cómo correr

```bash
# Terminal 1 — simulador (OBLIGATORIO PYTHONUTF8 en Windows: el print de
# arranque usa '≈' y rompe con cp1252)
set PYTHONUTF8=1
python simulador/servidor.py --escenario datos/escenario_practica.json --acelerar 6

# Terminal 2 — plataforma (desde la carpeta desafio-futbol/)
python -m plataforma.main --modo auto --reset          # auto-firma (orden marco)
python -m plataforma.main --modo interactivo --reset   # el juez aprueba en la web
# Consola judicial: http://127.0.0.1:8090  (usuarios: laura / martin, clave: demo)

# Terminal 3 — cuando el sim llega a fin_min + 5 de gracia:
python evaluacion/verificar.py --log salida/registro.jsonl
```

Flags útiles: `--acelerar 60` (partido en ~2 min para iterar), `--inicio-min 45`
(probar el cambio de turno), `--inicio-min 40`, `--sin-ui`, `--exportar`
(exporta `entrega/` y sale), `--servidor URL`.

**Test de reclamos**: `python test_reclamo.py` (con plataforma en modo
`interactivo`) — loguea como la jueza Laura y pulsa "forzar IP" sobre el
expediente de `tv.verpartido-hd.test` (IP compartida) → genera colateral real →
los reclamos automáticos → levantamiento firmado + reemplazo por dominio.
Es la forma de DEMOSTRAR reclamos en el video: jugando perfecto el sim
**nunca emite reclamos** (ver quirks abajo).

---

## 3. Arquitectura (`plataforma/`, stdlib puro, Python 3.9+)

```
main.py                Orquestador + hilos. Flags: --modo/--servidor/--reset/--sin-ui/--exportar
config.py              Constantes. SERVIDOR default http://127.0.0.1:8080
cliente_sim.py         Cliente HTTP (urllib). Fuerza localhost→127.0.0.1 (ver quirks)
db.py                  SQLite única + lock global + WAL + synchronous=OFF.
                       actuacion(): append-only con hash encadenado por expediente.
motor/reloj.py         Cachea /estado y extrapola el minuto entre polls (usa `acelerar`).
motor/turnos.py        esperar_firma_segura(): si falta < MARGEN_TURNO_MIN (0.6)
                       para el fin del turno, duerme hasta el borde y devuelve
                       el juez ENTRANTE. Toda firma pasa por acá (órdenes,
                       reintentos y levantamientos de reclamos).
motor/verificador.py   clasificar(): pirata / licenciatario / descartada.
                       analizar_colateral(): dns-pasivo → ip|dominio.
motor/expediente.py    Un expediente por tupla (host_stream, ip_servidor).
motor/poller.py        Thread fetch (/estado,/detecciones,/reclamos cada 0.5 s)
                       + cola + 4 workers en paralelo + lock por tupla.
motor/dispatcher.py    Worker por (expediente, proveedor): firma → POST →
                       espera confirmación. Monitor CONSOLIDADO: 4 GET/ciclo
                       (lista completa por proveedor), no uno por orden.
motor/reclamos.py      Ubica la orden aplicada que afecta el dominio reclamado,
                       la levanta firmada y despacha reemplazo por dominio.
juez/servidor_ui.py    ThreadingHTTPServer: login (cookie), bandeja, detalle,
                       aprobar/forzar-ip/rechazar, /transparencia público.
juez/templates.py      HTML server-side (dark, autorefresh 4 s).
auditoria/exportar.py  entrega/expediente-ejemplo.json + registro-auditoria.json
datos_app/plataforma.db  SSOT (se crea sola; --reset la borra)
```

Modos: `auto` = firma inmediata tras peritaje (la "orden marco": narrativa para
el pitch). `interactivo` = queda `elevado` hasta que el juez apruebe en la web.

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
12. **Race `expedientes.id` (vie 13, arreglado):** dos workers de tuplas
    distintas podían hacer `COUNT(*)+1` a la vez → mismo id → `UNIQUE
    constraint failed` y la detección se perdía (se recuperaba con la
    siguiente detección del stream, pero era riesgo latente). Fix:
    `db.bloqueo()` (contextmanager sobre el RLock global) envolviendo
    todo `obtener_o_crear`. Verificado: 20 creates concurrentes → 20 ids
    únicos, 0 errores.

---

## 5. Resultados de corridas verificadas

**×60 desde min 0 (vie 13, post-fix race):**
```
fases_piratas_bloqueadas: 7 de 7     visibilidad_residual: 5.6 %
primer bloqueo por fase: 0.5–5.5 min   clientes cubiertos: 100 % todas
colateral/falsos_positivos/rechazos/fuera_de_turno/ip_post_partido: 0
ordenes: 30 recibidas / 28 aplicadas / 2 fallidas (Cumbre, reintentos r1 OK)
reclamos (test forzado): 3/3 levantados firmados en <0.5 min
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

## 6. Pendiente (Hito 3–4, viernes 13)

- [ ] **Video ≤ 3 min**: corrida de práctica. Guión en PLAN.md §8.3. Incluir el
      truco "forzar IP" para mostrar un reclamo resuelto.
- [ ] **README del repo**: cómo correr, supuestos, qué código existía antes
      (stdlib puro, sin deps). Reusar secciones 2–4 de este archivo.
- [x] Regenerar `entrega/expediente-ejemplo.json` + `registro-auditoria.json`
      (`--exportar` tras la corrida 7/7 del vie 13).
- [ ] Pulir UI si sobra tiempo (prioridad baja vs. motor).
- [x] Probar `--inicio-min 40` completo (ver §5: 6/7 estructural, no bug).
- [ ] Commits periódicos + repo público para Hacki; congelar al cierre.

## 7. Decisiones de diseño ya tomadas (no reabrir sin motivo)

- Cero dependencias externas (stdlib) — portabilidad garantizada día 3.
- SQLite única con lock global (carga baja, cero problemas de concurrencia).
- Dispatcher con un thread por (expediente, proveedor) + monitor consolidado.
- Auto-firma como "orden marco judicial" (propuesta normativa #2) — la demo y
  el pitch quedan alineados; el modo interactivo existe para el video.
- Estructura de archivos como en PLAN.md §3; `plataforma/datos_app/juzgados_local.json`
  no se duplicó: se lee `datos/juzgados.json` directo (las claves finales son
  las mismas según README del desafío).
