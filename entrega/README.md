# Carpeta de Entregables Oficiales — Día 3
**Hackathon Argentina Space 2026 · Desafío Fútbol**  
**Proyecto:** DEOB (Diligenciamiento Electrónico de Órdenes de Bloqueo) + SICRE  
**Equipo:** Luis Alberto Villegas ([@luisvillegas-ade](https://github.com/luisvillegas-ade))

---

## 📋 Índice de Entregables

En esta carpeta se encuentran todos los artefactos requeridos por la organización para la evaluación final:

### 1. Propuesta Normativa (1 página)
📄 [`propuesta-normativa.md`](propuesta-normativa.md)  
Establece los 7 puntos clave que deben reglar ENACOM y el Poder Judicial de la Nación para viabilizar el sistema en Argentina:
- Orden judicial marco dinámica.
- Registro Federal Único de Prestadores de Acceso (RFPA).
- Prohibición de bloqueo de IPs compartidas (control de daño colateral).
- Vencimiento de pleno derecho al término del partido.
- Cadena de custodia criptográfica auditable.
- Procedimiento sumario digital de reclamos (Módulo SICRE).
- Turnos judiciales continuos con firma personal indelegable.

---

### 2. Expediente Electrónico Exportado
📄 [`expediente-ejemplo.json`](expediente-ejemplo.json)  
Causa `EXP-2026-000003` generada durante el partido de práctica:
- Carátula, IP del servidor y ASN.
- Peritaje técnico forense: marcas de agua extraídas, hashes SHA-256 de las capturas binarias y coexistencia en DNS pasivo.
- Órdenes libradas y confirmadas por los proveedores.
- Historial de fojas encadenadas criptográficamente.

---

### 3. Registro Integral de Auditoría
📄 [`registro-auditoria.json`](registro-auditoria.json)  
El libro diario inalterable de toda la sesión:
- Contiene las 180 actuaciones procesales, 38 evidencias y 33 órdenes.
- **Verificación independiente:** Cualquier auditor puede recomputar la cadena sin confiar en la plataforma ejecutando:
  ```powershell
  python -m plataforma.auditoria.verificar_cadena entrega/registro-auditoria.json
  ```
  *(Resultado verificado: `INTEGRIDAD OK`).*

---

### 4. Validaciones del Evaluador Oficial
📁 [`validacion/`](validacion/)  
Contiene los logs crudos y la salida formal de `evaluacion/verificar.py` certificando el resultado:
- **7 de 7** fases piratas neutralizadas (100% de cobertura).
- **3,2%** de visibilidad residual promedio.
- **0** falsos positivos y **0** órdenes fuera de turno.
- **3 de 3** reclamos de terceros resueltos por levantamiento y sustitución.

---

### 5. Video del Pitch y Demo
- **Pitch y Demo técnica:** Enlace disponible en la plataforma del evento (Hacki).
- **Guion y libreto maestro:** [`../PITCH-MASTER.md`](../PITCH-MASTER.md).
- **Instrucciones paso a paso para reproducción:** [`../GRABAR-VIDEO.md`](../GRABAR-VIDEO.md).
