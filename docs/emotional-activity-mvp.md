# MVP de actividad emocional

## Objetivo

Esta etapa integra los módulos emocional y corporal en un único flujo local:

```text
cámara -> rostro -> emoción estable -> actividad recomendada
       -> postura objetivo -> ejercicio -> resultado en memoria
```

No incluye sesiones, base de datos, API nueva, aplicación móvil, ESP32-CAM ni
chatbot.

## Estado de la etapa

La implementación de software está completa. Las pruebas automatizadas están
aprobadas. Antes de declarar validado el MVP falta ejecutar y registrar una
prueba manual de extremo a extremo con webcam.

| Criterio | Estado | Implementación |
| --- | --- | --- |
| Detectar y clasificar un rostro | Implementado | YuNet, FER+ y ONNX Runtime |
| Estabilizar varias predicciones | Implementado | `EmotionStabilizer` |
| Recomendar una actividad | Implementado | `ActivityRecommendationService` |
| Mostrar instrucciones | Implementado | Script integrado |
| Detectar landmarks corporales | Implementado | MediaPipe Pose Landmarker |
| Validar la postura seleccionada | Implementado | `PostureValidator` |
| Medir tiempo y progreso | Implementado | `ExerciseService` |
| Generar resultado en memoria | Implementado | `build_final_result()` |
| Validación real con webcam | Pendiente manual | Protocolo descrito más abajo |
| Calibración con usuarios | Pendiente futura | Requiere muestra representativa |
| Revisión por Psicología | Pendiente futura | Asociaciones aún provisionales |

## Componentes

### Posturas

El registro de `PostureValidator` contiene:

- `arms_up`;
- `arms_open`;
- `hands_on_hips`.

`arms_forward` y `squat` tienen identificadores reservados, pero no son
necesarios para cumplir el objetivo de tres posturas de esta etapa.

### Actividades locales

`ActivityCatalog` contiene inicialmente:

- `arms_up_5s`;
- `arms_open_5s`;
- `hands_on_hips_5s`.

Todas utilizan una repetición basada en tiempo. Las repeticiones múltiples se
consideran una ampliación posterior.

### Estabilización emocional

`EmotionStabilizer` usa una ventana móvil y exige:

- siete observaciones como tamaño máximo de ventana;
- cinco muestras con confianza suficiente;
- confianza individual mínima de `0.5`;
- acuerdo mínimo de `0.6`;
- ausencia de empate en la emoción dominante.

Las predicciones de baja confianza ocupan espacio en la ventana para desplazar
resultados antiguos, pero no cuentan como votos.

### Recomendaciones provisionales

```text
sadness -> arms_up_5s, arms_open_5s
anger   -> arms_open_5s
neutral, happiness, surprise, disgust, fear, contempt -> sin actividad
```

Una emoción sin asociación no es un error: el controlador permanece en análisis
emocional. Estas reglas demuestran integración técnica y no representan una
prescripción psicológica.

### Controlador general

`EmotionalActivityService` implementa:

```text
ANALYZING_EMOTION
    -> ACTIVITY_SELECTED
    -> WAITING_FOR_POSTURE
    -> PERFORMING_EXERCISE
    -> COMPLETED
```

La actividad seleccionada se presenta antes de activar pose. Esto evita ejecutar
clasificación emocional y estimación corporal de manera constante al mismo
tiempo.

## Ejecutar el MVP

Con `.venv` activado y los tres modelos descargados:

```powershell
python scripts/run_emotional_exercise_test.py
```

Controles:

- `ESPACIO`: omitir la espera de instrucciones e iniciar la actividad;
- `R`: reiniciar emoción, actividad y ejercicio;
- `Q`: cerrar la prueba.

La actividad inicia automáticamente después de tres segundos. El valor se
configura mediante `EMOTIONAL_ACTIVITY_INSTRUCTION_SECONDS`.

## Resultado final

Al completar el ejercicio, el script conserva e imprime:

```python
{
    "initial_emotion": "sadness",
    "emotion_confidence": 0.78,
    "activity": "arms_up_5s",
    "exercise_result": "completed",
    "elapsed_seconds": 5.0,
}
```

No se guarda en disco ni en una base de datos.

## Protocolo de validación manual pendiente

1. Activar `.venv` y cerrar aplicaciones que usen la webcam.
2. Ejecutar `python scripts/run_emotional_exercise_test.py`.
3. Mantener el rostro visible hasta obtener una emoción estable con actividad.
4. Confirmar que se muestre nombre e instrucción de la actividad.
5. Realizar la postura indicada y comprobar esqueleto y reglas visuales.
6. Romper la postura antes de terminar y comprobar que el progreso vuelva a cero.
7. Mantener la postura durante cinco segundos y comprobar `COMPLETED`.
8. Verificar el resultado impreso en consola.
9. Pulsar `R` y confirmar que comienza una sesión local nueva.
10. Pulsar `Q` y comprobar que cámara y ventanas se liberen.

Conviene repetir el protocolo con diferentes distancias, fondos e iluminación y
anotar falsos positivos, falsos negativos y FPS observados.

## Criterio para cerrar la etapa

La etapa puede etiquetarse como validada cuando el protocolo manual se complete
sin errores bloqueantes. Después se podrá avanzar hacia sesiones, persistencia,
API e interfaces sin mezclar esas responsabilidades con este commit.
