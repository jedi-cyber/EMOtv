# Arquitectura de EMOtv

EMOtv utiliza una estructura por capas bajo `src/emotv`.

## Capas

### Dominio

Contiene modelos independientes de frameworks:

- `PoseLandmark` y `PoseLandmarks`: puntos corporales normalizados;
- `PoseResult`: resultado de una inferencia corporal;
- `PostureId`: identificadores estables para seleccionar posturas;
- `PostureResult`: resultado genérico con confianza, mediciones y reglas
  incumplidas;
- `Activity`: instrucción local asociada a una postura, duración y repeticiones;
- `Exercise` y `ExerciseStatus`: definición y estado de un ejercicio;
- `ExerciseState`: `incorrect`, `holding` o `completed`.

El dominio no importa OpenCV ni MediaPipe.

### Aplicación

- `PoseService`: coordina detección y validación de postura.
- `ExerciseService`: máquina de estados que mide el tiempo sostenido y entrega
  un progreso entre `0.0` y `1.0`.
- `ActivityCatalog`: catálogo local consultable y administrable, protegido
  contra IDs duplicados y accesos concurrentes.
- `EmotionStabilizer`: obtiene una emoción dominante desde una ventana móvil,
  aplicando confianza mínima, muestras mínimas y acuerdo mínimo.
- `ActivityRecommendationService`: traduce una emoción estabilizada a una
  actividad del catálogo mediante reglas locales provisionales.
- `EmotionalActivityService`: controlador de estados que coordina clasificación,
  estabilización, recomendación, pose y progreso sin asumir una interfaz.

### Infraestructura

- `OpenCVCamera`: convierte webcam u otra fuente compatible en frames BGR.
- `PoseDetector`: adapta MediaPipe al modelo corporal del dominio.
- `PostureValidator`: despacha por `PostureId` hacia evaluadores registrados y
  devuelve un `PostureResult` genérico. `both_arms_up()` permanece como API de
  compatibilidad.
- `calculate_angle`: calcula el ángulo de tres landmarks.
- módulos existentes de detección facial y clasificación emocional.
- adaptadores PostgreSQL para sesiones, usuarios, estudiantes y consentimientos;
- modelos ORM y migraciones Alembic, aislados del dominio.

### Interfaces

- `PoseDrawer`: dibuja landmarks sin conocer cómo fueron detectados.
- scripts interactivos de cámara, pose, postura y ejercicio.
- aplicación web existente para el flujo emocional.
- routers FastAPI para autenticación, sesiones y actividades.

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

Esta separación permite sustituir la webcam por otra fuente compatible si
continúa entregando un `numpy.ndarray` BGR válido. El alcance vigente utiliza
webcam y no contempla ESP32-CAM.

## Flujo emocional integrado

`scripts/run_emotional_exercise_test.py` ejecuta localmente las fases de forma
secuencial para no inferir emoción y pose de manera constante al mismo tiempo:

```text
rostro -> emoción estable -> actividad seleccionada -> instrucción
       -> postura objetivo -> progreso -> resultado final en memoria
```

## Flujo de sesiones

La emoción se estima a partir del rostro. El cuerpo se utiliza exclusivamente
para guiar y validar posturas de las actividades; no se infieren emociones a
partir de landmarks corporales.

```text
EmotionalActivityService
    -> EmotionalActivityStatus
    -> SessionService
    -> EmotionalSession
    -> SessionRepository
    -> InMemorySessionRepository
```

`SessionState` representa los estados `created`, `in_progress`, `completed` y
`cancelled`. `SessionService` controla IDs, timestamps y transiciones y depende
del puerto `SessionRepository`, nunca del adaptador concreto. El repositorio en
memoria puede sustituirse por `PostgresSessionRepository` sin modificar la
visión artificial. `SessionRecord` es el modelo ORM y permanece dentro de
infraestructura.

La implementación y su auditoría están descritas en
[Sesiones y persistencia](sessions.md).

## API, identidad y autorización

FastAPI actúa como adaptador de entrada. `AuthenticationService` emite y valida
tokens JWT a partir del flujo OAuth2 password. `AuthorizationService` aplica
permisos mediante `Role` y `AccessAction`; las comprobaciones de propiedad se
realizan antes de invocar operaciones sensibles.

```text
HTTP -> router -> autenticación/autorización -> servicio de aplicación
                                                -> puerto -> PostgreSQL
```

`SessionService` permanece independiente de FastAPI y SQLAlchemy. El filtro por
estudiante forma parte de `SessionRepository`, por lo que PostgreSQL realiza la
selección sin cargar todas las sesiones. El catálogo de actividades todavía es
local: los cambios hechos mediante la API duran hasta reiniciar el proceso.

Las reglas preliminares de acceso, retención, consentimiento y eliminación se
encuentran en [Privacidad y gobierno de datos](privacy-data-governance.md).

## Decisiones relevantes

- Los pesos se guardan fuera del paquete, bajo `models/weights/`, y no se
  versionan en Git.
- MediaPipe trabaja en modo `VIDEO` con timestamps monotónicos para aprovechar
  el seguimiento entre frames.
- Solo se transforma al dominio el subconjunto de landmarks necesario.
- `completed` es terminal hasta que se llama a `ExerciseService.reset()`.
- La pérdida de la postura durante `holding` reinicia tiempo y progreso.
- Las reglas corporales permanecen separadas de la captura y del dibujo.
- Las asociaciones emoción–actividad son configuración provisional y no una
  recomendación clínica.
- El resultado integrado permanece en memoria durante esta etapa.
- `EmotionalActivityService` no depende de sesiones ni persistencia.
- Ningún detector o validador corporal conoce el repositorio de sesiones.

El alcance y el protocolo de validación están documentados en
[MVP de actividad emocional](emotional-activity-mvp.md).
