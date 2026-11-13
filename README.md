# DEOB + SICRE: Juzgado Digital de Bloqueo en Vivo

**Sistema Federal de Medidas Cautelares en Vivo y Tutela de Terceros Afectados**  
*Hackathon Argentina Space 2026 · Track Datos y Streaming (QualyData) · Salta, 11 al 13 de noviembre de 2026*  
**Autor:** Luis Alberto Villegas ([@luisvillegas-ade](https://github.com/luisvillegas-ade))  
**Vidriera en línea:** [https://desafio-futbol-two.vercel.app](https://desafio-futbol-two.vercel.app) *(Jueces: `laura` / `martin`)*  
**Consigna del desafío:** [CONSIGNA-ORIGINAL.md](CONSIGNA-ORIGINAL.md) · **Entregables Día 3:** [`entrega/`](entrega/)

---

## ⚖️ Nuestra propuesta: DEOB + SICRE

En un partido de fútbol, la piratería en vivo cambia de IP y servidor en minutos. Cortarla a ciegas causa un daño irreparable: derriba sitios legítimos de comercios, pymes o municipios alojados en la misma infraestructura compartida. Y delegar la censura a un algoritmo viola el art. 57 inc. a) de la Ley 27.078 (Argentina Digital).

Inspirados en la arquitectura judicial del **Poder Judicial de la Nación (PJN)** —que ya implementó **DEOX** para oficios electrónicos y opera sobre **Lex100**— desarrollamos una solución integral de Estado compuesta por dos módulos complementarios:

1. **DEOB (Diligenciamiento Electrónico de Órdenes de Bloqueo en Vivo):**  
   Módulo judicial que realiza el peritaje técnico forense en tiempo real (marca de agua + DNS pasivo), arma el expediente electrónico encadenado con hashes criptográficos y somete la cautelar a la firma digital del **juez de turno personal**. Despacha en paralelo a todos los ISPs del país, reintenta fallas y vence automáticamente al finalizar el evento deportivo.
2. **SICRE (Sistema Integral de Consulta y Reclamo Electrónico):**  
   Módulo público sumarísimo y gratuito (vía pública `/reclamar`, sin login ni letrado). Si un sitio legítimo sufre daño colateral, denuncia su dominio; el reclamo ingresa en segundos al despacho del magistrado, quien con un clic firma el levantamiento y su reemplazo por bloqueo de FQDN. **Debido proceso constitucional en tiempo real**.

---

## 🚀 Cómo correr el sistema (100% Python Estándar, Cero `pip install`)

> **Por qué stdlib puro para la evaluación oficial:**  
> El partido final corre en una máquina de evaluación de la organización. Sin dependencias externas no hay riesgos de red, conflictos de entorno ni fallas de librerías. Todo el motor core corre nativamente en Python 3.9+ estándar.

### Camino rápido (Recomendado):
Doble click en `JUGAR.bat`, o un solo comando en PowerShell:

```powershell
python demo.py                  # Modo interactivo a x6 (~17 min reales)
python demo.py --acelerar 25    # Velocidad sugerida para probar clicks y grabar (~4 min)
python demo.py --acelerar 60    # Corrida rápida de iteración (~2 min)
```

`demo.py` inicia el simulador oficial y la plataforma, abre el navegador en la consola judicial y, tras cumplirse los 5 minutos de gracia reglamentarios, ejecuta automáticamente `evaluacion/verificar.py` mostrando el tablero de control.

### Ejecución manual (Tres terminales):

```powershell
# Terminal 1 — Simulador oficial (en Windows habilitar UTF-8 para caracteres especiales)
$env:PYTHONUTF8=1; python simulador/servidor.py --escenario datos/escenario_practica.json --acelerar 6

# Terminal 2 — Plataforma judicial (desde la raíz del repo)
python -m plataforma.main --modo interactivo --reset

# Superficies disponibles:
#   • Consola judicial:    http://127.0.0.1:8090  (laura / martin — clave: demo)
#   • Monitor en vivo:     http://127.0.0.1:8090/monitor        (público / NOC)
#   • Transparencia:       http://127.0.0.1:8090/transparencia  (público)
#   • Portal SICRE:        http://127.0.0.1:8090/reclamar       (público)

# Terminal 3 — Evaluación y Auditoría (al finalizar el partido + 5 min gracia)
python evaluacion/verificar.py --log salida/registro.jsonl
python -m plataforma.auditoria.verificar_cadena                  # Verifica integridad SHA-256
```

---

## 🌐 Vidriera en línea (Vercel + Neon/Postgres)

Para permitir que el juez revise expedientes desde su celular o que la ciudadanía consulte el registro público desde cualquier dispositivo, desarrollamos una vidriera web en **[https://desafio-futbol-two.vercel.app](https://desafio-futbol-two.vercel.app)**.

```
Celular del Juez / Ciudadano ──► Vercel (FastAPI en Neon/Postgres São Paulo)
                                       │ (La web registra la decisión firmada)
Simulador Oficial (Local)   ◄── Motor Local (plataforma/, Python stdlib)
```

- **Arquitectura desacoplada:** La web sólo actúa como interfaz de captura; el motor local lee las decisiones, las valida criptográficamente contra el reloj del simulador y las despacha.
- **Sin `DATABASE_URL`:** El sistema corre en SQLite local 100% puro y aislado, garantizando el cumplimiento estricto del evaluador del hackathon.

---

## 📊 Resultados Auditados en el Escenario Oficial

Métricas arrojadas por el evaluador oficial (`evaluacion/verificar.py`) sobre la corrida interactiva completa:

| Métrica de Evaluación | Cliente Mínimo (Org) | Sistema DEOB + SICRE | Estado |
|---|:---:|:---:|:---:|
| **Fases piratas bloqueadas** | 1 de 7 | **7 de 7 (100 %)** | ✅ Óptimo |
| **Visibilidad residual promedio** | 86,6 % | **3,2 %** | ✅ Máxima efectividad |
| **Falsos positivos (Licenciatarios)** | — | **0** | ✅ Canal Norte protegido |
| **Órdenes fuera de turno judicial** | — | **0** | ✅ Respeto estricto del min 50 |
| **Bloqueos residuales post-partido** | Sí | **0** | ✅ Vencimiento de pleno derecho |
| **Reclamos atendidos (SICRE)** | 0 | **3 de 3 (100 %)** | ✅ Levantados y sustituidos |
| **Cadena de Custodia Criptográfica** | No | **INTEGRIDAD OK** | ✅ 180 fojas, 38 ev, 33 ord |

---

## 🏛️ Pipeline Técnico del Sistema

1. **Peritaje Forense Automatizado (`motor/verificador.py`):**  
   Extrae la marca de agua y la contrasta contra `/partido`. Excluye licenciatarios en sus dominios autorizados y consulta `/dns-pasivo` para clasificar la infraestructura (IP dedicada vs. hosting compartido/CDN).
2. **Expediente Electrónico Encadenado (`motor/expediente.py` + `db.py`):**  
   Carátula única por tupla `(host_stream, ip_servidor)`. Cada cambio de IP abre una ampliación de fase cautelar. Cada foja se numera y enlaza mediante:  
   `sha256(hash_previo | expediente_id | foja_n | tipo | detalle | minuto | timestamp_iso)`.
3. **Control Estricto de Turnos Judiciales (`motor/turnos.py`):**  
   La orden sólo es válida si el juez está formalmente de turno. Con un margen de seguridad de 0,6 min antes del relevo (min 50), las aprobaciones se transfieren al juez entrante. Nadie firma por otro.
4. **Despacho Multicanal y Reintentos (`motor/dispatcher.py`):**  
   Despacho simultáneo a los cuatro prestadores. Traducción automática para proveedores con soporte restringido (ej. FibraValle sólo acepta FQDN). Reintento inmediato ante caídas de enlace (Cumbre ~35% error) con `orden_id` nuevo.
5. **Vencimiento de Pleno Derecho (`hilo_cierre` en `main.py`):**  
   Al llegar al pitazo final (`fin_min + 5`), todas las restricciones por IP se extinguen automáticamente, eliminando la censura residual.
6. **Módulo SICRE (`motor/reclamos.py`):**  
   Canal de atención ciudadana inmediata. Identifica qué ISP bloquea al inocente, eleva la tercería a la bandeja del juez y ejecuta el levantamiento con sustitución de medida.

---

## 📁 Entregables del Hackathon (Día 3)

Todos los entregables exigidos por la organización se encuentran disponibles en el repositorio:

- **Propuesta Normativa (1 página, 7 puntos):** [`entrega/propuesta-normativa.md`](entrega/propuesta-normativa.md). Establece las bases legales para la orden marco dinámica, el Registro Federal de Proveedores (RFPA) y el procedimiento sumario de reclamos bajo la Ley 19.549.
- **Expediente de Ejemplo Exportado:** [`entrega/expediente-ejemplo.json`](entrega/expediente-ejemplo.json). Causa `EXP-2026-000003` completa con evidencias, fojas y órdenes.
- **Registro Integral de Auditoría:** [`entrega/registro-auditoria.json`](entrega/registro-auditoria.json). Cadena de custodia íntegra verificable con `verificar_cadena.py`.
- **Guía de Grabación y Demo:** [`GRABAR-VIDEO.md`](GRABAR-VIDEO.md).
- **Pitch Oficial del Equipo:** [`PITCH-MASTER.md`](PITCH-MASTER.md).
