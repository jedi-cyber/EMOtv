# Arquitectura de EMOtv

EMOtv utiliza una estructura por capas bajo `src/emotv`.

## Capas

### Dominio

Contiene modelos independientes de frameworks:

- `PoseLandmark` y `PoseLandmarks`: puntos corporales normalizados;
- `PoseResult`: resultado de una inferencia corporal;
- `PostureResult`: resultado conceptual de una postura;
- `Exercise` y `ExerciseStatus`: definición y estado de un ejercicio;
- `ExerciseState`: `incorrect`, `holding` o `completed`.

El dominio no importa OpenCV ni MediaPipe.

### Aplicación

- `PoseService`: coordina detección y validación de postura.
- `ExerciseService`: máquina de estados que mide el tiempo sostenido y entrega
  un progreso entre `0.0` y `1.0`.

### Infraestructura

- `OpenCVCamera`: convierte webcam u otra fuente compatible en frames BGR.
- `PoseDetector`: adapta MediaPipe al modelo corporal del dominio.
- `PostureValidator`: aplica reglas geométricas configurables.
- `calculate_angle`: calcula el ángulo de tres landmarks.
- módulos existentes de detección facial y clasificación emocional.

### Interfaces

- `PoseDrawer`: dibuja landmarks sin conocer cómo fueron detectados.
- scripts interactivos de cámara, pose, postura y ejercicio.
- aplicación web existente para el flujo emocional.

## Flujo corporal

```text
OpenCVCamera
    -> frame BGR
    -> PoseDetector (MediaPipe)
    -> PoseResult / PoseLandmarks
    -> PostureValidator
    -> ExerciseService
    -> ExerciseStatus
    -> PoseDrawer + interfaz
```

Esta separación permite sustituir la webcam por video, teléfono o ESP32-CAM
si la nueva fuente continúa entregando un `numpy.ndarray` BGR válido.

## Decisiones relevantes

- Los pesos se guardan fuera del paquete, bajo `models/weights/`, y no se
  versionan en Git.
- MediaPipe trabaja en modo `VIDEO` con timestamps monotónicos para aprovechar
  el seguimiento entre frames.
- Solo se transforma al dominio el subconjunto de landmarks necesario.
- `completed` es terminal hasta que se llama a `ExerciseService.reset()`.
- La pérdida de la postura durante `holding` reinicia tiempo y progreso.
- Las reglas corporales permanecen separadas de la captura y del dibujo.
