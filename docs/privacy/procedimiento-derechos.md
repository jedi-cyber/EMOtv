# Procedimiento para atender los derechos de las personas evaluadas

> Sujeto a revisión de la Facultad. Describe cómo se atiende cada solicitud con
> las funciones que hoy tiene EMOtv. **No fija plazos de respuesta**: los plazos,
> la forma de la solicitud y la respuesta ante una negativa dependen de la Ley
> N.° 29733 y del D.S. 016-2024-JUS y deben **verificarse con asesoría legal**.

## Quién atiende

- Las solicitudes llegan a `[3: CONTACTO PARA EJERCER DERECHOS]` o al docente
  responsable.
- **Las atiende el docente** a cargo del usuario que condujo la sesión (o el
  propio docente, si él la condujo): es la única cuenta, junto con quien la
  condujo, que puede ver la sesión, y la única que la elimina (ver
  [matriz-de-accesos.md](matriz-de-accesos.md)). La administración y el soporte
  técnico **no pueden** atenderlas dentro del sistema, porque no acceden a
  sesiones.
- Puede pedirlo la persona adulta o, si es un niño, su padre, madre o tutor.

## Paso 0: identificar las sesiones

EMOtv no registra a las personas evaluadas ni conoce nombres: cada sesión lleva
solo un código aleatorio (`S-` y seis caracteres) que se anotó en el formato
firmado. El docente:

1. Pide a la persona su copia del formato firmado.
2. Comprueba con el formato que custodia (`[10: LUGAR DE CUSTODIA]`) que los
   códigos anotados corresponden a quien lo pide y, si es un niño, que quien
   pide es su padre, madre o tutor. `[Verificar con asesoría legal: cómo
   acreditar la identidad y la representación.]`
3. Busca cada código en **Sesiones** (columna **Código**).

Si no se puede verificar, no se entregan datos ni se elimina nada; se anota en el
registro de solicitudes. Como no hay seguimiento por persona, una sesión cuyo
código no figure en el formato no se puede atribuir a nadie.

## Acceso

Qué entrega EMOtv: el **reporte aprobado** de cada sesión con protocolo,
impreso. Incluye el código de la sesión, la fecha, el modelo usado, la línea de
tiempo (estímulos, expresiones estimadas, cuestionarios con sus respuestas, lo
que dijo ver y los marcadores), las métricas, las respuestas a los cuestionarios
y el texto del reporte, con el aviso de que las expresiones son estimaciones.

1. Para cada código, abre la sesión y su reporte. Si no existe, redáctalo o
   pide a quien condujo que lo redacte; si está en revisión, revísalo y apruébalo
   (el reporte de un docente se cierra sin revisión).
2. En el reporte aprobado, pulsa **Vista imprimible** y luego **Imprimir
   reporte**. El sistema registra la impresión en la auditoría y en el historial
   del reporte.
3. Entrega la copia en mano a la persona. No hay portal para personas evaluadas
   ni envío por correo desde el sistema.
4. Una sesión sin protocolo no tiene reporte: su detalle (expresión registrada,
   fecha y modelo) se puede mostrar en pantalla si se pide. El sistema no tiene
   una vista imprimible de ese detalle.

## Rectificación

**Limitación actual del sistema:** una vez registrados, **no existe una función
para corregir** las respuestas a cuestionarios, los marcadores, lo que dijo ver
ni las expresiones estimadas.

| Dato | Cómo se corrige |
| --- | --- |
| Texto del reporte | Si está en borrador o con observaciones, quien lo redactó lo edita. Si está aprobado, **Crear versión nueva**, corregir y volver a aprobar; la versión anterior queda reemplazada |
| Respuestas u otros registros | Solo eliminando la sesión con acta (ver «Cancelación») |

`[Verificar con asesoría legal: si esta forma de rectificación es suficiente o si
el sistema debe permitir corregir esos datos.]`

## Cancelación (eliminación)

1. Si la sesión la condujo un usuario, ese usuario abre la sesión y pulsa
   **Pedir que se elimine**. El docente también puede eliminar sin solicitud
   previa.
2. El docente abre la sesión, pulsa **Eliminar la sesión** y confirma. En una
   sola transacción se borran la sesión y todos sus registros (capturas,
   respuestas, marcadores, lo que dijo ver, avance del protocolo, reportes,
   comentarios e historial); el sistema verifica que no quede ninguno y, si la
   verificación falla, no borra nada. Una sesión en curso no se elimina: primero
   se termina o se cancela.
3. Se genera un **acta** con el código de la sesión, la fecha, la cantidad de
   registros por tipo y el resultado de la verificación, sin datos personales.
   Pulsa **Imprimir acta** y entrega una copia si se pide. Las actas quedan en
   **Sesiones → Actas de eliminación**.
4. Si el formato tiene varios códigos, se repite por cada sesión.
5. Fuera del sistema:
   - Los **respaldos** cifrados anteriores siguen conteniendo los datos hasta
     que se eliminen; avisa al responsable técnico. `[Verificar con asesoría
     legal: tratamiento de los respaldos ante una cancelación.]`
   - Decide con la persona qué hacer con el formato firmado. `[Verificar con
     asesoría legal: si debe conservarse como prueba del consentimiento.]`

## Oposición y retiro de la autorización

1. Quien conduce no inicia sesiones nuevas con esa persona: cada sesión pide de
   nuevo la confirmación de la autorización, y sin ella no hay sesión.
2. Anota el retiro en el formato firmado (sección «Retiro de la autorización»).
3. Si la persona pide además que se borren sus datos, sigue «Cancelación» con
   cada código anotado.
4. Si la persona quiere volver a participar más adelante, firma un formato nuevo.

## Registro de las solicitudes

**EMOtv no tiene un registro de solicitudes de derechos.** La auditoría guarda
las acciones (impresión de un reporte, solicitud de eliminación, eliminación)
con fecha, cuenta e id del recurso, pero no la solicitud en sí. Cada solicitud
se anota en un registro institucional fuera del sistema, en
`[14: UBICACIÓN DEL REGISTRO DE SOLICITUDES]`, **sin nombres**: solo los códigos
de las sesiones.

| Campo | Ejemplo |
| --- | --- |
| N.° de solicitud | 2026-001 |
| Fecha de recepción | 2026-11-03 |
| Códigos de las sesiones | S-4F7K2Q, S-7KQ2MD |
| Quién la presenta | Persona adulta / padre, madre o tutor |
| Derecho | Acceso / rectificación / cancelación / oposición |
| ¿Se verificó la identidad? | Sí, con el formato firmado |
| Acción en EMOtv | Reporte impreso / versión nueva / eliminación (n.° de acta) |
| Fecha de respuesta | 2026-11-05 |
| Atendió | Docente (cargo, sin datos de la persona) |
| Observaciones | — |
