# Catálogo informativo de expresiones

Después de registrar una expresión, el estudiante ve un resultado educativo con
información **fija y revisable**. La pantalla nunca llama al LLM. Emi, el
chatbot, queda para profundizar cuando el estudiante lo decida.

## Reparto de funciones

| Pantalla de resultado | Emi |
| --- | --- |
| Información base del catálogo, igual para todos | Responde preguntas adicionales |
| Textos redactados por el equipo y revisados por Psicología | Solo recibe lo que el estudiante escribe y envía |
| Sin datos personales | La pregunta sugerida no incluye confianza, fecha ni datos de la sesión |

El botón «Preguntar a Emi sobre esta expresión» abre el asistente con una
pregunta general y editable, por ejemplo «¿Qué diferencia hay entre la sorpresa
y el miedo en el rostro?». No se envía nada hasta que el estudiante pulsa
«Enviar».

## Contenido

Tabla `expression_info` (migración `20261008_12`), una fila por clase de FER+:
`neutral`, `happiness`, `surprise`, `sadness`, `anger`, `disgust`, `fear` y
`contempt`.

| Campo | Contenido |
| --- | --- |
| `label_es` | Etiqueta en español que usa toda la interfaz |
| `what_it_is` | Qué es la emoción |
| `why_it_occurs` | Por qué suele presentarse **en las personas en general**: función y situaciones habituales |
| `facial_cues` | Cómo se reconoce en el rostro: cejas, ojos, boca y duración típica |
| `practice_tip` | Sugerencia breve para practicar reconocerla o producirla |
| `limitation_note` | Limitación específica de esa expresión |
| `review_status` | `draft` o `reviewed`; con `reviewed` se registran `reviewed_by_user_id` y `reviewed_at` |

Bajo los textos se muestra siempre la limitación común:

> El reconocimiento facial estima una expresión a partir de la imagen y no
> determina por sí mismo el estado emocional ni psicológico de la persona.

Si `review_status` es `draft`, la pantalla añade la nota discreta «Contenido
pendiente de revisión por profesionales de Psicología».

## Reglas de redacción

- Cada campo tiene de 2 a 4 oraciones (entre 20 y 1200 caracteres).
- `why_it_occurs` explica por qué la emoción aparece en las personas en
  general, nunca por qué la siente el estudiante ni qué le pasa.
- Hablar de «expresión compatible con», nunca afirmar lo que la persona siente.
- Sin trastornos, diagnósticos ni consejos terapéuticos.
- La limitación menciona que la cultura, el contexto, la iluminación y el
  ángulo de la cámara influyen en el reconocimiento.
- Ningún LLM genera ni completa estos textos.

Los textos iniciales están en **borrador**: deben revisarlos profesionales de
Psicología. Las pruebas comprueban sobre la propia migración la cantidad de
oraciones, las palabras prohibidas y los factores de la limitación.

## Revisión y edición

La página **Catálogo de expresiones** (solo administración, `/admin/expressions`)
permite editar los textos. Al guardar:

- marcar «revisado por Psicología» registra quién y cuándo;
- guardar sin marcar deja el texto como borrador y elimina la revisión anterior,
  para que un cambio nunca quede como revisado sin una nueva revisión.

## Traducción en la interfaz

`web/src/expressions/ExpressionCatalog.tsx` centraliza las etiquetas: usa
`label_es` del catálogo y, si la API no responde, un respaldo local que solo
contiene etiquetas, nunca textos educativos. La fase en vivo, el resultado, el
historial y el detalle de sesión usan este módulo.
