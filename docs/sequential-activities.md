# Actividades secuenciales

Una actividad puede tener varios pasos ordenados (`steps`). Cada paso indica una postura conocida por el validador, una instrucción y los segundos durante los que debe mantenerse. `repetitions` repite la secuencia completa. Las actividades antiguas sin `steps` siguen siendo válidas: se transforman internamente en un paso.

Las cinco posturas usadas por el catálogo (`arms_up`, `arms_open`, `arms_forward`, `hands_on_hips`, `squat`) tienen validadores predeterminados. La suite unitaria comprueba que todos los pasos de las actividades incluidas pueden validarse y completarse con landmarks sintéticos. Antes de usar estas reglas con personas se deben calibrar con vídeo real; en particular, `arms_forward` depende de la estimación de profundidad y `squat` solo reconoce una postura estática aproximada.

El progreso enviado por WebSocket corresponde a toda la secuencia; la sesión se completa únicamente después del último paso. La respuesta incluye `step_index`, `step_count` y `step` para mostrar y anunciar la instrucción actual. Si se pierde la postura durante un paso, solo se reinicia el tiempo de ese paso.

El catálogo incluye seis secuencias nuevas además de las tres actividades previas. La recomendación elige aleatoriamente entre candidatos configurados para la expresión detectada, evitando cuando sea posible la actividad usada en la sesión anterior del estudiante y la última elección para esa expresión. La elección se fija al asignarla a la sesión: los pasos no se barajan mientras se realiza el ejercicio. Las asociaciones entre expresión y actividad son demostrativas, no indicaciones clínicas.

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
