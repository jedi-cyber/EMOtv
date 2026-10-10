# Actividades secuenciales

Una actividad puede tener varios pasos ordenados (`steps`). Cada paso indica una postura conocida por el validador, una instrucción y los segundos durante los que debe mantenerse. `repetitions` repite la secuencia completa. Las actividades antiguas sin `steps` siguen siendo válidas: se transforman internamente en un paso.

Las cinco posturas usadas por el catálogo (`arms_up`, `arms_open`, `arms_forward`, `hands_on_hips`, `squat`) tienen validadores predeterminados. La suite unitaria comprueba que todos los pasos de las actividades incluidas pueden validarse y completarse con landmarks sintéticos. Antes de usar estas reglas con personas se deben calibrar con vídeo real; en particular, `arms_forward` depende de la estimación de profundidad y `squat` solo reconoce una postura estática aproximada.

La secuencia completa tiene `pasos × repeticiones` pasos y la sesión se completa únicamente después del último. El progreso enviado por WebSocket es global: `pasos completados / (pasos × repeticiones)`.

## Verificación de cada paso

- Solo se evalúa la postura del paso actual y solo ella hace avanzar su tiempo. Una postura válida para otro paso nunca cuenta.
- El tiempo de un paso se acumula únicamente entre frames consecutivos con la postura correcta.
- **Postura incorrecta con el cuerpo visible** (otra postura, brazos mal colocados): el tiempo del paso se **reinicia** a cero de inmediato. Los pasos ya completados se conservan.
- **Frames sin landmarks utilizables** (no se detecta a la persona o algún landmark necesario tiene `visibility` menor que `POSE_MIN_LANDMARK_VISIBILITY`): el tiempo se **pausa**, sin avanzar ni perderse. Si el hueco desde el último frame correcto supera `POSE_DROPOUT_TOLERANCE_SECONDS` (0,75 s por defecto, en `src/emotv/config.py`), el tiempo del paso se reinicia. Así un parpadeo de la detección no obliga a empezar el paso de nuevo.
- Mientras faltan landmarks, el mensaje pide al estudiante que se aleje un poco de la cámara y se centre, e indica qué partes del cuerpo deben verse.

Cada mensaje `status` incluye `step` (paso actual), `step_index` y `step_count` (índice global en la secuencia), `repetition_index` y `repetition_count`, `steps_completed`, `step_elapsed_seconds` y `step_remaining_seconds`. La web muestra «Paso X de Y» dentro de la repetición, «Repetición R de N», la instrucción, la postura esperada y el tiempo restante del paso. La voz anuncia cada cambio de paso una sola vez.

## Registro del avance

Al iniciar la actividad y en cada cambio de paso (no en cada frame) se guardan en la sesión `exercise_steps_completed`, `exercise_steps_total` (pasos × repeticiones), `exercise_repetitions` y `exercise_duration_seconds` (tiempo sostenido en postura correcta). Si la actividad se interrumpe por cancelación, desconexión o error, la sesión conserva hasta qué paso llegó. Al completarla, se registran los valores finales.

El catálogo incluye seis secuencias nuevas además de las tres actividades previas. La recomendación elige aleatoriamente entre candidatos configurados para la expresión detectada, evitando cuando sea posible la actividad usada en la sesión anterior del estudiante (según su historial de sesiones, no memoria del servidor). La elección se fija al asignarla a la sesión: los pasos no se barajan mientras se realiza el ejercicio. Las asociaciones entre expresión y actividad son demostrativas, no indicaciones clínicas.

Las asociaciones viven en la tabla `emotion_activity_recommendations` (migración `20261009_13`, sembrada con las que antes estaban en código) y administración las edita en **Administrar actividades → Actividades recomendadas por expresión** o con `PUT /recommendations/{expresión}`. Solo se aceptan actividades con al menos dos pasos; editar una actividad recomendada para dejarla con un paso devuelve `409` con las expresiones afectadas, y eliminarla la quita de sus asociaciones. Si aun así una asociación queda inválida, el recomendador la descarta con un aviso en el log; si una expresión se queda sin candidatos, el estudiante elige de la lista completa. Las tres actividades históricas de una postura siguen disponibles para selección manual. Para auditar el contenido realmente guardado en PostgreSQL:

```powershell
python scripts/audit_postgres_activities.py
```

El comando comprueba existencia, número de pasos y disponibilidad de validadores. `--repair` crea una secuencia recomendada ausente o restaura desde el catálogo local una que tenga menos de dos pasos; no modifica secuencias ya válidas.

Para PostgreSQL, aplicar `alembic upgrade head` antes de iniciar la API. La migración agrega `activities.steps` y crea las seis secuencias nuevas si sus identificadores aún no existen. No reemplaza actividades editadas por administración.

En administración se pueden editar los pasos de cada actividad. En el analizador web se anuncia cada paso mediante síntesis de voz del navegador si el usuario activó esa opción. La voz no forma parte del análisis de IA y puede no estar disponible en todos los navegadores.

## Repetir el reconocimiento

Al completar la actividad, el estudiante puede abrir el resultado de la sesión o pulsar **«Volver a analizar mi expresión»**. Esta última acción limpia la expresión, la recomendación, la actividad y el progreso anteriores; solicita de nuevo la cámara y crea otra sesión antes de reconocer la expresión. No modifica ni reutiliza la sesión completada. Si ya no hay consentimiento o el modelo dejó de estar disponible, el nuevo inicio queda sujeto a las mismas comprobaciones que cualquier análisis.

## Verificación

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe -m pytest tests\unit -q
cd web
npm test
npm run build
```

La migración debe ejecutarse contra la base indicada por `DATABASE_URL`; conviene revisar ese valor antes de aplicarla. El recorrido manual a comprobar en la web es: iniciar análisis → aceptar una actividad secuencial → completar todos sus pasos → volver a analizar → confirmar que la nueva sesión comienza sin datos del análisis previo.
