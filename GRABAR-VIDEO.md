# 🎬 GUÍA PRÁCTICA: CÓMO GRABAR LA PANTALLA EN SILENCIO (VELOCIDAD CÓMODA)
*(Aceleración x25: te da 2 minutos enteros de reloj real para hacer los clicks con la Jueza Laura antes del cambio de turno).*

---

## ⚙️ PASO 0 — Preparar el entorno (Antes de grabar)

### 1. Terminal 1 (Ejecutar con aceleración x25):
```powershell
cd C:\Proyectos-Hackatones\argentinaSpace\desafio-futbol
python demo.py --acelerar 25
```
*(Si te pregunta `[demo] ¿los freno? [S/n]`, apretá **Enter**).*

### 2. Ventana 1 de Navegador (Normal) — Dejá 4 pestañas abiertas:
- **Pestaña 1:** `http://127.0.0.1:8090` (Login: poné `laura` / `demo` y entrá a la Bandeja).
- **Pestaña 2:** `http://127.0.0.1:8090/monitor` *(Dejala visible en pantalla)*.
- **Pestaña 3:** `http://127.0.0.1:8090/reclamar` (Escribí en el formulario: Dominio: `panaderia-la-espiga.test` | Mensaje: `Bloqueo indebido` — **NO aprietes el botón todavía**).
- **Pestaña 4:** `http://127.0.0.1:8090/transparencia`.

### 3. Ventana 2 de Navegador (Modo Incógnito: Ctrl + Shift + N):
- Abrí `http://127.0.0.1:8090` y logueate con: usuario `martin` / clave `demo`.  
  *(Dejá esta ventana minimizada o al costado, la usás recién cuando termine el turno de Laura).*

### 4. Terminal 2 (Dejar escrita la línea, sin apretar Enter):
```powershell
cd C:\Proyectos-Hackatones\argentinaSpace\desafio-futbol
python -m plataforma.auditoria.verificar_cadena
```

---

## 🔴 PASO 1 — Empezar a grabar

1. Mirá la **Pestaña 2 (Monitor)**: cuando el reloj arriba marque **`6′`** o **`7′`**:
2. Apretá **`Win + Alt + R`** (o Win + G) para iniciar la grabación de pantalla.

---

## 🖱️ PASO 2 — Los Clicks Exactos (Sin apuros)

### [Paso A] En el Monitor (~15 segundos)
- Estás en la **Pestaña 2 (Monitor)**.
- Mové suavemente el mouse sobre el registro inferior donde dice `deteccion_descartada` (Canal Norte) y sobre los nodos del centro.

---

### [Paso B] Peritaje en el Expediente (~20 segundos)
1. Cambiá a la **Pestaña 1 (Bandeja de Laura)**.
2. Hacé clic en el enlace azul **`EXP-2026-000002`** (Golazo Libre).
3. Quedate unos segundos mostrando la caja celeste que dice *"Por qué esta medida: La IP aloja 12 dominios..."*.

---

### [Paso C] Firma de la Jueza Laura (~20 segundos)
1. Hacé clic en **`← Bandeja`** (arriba a la derecha).
2. Hacé clic en el botón azul **`Aprobar y mandar bloqueo urgente`** de **`EXP-2026-000001`**.
3. Hacé clic en el botón azul **`Aprobar y mandar bloqueo urgente`** de **`EXP-2026-000002`**.
4. Cambiá 3 segundos a la **Pestaña 2 (Monitor)**: se ven las pastillas `[aurora] [andina]` en verde.

---

### [Paso D] La Prueba de Reclamo (~35 segundos)
1. Volvé a la **Pestaña 1 (Bandeja)**.
2. En la fila de `EXP-2026-000003` (Verpartido), hacé clic en el botón gris **`Aprobar forzando IP`**.
3. Cambiá a la **Pestaña 3 (`/reclamar`)**.
4. Hacé clic en el botón **`Presentar reclamo`** (esperá a que aparezca el cartel verde).
5. Volvé a la **Pestaña 1 (Bandeja)**: arriba apareció la tabla amarilla con el reclamo.
6. Hacé clic en el botón **`Hacer lugar: levantar y reemplazar`** (o tocá la tecla **`A`**).

*(¡Listo! Todo esto lo terminás con Laura con tiempo de sobra antes de que el reloj llegue al minuto 50).*

---

### [Paso E] Cambio de Turno al Juez Martín (~25 segundos)
*(Esperá a que el reloj del partido cruce el minuto 50)*
1. En la Pestaña 1 (Laura), mostrá que arriba ahora dice `FUERA DE TURNO — solo lectura`.
2. Pasá a la **Ventana Incógnito (Juez Martín)**: mostrá que dice `DE TURNO · puede firmar`.
3. Si hay algún expediente pendiente en la bandeja de Martín, tocale el botón **`Aprobar`** (o apretá la tecla **`A`**).
4. Cambiá a la **Pestaña 4 (Transparencia)** unos segundos: se ven las órdenes públicas con su fecha y hora.

---

### [Paso F] Cierre y Verificación Oficial
1. Cuando el reloj del partido supere los **`110′`** (105 + 5 de gracia), andá directo a la **Terminal 1**.
2. Mostrá la salida del script oficial `verificar.py` con el texto **`fases piratas bloqueadas: 7 de 7`**.
3. Cambiá a la **Terminal 2** y apretá **`Enter`**.
4. Mostrá la salida: **`INTEGRIDAD OK — N actuacion(es)... verificadas`**.

---

## ⏹️ PASO 3 — Cortar la grabación
- Apretá **`Win + Alt + R`** para cortar la grabación.
- El video queda en: `Este equipo > Videos > Capturas`.
