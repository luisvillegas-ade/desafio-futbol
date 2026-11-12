# 🎬 GRABAR EL VIDEO — paso a paso exacto

Lo único que necesitás: **una terminal PowerShell** y **el navegador**.
Grabás la pantalla con **Win + G** (Xbox Game Bar, ya viene con Windows)
o con OBS si lo tenés. Duración objetivo: menos de 3 minutos.

---

## PASO 0 — Preparar (una sola vez)

1. Abrí PowerShell (tecla Windows → escribí `powershell` → Enter).
2. Copiá y pegá estas **dos líneas**:

```powershell
cd C:\Proyectos-Hackatones\argentinaSpace\desafio-futbol
python demo.py --acelerar 60
```

3. Si pregunta `[demo] ¿los freno? [S/n]` → apretá **Enter** (nada más).
4. Esperá ~10 segundos: **se abre el navegador solo** en la consola judicial.
   Cuando lo veas, todo está corriendo. No cierres la terminal.

5. Abrí **una pestaña más** en el navegador con esta dirección:

```
http://127.0.0.1:8090/monitor
```

Ya tenés tus dos pantallas: **Consola** (pestaña 1) y **Monitor** (pestaña 2).

---

## PASO 1 — Empezar a grabar

- Apretá **Win + G** → tocá el botón **⏺ grabar** (o Win + Alt + R directo).
- El video queda guardado en `Videos\Capturas`.

> Tip: no hace falta hablar perfecto — podés regrabar las veces que quieras,
> el partido se reinicia cada vez que corrés `python demo.py --acelerar 60`.

---

## PASO 2 — Escena 1: el problema y la detección (~25 seg)

**Pantalla:** pestaña del **Monitor**.

El partido corre solo — vas a ver caer las detecciones y crearse los
expedientes. Decí más o menos esto con tus palabras:

> *"Cada fin de semana se piratean partidos en vivo. El problema: bloquear
> rápido sin tirar sitios legítimos. Esta plataforma abre un expediente
> judicial por cada señal pirata — y todo corre en vivo."*

---

## PASO 3 — Escena 2: el expediente y la firma del juez (~40 seg)

1. Cambiá a la pestaña **Consola** → login: usuario `laura`, clave `demo`.
2. Vas a ver expedientes en la bandeja con botones. Entrá a uno (clic en su ID).
3. Se ve: carátula, peritaje técnico (marca de agua, SHA-256, DNS pasivo),
   medida sugerida, dependencia. Volvé a la bandeja (`← Bandeja`).
4. Apretá **"Aprobar y mandar bloqueo urgente"** en un par de expedientes.
5. Volvé al **Monitor**: las pills `[aurora] [andina] [cumbre] [valle]` se
   ponen verdes y los chips se mueven a la columna `despacho`.

Decí:

> *"El juez de turno revisa el peritaje automático y firma. La orden sale
> en paralelo a los cuatro proveedores — y si uno falla, se reintenta solo.
> Todo movimiento queda en la cadena de custodia, como un libro diario."*

---

## PASO 4 — Escena 3: el reclamo del ciudadano (~45 seg)

Esta es la escena estrella.

1. En la **Consola**, entrá al expediente de `tv.verpartido-hd.test`
   (suele ser `EXP-2026-000005`, aparece ~min 9 — si todavía no está,
   esperá unos segundos).
2. Apretá **"Aprobar forzando IP"** → esto bloquea la IP compartida y
   afecta a la panadería legítima.
3. Abrí **otra pestaña** (sin login, es público):

```
http://127.0.0.1:8090/reclamar
```

4. Escribí `panaderia-la-espiga.test` en el dominio → **Enviar reclamo**.
5. Volvé al **Monitor**: en el log aparece `[reclamos]` y el contador
   `reclamos 1` — el sistema levantó el bloqueo con firma judicial y lo
   reemplazó por uno preciso por dominio.

Decí:

> *"Si el bloqueo se pasa de largo, hay remedio. El ciudadano reclama sin
> login, el juez levanta la medida firmado y el sistema la reemplaza por
> una más precisa. Debido proceso — no censura."*

---

## PASO 5 — Escena 4: la prueba de auditor (~30 seg)

1. El partido ya terminó (~2 min). En la **terminal** vas a ver el puntaje:
   `fases piratas bloqueadas: 7 de 7`.
2. Abrí **otra PowerShell** (la primera sigue abierta), pegá:

```powershell
cd C:\Proyectos-Hackatones\argentinaSpace\desafio-futbol
python -m plataforma.auditoria.verificar_cadena
```

3. Muestra: `INTEGRIDAD OK — N actuaciones verificadas`.

Decí:

> *"Resultado: 7 de 7 fases bloqueadas, cero daño colateral, cero firmas
> fuera de turno. Y la cadena de custodia es verificable por cualquiera —
> tocás una foja y el auditor te dice exactamente cuál está trucada."*

---

## PASO 6 — Cortar

- **Win + Alt + R** otra vez → el video queda en `Videos\Capturas`.
- Recortalo si quedó largo (fotos de Windows ya trae editor, o Clipchamp).

---

## Si algo sale mal

| Problema | Solución |
|---|---|
| La ventana se cerró sola | Volvé al PASO 0 — el launcher ya está arreglado |
| Pregunta sobre puertos | Enter = sí, frena los procesos viejos |
| El navegador no se abrió | Escribí `http://127.0.0.1:8090` a mano |
| El partido ya terminó y querés regrabar | Ctrl+C en la terminal, Enter, y PASO 0 otra vez |
| No existe el expediente verpartido todavía | Esperá ~15 seg más y actualizá la página |

---

## Resumen en 3 líneas (para tener al lado)

```
1) cd C:\Proyectos-Hackatones\argentinaSpace\desafio-futbol
2) python demo.py --acelerar 60        → Enter si pregunta
3) Win+Alt+R graba · monitor + consola + /reclamar · Win+Alt+R corta
```
