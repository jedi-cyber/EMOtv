# Procedimiento para atender los derechos de los participantes

> Sujeto a revisión de la Facultad. Describe cómo se atiende cada solicitud con
> las funciones que hoy tiene EMOtv. **No fija plazos de respuesta**: los plazos,
> la forma de la solicitud y la respuesta ante una negativa dependen de la Ley
> N.° 29733 y del D.S. 016-2024-JUS y deben **verificarse con asesoría legal**.

## Quién atiende

- Las solicitudes llegan a `[3: CONTACTO PARA EJERCER DERECHOS]` o al docente
  responsable.
- **Las atiende el docente** a cargo del usuario que registró al participante
  (o el propio docente, si él lo registró): es la única cuenta, junto con quien
  registró, que puede ver y eliminar los datos (ver [matriz-de-accesos.md](matriz-de-accesos.md)).
  La administración y el soporte técnico **no pueden** atenderlas dentro del
  sistema, porque no acceden a participantes.
- Puede pedirlo el participante adulto o, si es un niño, su padre, madre o tutor.

## Paso 0: identificar al participante

EMOtv no conoce nombres. El docente:

1. Pide a la persona su copia del formato firmado o la ficha con el código.
2. Comprueba en la ficha de papel que custodia (`[10: LUGAR DE CUSTODIA]`) que el
   código corresponde a quien lo pide y, si es un niño, que quien pide es su
   padre, madre o tutor. `[Verificar con asesoría legal: cómo acreditar la
   identidad y la representación.]`
3. Busca el código en **Participantes**.

Si no se puede verificar, no se entregan datos ni se elimina nada; se anota en el
registro de solicitudes.

## Acceso

Qué entrega EMOtv: el **reporte aprobado** de cada sesión, impreso. Incluye el
código, la fecha, el modelo usado, la línea de tiempo (estímulos, expresiones
estimadas, cuestionarios con sus respuestas, lo que dijo ver y los marcadores),
las métricas, las respuestas a los cuestionarios y el texto del reporte, con el
aviso de que las expresiones son estimaciones.

1. Para cada sesión del participante, abre su reporte. Si no existe, redáctalo o
   pide a quien condujo que lo redacte; si está en revisión, revísalo y apruébalo
   (el reporte de un docente se cierra sin revisión).
2. En el reporte aprobado, pulsa **Vista imprimible** y luego **Imprimir
   reporte**. El sistema registra la impresión en la auditoría y en el historial
   del reporte.
3. Entrega la copia en mano a la persona. No hay portal para participantes ni
   envío por correo desde el sistema.
4. Datos que **no salen en el reporte** y que el docente puede mostrar en
   pantalla si se piden: la edad, las notas libres del participante y las
   autorizaciones registradas (versión, fecha, casillas). El sistema no tiene una
   vista imprimible de esos datos.

## Rectificación

**Limitación actual del sistema:** una vez registrados, **no existe una función
para corregir** la edad, las notas del participante, las respuestas a
cuestionarios, los marcadores, lo que dijo ver ni las expresiones estimadas.

Lo que sí se puede hacer:

| Dato | Cómo se corrige |
| --- | --- |
| Texto del reporte | Si está en borrador o con observaciones, quien lo redactó lo edita. Si está aprobado, **Crear versión nueva**, corregir y volver a aprobar; la versión anterior queda reemplazada |
| Autorizaciones | Se registra un formato nuevo (**Registrar autorización**); el sistema usa la más reciente. Si se retiró una autorización, no se registran nuevas |
| Edad, notas, respuestas u otros registros | Solo eliminando al participante con acta (ver «Cancelación») y, si la persona quiere seguir, registrándolo de nuevo con un código nuevo |

`[Verificar con asesoría legal: si esta forma de rectificación es suficiente o si
el sistema debe permitir corregir esos datos.]`

## Cancelación (eliminación)

1. Si el participante lo registró un usuario, ese usuario pulsa **Solicitar
   eliminación** en **Participantes**. El docente también puede eliminar sin
   solicitud previa.
2. El docente pulsa **Eliminar** y confirma. En una sola transacción se borran el
   participante y todos sus registros (autorizaciones, sesiones, capturas,
   respuestas, marcadores, lo que dijo ver, sesión guiada, reportes, comentarios
   e historial); el sistema verifica que no quede ninguno y, si la verificación
   falla, no borra nada.
3. Se genera un **acta** con el código, la fecha, la cantidad de registros por
   tipo y el resultado de la verificación, sin datos personales. Pulsa
   **Imprimir acta** y entrega una copia si se pide.
4. Fuera del sistema:
   - Los **respaldos** cifrados anteriores siguen conteniendo los datos hasta
     que se eliminen; avisa al responsable técnico. `[Verificar con asesoría
     legal: tratamiento de los respaldos ante una cancelación.]`
   - Decide con la persona qué hacer con la **ficha de papel** y el formato
     firmado. `[Verificar con asesoría legal: si deben conservarse como prueba
     del consentimiento.]`

## Oposición y retiro de la autorización

1. En **Participantes → Autorizaciones**, pulsa **Registrar retiro**, indica quién
   retira (el participante o el tutor) y qué retira (participación, cámara o
   asentimiento) y pulsa **Confirmar retiro**.
2. Desde ese momento el sistema **no permite sesiones nuevas** con ese
   participante ni registrar autorizaciones nuevas, y lo marca para que el
   docente decida su eliminación.
3. Si la persona pide además que se borren sus datos, sigue «Cancelación».
4. Si la persona quiere volver a participar más adelante, se registra con un
   código nuevo y un formato nuevo.

## Registro de las solicitudes

**EMOtv no tiene un registro de solicitudes de derechos.** La auditoría guarda
las acciones (impresión de un reporte, solicitud de eliminación, eliminación,
retiro de autorización) con fecha, cuenta e id del recurso, pero no la
solicitud en sí. Cada solicitud se anota en un registro institucional fuera del
sistema, en `[14: UBICACIÓN DEL REGISTRO DE SOLICITUDES]`, **sin nombres de
participantes**: solo el código.

| Campo | Ejemplo |
| --- | --- |
| N.° de solicitud | 2026-001 |
| Fecha de recepción | 2026-11-03 |
| Código del participante | P-7KQ2MD |
| Quién la presenta | Participante adulto / padre, madre o tutor |
| Derecho | Acceso / rectificación / cancelación / oposición |
| ¿Se verificó la identidad? | Sí, con la ficha de papel |
| Acción en EMOtv | Reporte impreso / versión nueva / eliminación (n.° de acta) / retiro registrado |
| Fecha de respuesta | 2026-11-05 |
| Atendió | Docente (cargo, sin datos del participante) |
| Observaciones | — |
