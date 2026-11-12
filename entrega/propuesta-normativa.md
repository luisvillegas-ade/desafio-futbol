# Propuesta normativa — Plataforma federal de órdenes de bloqueo en vivo

*Una página. Qué debería establecer una ley o resolución (ENACOM + Poder Judicial) para que esta plataforma funcione, y por qué.*

## 1. Orden judicial marco dinámica

El juez competente libra **una sola orden marco por evento deportivo**, antes o al inicio del mismo, que autoriza a la plataforma (fiscalía/titular de derechos) a **incorporar dinámicamente direcciones IP y FQDN verificados pericialmente** durante la duración del evento. Cada incorporación queda asentada como actuación numerada en el expediente electrónico con evidencia verificable (captura + hash + sello de tiempo), y queda a disposición del juez para control posterior inmediato.

**Por qué:** hoy cada bloqueo requiere intervención judicial individual; a la velocidad de la piratería en vivo (minutos), el circuito manual hace imposible llegar a tiempo sin convertir la firma en un trámite vacío. La orden marco conserva el control judicial real (define el perímetro: qué señal, qué evento, qué tipo de medida) sin convertir al juez en cuello de botella.

## 2. Registro Federal Único de Prestadores de Acceso (RFPA)

Todo ISP que opere en el país —incluidos cooperativas y proveedores regionales pequeños— debe registrar en ENACOM un **punto de contacto API** para recepción de medidas cautelares en vivo, declarando sus capacidades técnicas (tipo de bloqueo que puede aplicar: IP, dominio/DNS, SNI). La falta de registro no exime del cumplimiento: la orden se les notifica por el canal declarado y se presume recibida.

**Por qué:** en el operativo de mayo de 2025 la orden llegó a los proveedores a través de cámaras porque no existía registro actualizado; los ISPs chicos son justamente los que más tardan y los que menos capacidad tienen (algunos solo pueden filtrar DNS).

## 3. Proporcionalidad técnica: prohibición de bloqueos de IP compartidas

Toda medida debe ser precedida de una **verificación de coexistencia** (DNS pasivo o fuente equivalente) que acredite si la dirección IP aloja servicios ajenos al infractor. Si existe coexistencia, está **prohibido el bloqueo por IP** y la medida debe circunscribirse al FQDN infractor. La verificación queda agregada al expediente como peritaje.

**Por qué:** bloquear una IP compartida derriba sitios legítimos (panaderías, municipios, medios) — es el daño colateral que ya generó incidentes en Italia (Piracy Shield) y la principal objeción de las cámaras de proveedores.

## 4. Vencimiento de pleno derecho

Toda restricción por dirección IP **vence automáticamente transcurridos 15 minutos de finalizado el evento deportivo**, sin necesidad de orden judicial adicional. Los bloqueos por dominio pueden subsistir solo si la orden marco lo autoriza expresamente y por plazo cierto. El registro público muestra estado y fecha de expiración de cada medida.

**Por qué:** un bloqueo residual es censura sin causa vigente; el vencimiento automático elimina el riesgo de "órdenes olvidadas" y da previsibilidad a los proveedores.

## 5. Procedimiento sumario digital de reclamos

Todo titular de un sitio afectado puede reclamar por **vía digital sumarísima** (formulario/API pública). La plataforma debe elevar el reclamo al juez de turno y la medida debe resolverse en un **plazo máximo de 15 minutos**: si el afectado es ajeno al infractor, se dispone el levantamiento inmediato y, cuando corresponda, su reemplazo por una medida más precisa sobre el objetivo real.

**Por qué:** sin vía rápida de reparación, el daño colateral se convierte en irreparable y el sistema pierde legitimidad. El plazo corto es viable justamente porque todo el circuito ya es digital y trazable.

---

*Documento elaborado para el Desafío Fútbol — Hackathon Argentina Space 2026. Datos ficticios; no es asesoramiento legal.*
