# Plan — Deploy de la consola judicial en Vercel + pulido final

**Objetivo:** los jueces aprueban desde un navegador (celular o notebook) sin
instalar nada — misma ventaja que tiene el equipo de referencia
(`alejogomezmdz14-hash/desafio-futbol`). El motor sigue corriendo en la máquina
del equipo porque el simulador del partido final vive en la **red local del
evento**; lo que migra a la nube es la **consola judicial + la base de datos**.

**Corte duro:** lo que no esté verificado end-to-end el **vie 13 a las 08:00**
no se usa en el partido final. El plan B (túnel) y el modo local puro ya están
verificados y siempre quedan disponibles.

**Regla de oro — modo local CONGELADO:**
`python -m plataforma.main --modo interactivo` con SQLite y UI en `127.0.0.1:8090`
debe seguir funcionando **idéntico a hoy**, sin dependencias nuevas. Todo el
deploy es aditivo y se activa solo con `DATABASE_URL=postgres://...`. Las deps
nuevas (fastapi/uvicorn/psycopg) las importa únicamente `plataforma/api/` — el
motor local jamás las importa.

---

## Arquitectura destino

```
simulador org (LAN del evento, http://<ip>:8080)
   ▲  ▼  detecciones / órdenes / reclamos
MOTOR — notebook del equipo (sin cambios funcionales)
   ▲  ▼  DATABASE_URL → psycopg + TLS
NEON POSTGRES — SSOT compartido (región São Paulo, tier free)
   ▲  ▼
VERCEL — FastAPI: mismas vistas HTML de templates.py + API
   ▲  ▼  HTTPS
JUEZ EN EL CELULAR — login, bandeja, aprobar / hacer lugar. Cero instalación.
```

**Restricción de diseño crítica (no negociable):**
Todo lo que toca el simulador (firmar órdenes, despachar, levantar bloqueos)
**solo lo ejecuta el motor local**. La web desplegada en Vercel únicamente
registra *decisiones* en la base (`estado`, `aprobada_por`, `juez_asignado`,
marca de reclamo aceptado). Los handlers actuales de `servidor_ui.py` llaman
directo a `gestor.resolver()` que firma y POSTea al sim — en el modo
desplegado ese camino se bifurca: la web marca la decisión y el hilo
`Thread-Reclamos` del motor la ejecuta. Lo mismo para cualquier POST que hoy
firme algo: en cloud-mode la web escribe la intención, el motor la ejecuta.

---

## Fase 0 — Pulido sin infra (1–2 h, independiente del deploy)

1. **Anclaje legal** en `entrega/propuesta-normativa.md` (sin agrandarla: refs
   parentéticas cortas):
   - Art. 57 inc. a) Ley 27.078 — prohibición de bloqueo sin orden judicial.
   - CSJN "Rodríguez c/ Google" — examen caso por caso antes de bloquear.
   - Ley 25.506 — en producción la firma es digital con certificado del juez
     (el HMAC del sim es placeholder; la propuesta ya lo decía, citar la ley).
2. **"Aprobar todo"** en la bandeja: POST `/exp/aprobar-todo` que aprueba en
   lote todos los `elevado` del juez en sesión (asienta actuación +
   `aprobada_por` por cada uno, respeta anti-doble-clic y turno). Replica el
   "firmar en lote" del competidor.
3. **Tabla comparativa** en `README.md`: correr el cliente de ejemplo de la org
   (`ejemplos/`) contra el sim de práctica y medir su resultado real
   (esperado ~1/7, ~92 % residual) → tabla `cliente org vs plataforma`
   con nuestros números verificados (7/7, 3.1 % x6). Storytelling clave.
4. **`entrega/validacion/`** con la evidencia de la corrida x6 ya hecha:
   `verificar.txt` (salida de `evaluacion/verificar.py`) +
   `verificar-cadena.txt` (salida del verificador sobre el export) +
   `nota.md` (comando y aceleración usados). Generado por redirect de
   salida, **sin editar a mano**.
5. **`--red`**: flag en `main`/`servidor_ui` para bindear `0.0.0.0` en vez de
   `127.0.0.1` (default sigue siendo loopback). Fallback "juez desde el celular
   por wifi" si Vercel no llega.

## Fase 1 — Postgres como SSOT desplegable (`db.py`)

Backend por `DATABASE_URL`: vacío → SQLite (actual, intocable);
`postgres://` → psycopg. Mantener **valores y formato idénticos** (timestamps
como TEXT ISO, mismos strings) para que hashes y cadena sean byte-idénticos
entre backends.

Cambios mecánicos previstos en `db.py`:

- Placeholders: función `_q(sql)` que traduce `?`→`%s` solo en backend pg.
- Unificar upserts a sintaxis común: `INSERT ... ON CONFLICT DO NOTHING` y
  `ON CONFLICT (pk) DO UPDATE` (SQLite ≥3.24 y PG las aceptan ambas).
- `lastrowid`: en pg usar `INSERT ... RETURNING id`; en sqlite queda igual.
- DDL: branch por backend (pg: `SERIAL`/`GENERATED`, sqlite: `INTEGER PRIMARY
  KEY`). Los `ALTER` de migración idem.
- Filas: normalizar acceso por nombre → `dict(row)` en el borde
  (`dict_row` en psycopg; sqlite `Row`→dict), revisar que ningún sitio use
  `row[0]` posicional.
- PRAGMAs/WAL/synchronous: solo en sqlite.
- **`actuacion()` — carrera cross-proceso (el bug real del deploy):**
  hoy calcula `n = max(n)+1` en Python bajo `_lock`, que no existe entre
  procesos. Con motor+web escribiendo actuaciones del mismo expediente hay
  colisión de `n`. Fix obligatorio: insertar con
  `INSERT INTO actuaciones(...) SELECT ..., COALESCE(MAX(n),0)+1, ...`
  en una sola sentencia (válido en ambos backends), o bloquear por fila de
  expediente. Verificar con `verificar_cadena` que el formato de hash no
  cambió (no cambia: mismos campos, mismo orden).
- Tabla `sesiones(sid PK, usuario, expira, datos)` creada en init: en backend
  pg la web la usa en vez del dict `SESIONES` en memoria. En sqlite local el
  dict puede quedarse (un solo proceso).

Verificación Fase 1: `set DATABASE_URL=postgres://<neon>` +
`python -m plataforma.main --modo interactivo --reset` → corrida x30 completa
con clicker → evaluador 7/7 → `verificar_cadena` INTEGRIDAD OK. Si los hashes
difieren del formato sqlite, algo se serializó distinto: corregir antes de
seguir.

`requirements.txt` (nuevo, solo capa desplegada):
`fastapi`, `uvicorn`, `psycopg[binary]` — con nota en README: el motor local
sigue stdlib-puro; estas deps son solo para el deploy.

## Fase 2 — Web en Vercel

- `plataforma/api/app.py`: FastAPI que **reutiliza `templates.py`** (ya son
  funciones puras que devuelven HTML) y las funciones de `db.py`,
  `motor/turnos.py`, `motor/reclamos.py` que usa `servidor_ui.py`.
  Rutas mínimas: `GET /` (bandeja), `/login`+POST, `/exp/<id>`+`/informe`,
  `/transparencia`, `/reclamar`+POST, `/monitor`(+`/monitor/datos`),
  POST `/exp/<id>/{aprobar,forzar-ip,rechazar,aprobar-todo,pase-*,archivar}`,
  POST `/reclamo/<id>/hacer-lugar`.
- **Regla cloud:** los POST que hoy ejecutan firma+despacho en el request
  (`hacer-lugar` → `gestor.resolver()`, cualquier acción que POSTee al sim)
  se bifurcan: si `DATABASE_URL` apunta a pg **y** no hay motor local en este
  proceso → la web solo marca la decisión en la base; el motor la ejecuta.
  Implementar como flag `SOLO_WEB` (env `MODO_WEB=1` en Vercel).
- `Thread-Reclamos` del motor: extender para que además procese reclamos
  marcados "aceptados por la web" (estado intermedio, ej. `aceptado_web`)
  ejecutando `resolver()` con el `juez_id` registrado.
- Login: cookie `sid` random + tabla `sesiones`; env `SESION_SECRET`;
  env `CLAVE_ACCESO` para override de 'demo' (default solo local).
- `vercel.json` + `api/index.py` (`from plataforma.api.app import app`).
- Neon: crear proyecto free → `DATABASE_URL` en Vercel y en la notebook.
- Deploy: preview primero (`vercel`), prod después (`vercel --prod`).
  URL final esperada: `https://desafio-futbol-<usuario>.vercel.app`.

## Fase 3 — Verificación e2e + entrega

- Corrida de integración: sim local x6 + motor local con `DATABASE_URL`→Neon +
  juez clickeando **desde la URL de Vercel en un celular** → evaluador 7/7,
  residual esperado ~3–8 %, cadena OK, provocar reclamo y "hacer lugar" desde
  el celular (el motor lo ejecuta).
- Guardar salidas en `entrega/validacion/vercel.txt`.
- README: sección "En línea" con la URL + diagrama de 3 líneas.
- **Stretch (solo si sobra tiempo y la cuenta tiene Vercel Sandbox):** botón
  "correr partido de práctica" que levanta sim+motor en un sandbox apuntando
  a la misma base. Si no está disponible en hobby, se omite sin drama — el
  partido final igual corre con motor local contra el sim de la org.

## Plan B — túnel (30 min, cero código, siempre disponible)

Si Vercel/Neon no llega a verificarse: la UI local ya es la consola judicial;
exponerla con `cloudflared tunnel --url http://127.0.0.1:8090`
(`winget install Cloudflare.cloudflared`) o `ngrok http 8090` → imprime una
URL pública `*.trycloudflare.com` que es el acceso del juez desde el celular.
Requisito: la notebook online durante el partido (igual que con Neon).

## Riesgos

- Latencia motor↔Neon (~40–90 ms/escritura desde Salta): despreciable a x1;
  a x6+ medir en la corrida de integración — si laggea, agrupar commits.
- Cold starts de Vercel (~1–3 s la primera request): solo afecta la primera
  carga del juez; el meta-refresh lo mantiene tibio.
- Carrera en `actuaciones.n` entre procesos: cubierta en Fase 1 (sentencia
  atómica). Sin ese fix, NO desplegar.
- Sesiones en memoria entre invocaciones serverless: cubierto (tabla).
- `vercel`/`neon` requieren cuentas del usuario (GitHub login alcanza).

## Lo que NO se toca

- `motor/` (dispatcher, poller, turnos, verificador, reclamos): cero cambios
  funcionales salvo la extensión de `Thread-Reclamos` de Fase 2.
- Hashes, cadena de custodia, huellas: byte-idénticos entre backends.
- `servidor_ui.py` local: queda como está (sigue siendo el modo del partido
  si el deploy falla). El FastAPI reimplementa las rutas llamando las mismas
  funciones; no refactorizar el handler viejo.
- `entrega/*.json`: solo se regeneran con `--exportar`, nunca a mano.
