# Reconocimiento de emociones: «¿Qué emoción es?»

Un paso del protocolo que practica el **reconocimiento** de emociones. Se muestra
una imagen emocional del banco y la persona elige qué emoción es entre unas pocas
opciones. Después lee el nombre de la emoción de la imagen y el paso avanza solo.

Complementa la [práctica de producción de expresiones](expression-practice.md).
Primero se reconoce la emoción en otra cara y después se produce con la propia.
Las dos sirven al objetivo del proyecto: psicoeducación sobre el reconocimiento
emocional en la niñez y en personas con condiciones que dificultan procesar
emociones. Quien conduce la sesión es el Usuario (estudiante de Psicología) y el
Docente revisa los resultados.

## Reglas

- **No analiza la cámara.** En este paso la pantalla de la persona no envía
  cuadros: se mide la respuesta, no la expresión del rostro.
- **Describe, no valora.** Tras responder, la persona lee solo el nombre de la
  emoción de la imagen («Es tristeza»), acierte o no. Tampoco se dice
  «correcto» o «incorrecto». Los reportes dicen qué ocurrió, por ejemplo
  «Eligió la emoción de la imagen en 3 de 4 ejercicios».
- **No es una evaluación.** Todo resultado lleva un aviso fijo: una sesión
  breve no permite sacar conclusiones sobre cómo reconoce emociones la persona.
  No hay puntajes ni seguimiento por persona.
- **La respuesta la decide la imagen.** El servidor copia la expresión esperada
  de la imagen emocional; quien arma el protocolo no la escribe. Una imagen sin
  expresión esperada (abstracta o propia sin indicarla) no sirve para este
  paso.

## Armado del protocolo

En el editor de protocolos se elige una imagen y se pulsa **Agregar como «¿Qué
emoción es?»**. Solo hay dos ajustes, ya propuestos:

| Ajuste | Por defecto | Límites |
| --- | --- | --- |
| Opciones | 3 | 2 a 4 |
| Tiempo para responder | 15 s | 1 a 120 s |

Las opciones se eligen solas. Siempre está la emoción de la imagen y el resto
son distractoras tomadas de alegría, tristeza, enojo, miedo, sorpresa, asco y
cara tranquila. Desprecio solo aparece cuando es la respuesta, porque es poco
común y difícil de nombrar para un niño. El orden y las distractoras dependen
de la sesión y del paso, así que cada consulta muestra las mismas.

Con niños rige la misma regla de siempre: solo imágenes «Para niños» leves y
aprobadas.

### Situaciones

El paso admite una **situación** opcional: una historia corta de hasta 200
caracteres que acompaña a la ilustración, por ejemplo «A Lucía se le cayó su
helado al piso». Con ella la pregunta pasa a ser «¿Cómo se siente?». La
respuesta sigue siendo la expresión esperada de la imagen, así que la
ilustración debe mostrar la escena con esa emoción.

El texto lo escribe quien arma el protocolo y se guarda con el paso
(`protocol_steps.situation`, migración `20261102_32_recognition_situations`).
Debe usar nombres inventados: el servidor rechaza una situación con DNI,
correos o teléfonos, con el mismo filtro que usa Emi. Los resultados se
registran igual que en cualquier reconocimiento.

### Modo accesible

Se activa en el protocolo con la casilla **Modo accesible**, debajo del público
(`protocols.accessible`, migración `20261102_33_accessible_protocols`). Está
pensado para quienes se saturan con facilidad y cambia solo la presentación:

- La pantalla de la persona muestra un pictograma junto al nombre de cada
  emoción. El nombre sigue siendo la etiqueta del botón; el pictograma es un
  apoyo visual, no una imagen de nadie ni de lo detectado.
- Botones y letra más grandes, y nada se mueve (sin animaciones ni
  transiciones). La aplicación no usa sonidos.
- La pausa tras cada reconocimiento o ejercicio dura el doble
  (`ACCESSIBLE_PAUSE_FACTOR`).
- En el editor, los pasos nuevos proponen 2 opciones y 30 s para responder, y
  el doble del tiempo máximo en una práctica. Se pueden cambiar.

Lo que se registra y se reporta no cambia. Quien conduce ve «modo accesible»
en el encabezado del paso.

## En la sesión

1. Va después de la calibración, como los demás pasos durante el analizador.
2. **Pantalla de la persona.** Muestra la imagen, la situación si la hay, la
   pregunta («¿Qué emoción es?» o «¿Cómo se siente?») y un botón grande por
   opción. Al tocar uno se envía
   `POST /participant-view/{token}/answer`.
3. **Quien conduce.** Ve la emoción de la imagen, la situación y las mismas
   opciones. Si la
   persona señala o dice su respuesta, la registra con
   `POST /guided-sessions/{id}/recognition`.
4. Tras la respuesta, o al vencer el tiempo, la persona lee el nombre de la
   emoción durante la pausa (`PRACTICE_STEP_PAUSE_SECONDS`, 2 s por defecto) y
   el paso avanza solo.
5. Saltar el paso o detener la sesión queda registrado como tal.

## Qué se guarda

Tabla `recognition_results` (migración `20261102_31_recognition_steps`), una
fila por paso y sesión:

| Campo | Contenido |
| --- | --- |
| `stimulus_id`, `target_expression` | la imagen y su expresión esperada |
| `options` | las opciones mostradas, en orden |
| `outcome` | `answered`, `timed_out`, `skipped` o `stopped` |
| `chosen_expression` | la opción elegida (solo si respondió) |
| `seconds_to_answer` | segundos desde que apareció la imagen |
| `answered_by` | `participant` (tocó la pantalla) o `conductor` (lo registró quien conduce) |
| `started_at`, `ended_at` | inicio y fin del paso |

No guarda imágenes, cuadros de la cámara ni datos de la persona. La retención
y la eliminación por sesión incluyen esta tabla. `protocol_steps` agrega
`option_count` y el tipo `recognition`.

## Reporte y estadísticas

- **Métricas y reporte** (`GET /sessions/{id}/metrics`, bloque `recognition`).
  Incluyen la frase, cada paso con sus opciones y lo elegido, y el desglose por
  emoción de la imagen con lo que se eligió en su lugar, contado. Va aparte de
  la coincidencia de la expresión estimada: las imágenes de un reconocimiento
  no cuentan allí.
- **Línea de tiempo.** Cada reconocimiento aparece con `kind` `recognition` y
  la opción elegida.
- **Estadísticas** (`GET /statistics`, bloque `recognition`). Totales y
  desglose por emoción de la imagen, contando sesiones y nunca personas. Un
  paso que terminó sin respuesta cuenta como no elegido. Los saltados y los
  detenidos se informan aparte.
- **API móvil 4.2.** `GET /mobile/sessions/{id}` trae `metrics.recognition` y
  `GET /mobile/statistics` trae `recognition`. Son campos opcionales: ver
  [mobile-api.md](mobile-api.md).
