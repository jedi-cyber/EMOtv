# Arquitectura de EMOtv

EMOtv tiene dos piezas que se despliegan por separado:

- **Frontend** React + TypeScript + Vite en `web/`. Obtiene la cámara en el
  navegador con `getUserMedia` y envía frames JPEG por WebSocket.
- **Backend** FastAPI en `src/emotv/` (`emotv.interfaces.web.app:app`), con
  PostgreSQL + Alembic como única base de datos.

**El servidor nunca abre una cámara física.** Recibe frames, los procesa en
memoria y los descarta; no guarda fotografías ni video.

Las versiones visuales de estos diagramas están en
[thesis-evidence/diagrams/](thesis-evidence/diagrams/). Si difieren, la fuente
de verdad son el código y las migraciones.

## Diagrama del sistema

```mermaid
flowchart LR
  subgraph Cliente["Equipo del estudiante"]
    CAM["Cámara<br/>getUserMedia"] --> SPA["SPA React + Vite<br/>web/"]
  end
  subgraph Docker["Docker Compose"]
    WEB["web: nginx<br/>estáticos + proxy"]
    API["api: FastAPI<br/>emotv.interfaces.web.app"]
    MOD["models: descarga pesos<br/>y mide el benchmark"]
    DB[("db: PostgreSQL 16<br/>migraciones Alembic")]
    VOL[["volumen emotv_models<br/>YuNet · FER+ · MediaPipe"]]
  end
  subgraph Externo["Servicios externos"]
    N8N["n8n Cloud<br/>workflow «Version 1.0 EMI»"]
    GROQ["Groq (LLM)"]
  end
  SPA -->|"REST /auth /sessions /students ..."| WEB
  SPA -->|"WebSocket /ws/activity<br/>frames JPEG, sin guardar"| WEB
  WEB --> API
  API --> DB
  MOD --> VOL
  VOL -->|solo lectura| API
  API -->|"POST + X-EMOtv-Key<br/>pregunta, historial, conocimiento"| N8N
  N8N --> GROQ
```

Dentro de la API, cada frame recorre esta cadena:

```text
Navegador (getUserMedia)
    -> JPEG por WebSocket /ws/activity (token, sesión, actividad)
    -> EmotionFrameAnalyzer: YuNet (rostro) + HSEmotion o FER+ ONNX (expresión y distribución)
    -> LiveExpressionTracker (EmotionStabilizer, calibración neutral opcional en memoria):
       lectura en vivo, nada persistido
    -> el estudiante confirma -> SessionService.record_recognition (expresión elegida)
    -> ActivityRecommendationService (2+ posturas) -> actividad u omitirla
    -> PoseService: MediaPipe + PostureValidator (solo posturas)
    -> BrowserActivityService -> progreso y estado al navegador
    -> SessionService -> PostgreSQL (resultado, sin imágenes)
```

## Flujo del estudiante

```mermaid
flowchart TD
  L["Inicio de sesión"] --> P{"¿Contraseña<br/>provisional?"}
  P -- sí --> FA["Primer acceso:<br/>cambia la contraseña"] --> C
  P -- no --> H["Inicio"]
  H --> C{"¿Consentimiento<br/>vigente?"}
  C -- no --> CP["Consentimiento:<br/>lee y acepta la política"] --> AN
  C -- sí --> AN["Analizador: guía previa<br/>y requisitos (cámara,<br/>consentimiento, servicio)"]
  AN --> LV["Lectura en vivo<br/>de la expresión"]
  LV --> RG["Registra la expresión<br/>(estable y con confianza suficiente)"]
  RG --> RS["Resultado educativo:<br/>expresión en español, confianza,<br/>información y limitación"]
  RS --> D{"¿Hace la actividad?"}
  D -- "no" --> FIN["Finaliza sin actividad<br/>(la expresión queda guardada)"]
  D -- "sí" --> AC["Actividad de 2+ posturas:<br/>cada paso se verifica con MediaPipe"]
  AC --> OK["Actividad completada<br/>o cancelada"]
  FIN --> HS["Mis sesiones / detalle"]
  OK --> HS
  RS -. "opcional" .-> EMI["Emi: preguntas educativas<br/>(sin resultados personales)"]
```

En cualquier momento el estudiante puede revocar el consentimiento: los
análisis nuevos quedan bloqueados y las sesiones registradas se conservan.
Salir de la página, cancelar o terminar apaga la cámara.

La expresión se estima solo a partir del rostro. El cuerpo se usa
exclusivamente para verificar posturas; nunca se infieren emociones desde los
landmarks corporales. El resultado es una estimación de la expresión facial, no
un diagnóstico.

## Capas

### Dominio (`emotv.domain`)

Modelos independientes de frameworks: `PoseLandmark(s)`, `PoseResult`,
`PostureId`, `PostureResult`, `Activity` y sus pasos, `ExerciseStatus`,
`StabilizedEmotion`, `EmotionalSession` y `SessionState`, `User`, `Role`,
`Student`, consentimientos y `PsychologistAssignment`. El dominio no importa
OpenCV, MediaPipe, SQLAlchemy ni FastAPI.

### Aplicación (`emotv.application`)

- `BrowserActivityService`: coordina los frames del navegador con la actividad
  y entrega el estado de cada paso.
- `PoseService` y `ExerciseService`: validación de postura y tiempo sostenido.
- `EmotionStabilizer`: emoción dominante en una ventana móvil con confianza,
  muestras y acuerdo mínimos.
- `ActivityRecommendationService` y `ActivityCatalog`: asociaciones
  expresión → actividad leídas de PostgreSQL (`emotion_activity_recommendations`)
  en cada recomendación, sin estado en memoria. Descarta con un aviso en el log
  las actividades inexistentes o de un solo paso y nunca interrumpe el análisis.
  No son una recomendación clínica. `RecommendationConfigService` valida su
  edición por administración.
- `EmotionModelCatalog` y el contrato `EmotionClassifier`.
- `evaluate_resources`: política de admisión `SUPPORTED`/`WARNING`/`BLOCKED`.
- `SessionService`, `AuthenticationService`, `AuthorizationService`,
  `ConsentPolicyService`, `IdentityRegistrationService` y `LoginThrottle`.
- Puertos (`application.ports`) para repositorios de sesiones, actividades,
  usuarios, estudiantes, consentimientos, asignaciones e intentos de login.

### Infraestructura (`emotv.infrastructure`)

- `vision.face_detection.YuNetFaceDetector` (`face_detection_yunet_2026may.onnx`).
- `vision.emotion_classifier`: FER+ ONNX, HSEmotion ONNX (lectura en vivo
  predeterminada si su admisión es válida), HardlyHumans ViT
  (experimental, extra `emotion-vit`), fábrica, `EmotionFrameAnalyzer` y
  `ServerModelAdmission`.
- `vision.pose_detection.PoseDetector` (MediaPipe en modo `VIDEO`) y
  `vision.movement_analysis` (`PostureValidator`, ángulos).
- `persistence`: adaptadores PostgreSQL y en memoria, modelos ORM y conexión.
- `chat.N8nWebhookChatGateway` para Emi: llama al workflow EMI de n8n Cloud,
  que usa Groq. Nunca recibe resultados personales ni identificadores del
  usuario. Ver [chatbot-emi.md](chatbot-emi.md).

### Interfaces (`emotv.interfaces.web`)

- Routers de autenticación, identidades, sesiones, actividades, análisis y chat.
- `WebSocket /ws/activity`: autenticación en el primer mensaje, propiedad de la
  sesión, consentimiento vigente, admisión del modelo y limpieza al cerrar.
- `GET /` devuelve un estado simple; `GET /health` comprueba base de datos y
  pesos para Docker.
- Seguridad HTTP: CORS, hosts de confianza, cabeceras y validación de Origin.

## Modelo facial

En la lectura en vivo, el servidor elige el modelo: HSEmotion
(`hsemotion_enet_b0_8_best_afew`) si su admisión es válida y, si no, FER+
(`ferplus_onnx`). Solo administración consulta `GET /analysis/models` y puede
forzar otro `emotion_model_id` en el WebSocket; si un estudiante pide un modelo
distinto de esos dos, el servidor lo rechaza con `4403`. La UI oculta el
selector a estudiantes, pero la restricción se aplica en FastAPI. Cada
clasificador declara su propio recorte (margen, tamaño y color) según su fuente.

Antes de cargar el clasificador, el WebSocket vuelve a evaluar la admisión del
modelo: un cliente no puede evitar el bloqueo manipulando la interfaz y no hay
fallback silencioso. Una evaluación ausente, insuficiente o vencida bloquea
incluso FER+, y el motivo llega al navegador como mensaje de error. Tras cargar
el clasificador se registran `emotion_model_id` y `emotion_model_version` en la
sesión. La inferencia ocurre en el servidor, así que su capacidad es la que
determina la admisión. Véanse [condiciones actuales](emotion-model-candidates.md)
y [trabajo pendiente](adaptive-emotion-models-plan.md).

## Protección de carga del análisis

La lectura en vivo y la actividad no pueden dejar sin recursos al resto del
servidor. Nada de esto cambia el modelo ni el umbral de registro.

- **Un cuadro a la vez por sesión.** El navegador envía el siguiente cuadro solo
  después de recibir la respuesta al anterior, como máximo uno cada 250 ms
  (4 por segundo). Si el servidor tarda más, la frecuencia baja sola. Con la
  pestaña oculta no envía nada. En el servidor, una tarea lee el socket sin
  esperar al análisis y **descarta** cualquier cuadro que llegue mientras otro
  está pendiente o en análisis; las instrucciones (registrar, calibrar,
  cancelar) sí se procesan en orden. Nunca se forma una cola de cuadros.
- **Cupos** (`interfaces/web/analysis_capacity.py`, por proceso de la API):
  `MAX_ACTIVE_SESSIONS` conexiones de análisis abiertas y
  `MAX_CONCURRENT_ANALYSES` cuadros analizándose a la vez (por defecto, núcleos
  − 1, mínimo 1). Sin cupo, la sesión espera `ANALYSIS_BUSY_WAIT_SECONDS`; si
  sigue sin cupo, recibe "El servidor está ocupado; intenta de nuevo en un
  momento", se cierra con el código 1013 y se libera.
- **Pool propio.** La decodificación del JPEG y el análisis corren en un
  `ThreadPoolExecutor` dedicado, fuera del bucle de eventos: el login, la API
  y el chat siguen respondiendo aunque el análisis esté saturado.
- **Hilos por sesión.** Cada clasificador se carga una vez por proceso y lo
  comparten las sesiones (las sesiones ONNX admiten llamadas concurrentes); cada
  análisis usa `ONNX_THREADS_PER_SESSION` hilos de onnxruntime (1 por defecto) y
  `MAX_CONCURRENT_ANALYSES` limita cuántos corren a la vez, así varias sesiones
  no compiten por todos los núcleos. HardlyHumans (PyTorch) y YuNet (OpenCV) no
  usan este límite.
- **Inactividad.** Si no llegan cuadros durante `LIVE_IDLE_TIMEOUT_SECONDS`
  (60) mientras se esperan, el servidor cierra con el código 4408 y libera la
  sesión y su cupo. Mientras el estudiante revisa su resultado no se esperan
  cuadros y no se aplica.
- **Docker.** El servicio `api` tiene `cpus` (`API_CPUS`, 3) y `mem_limit`
  (`API_MEMORY_LIMIT`, 2560 MiB) para dejar recursos a `db` y `web`; ver
  [docker.md](docker.md#consumo-medido).
- **Benchmark.** `run_emotion_models_benchmark.py` mide también el cuadro
  completo con 1, 2 y 4 sesiones simultáneas. El superadministrador ve ese p95
  en la página «Modelos». Es solo informativo: no cambia el modelo
  ni bloquea nada. Si HSEmotion queda bloqueado por CPU o RAM, la admisión ya
  hace que la lectura en vivo use FER+.

## Práctica de expresiones

Un ejercicio de práctica es un paso del protocolo (`ProtocolStep` con
`kind = "practice"`) que corre dentro de la fase `STIMULI` de la sesión guiada.
Detalle, diferencias con el diseño y pendientes en
[expression-practice.md](expression-practice.md).

```text
ParticipantViewPage --(un cuadro a la vez, cada 500 ms)--> POST /participant-view/{token}/frames
  -> AnalysisCapacity.try_run (sin cupo: el cuadro se descarta)
  -> GuidedSessionService: YuNet + modelo local -> distribución (imagen descartada)
  -> PracticeTracker (nivel EMA, histéresis, sostén; memoria constante)
  -> al terminar: PracticeResult -> practice_results
```

- **Capas.** `domain.protocol` define el paso y sus límites;
  `domain.guided_session`, `PracticeResult`, `PracticeOutcome`, instrucciones y
  `PRACTICE_NOTICE`. `application.practice_tracker` es puro (sin reloj propio
  ni repositorios). `GuidedSessionService` mantiene el tracker en memoria, junto
  a la calibración neutral, y guarda solo el resultado.
  `session_metrics`, `session_insights_service` y `session_statistics_service`
  lo resumen sin puntajes ni valoraciones.
- **Lo que sale del servidor.** El nivel en vivo solo llega a las dos pantallas
  de la sesión: la persona ve la instrucción, la señal (si quien conduce no la
  apagó) y el logro; quien conduce ve además el tiempo restante. Nunca la
  expresión detectada ni probabilidades.
- **Validación.** `PracticeValidationService` agrega el protocolo «Validación
  con adultos» a cuentas `PRUEBA-NN` en modo demo y arma en memoria el CSV
  agregado para administración (`/practice-validation/...`).

## Sesiones, identidad y autorización

```text
HTTP/WS -> router -> autenticación/autorización -> servicio de aplicación
                                                  -> puerto -> PostgreSQL
```

`AuthorizationService` aplica permisos por `Role` y `AccessAction`, con
comprobación de propiedad para estudiantes y de asignación explícita para
Psicología. Toda restricción se aplica en FastAPI, no solo ocultando botones.
`SessionService` es independiente de FastAPI y SQLAlchemy; el filtro por
estudiante forma parte de `SessionRepository`. Detalles en
[Sesiones y persistencia](sessions.md) y
[Privacidad y gobierno de datos](privacy-data-governance.md).

## Pesos de modelos

Los pesos viven en `models/weights/` y no se versionan. `scripts/download_models.py`
es la única descarga de los modelos requeridos (YuNet 2026may, FER+ y
MediaPipe Pose) y de HSEmotion, que es opcional (si falta, se usa FER+);
verifica SHA-256 y es idempotente. En Docker lo ejecuta el
servicio `models` sobre su volumen antes de arrancar la API.

## Herramientas de diagnóstico local

`scripts/diagnostics/` contiene `OpenCVCamera`, una vista previa y `PoseDrawer`.
Solo los usan scripts que abren la webcam del equipo del desarrollador para
probar modelos a mano (`scripts/run_*_test.py`, `scripts/poses/run_*`,
`scripts/emotion/run_face_detection_test.py`). Quedan fuera del producto: la API
no los importa y la imagen Docker no los ejecuta. No usarlos con voluntarios.

## Modelo de datos

Tablas, relaciones y reglas de borrado en [data-model.md](data-model.md).

## Decisiones relevantes

- MediaPipe trabaja en modo `VIDEO` con timestamps monotónicos.
- Solo se transforma al dominio el subconjunto de landmarks necesario.
- La pérdida de la postura durante `holding` reinicia tiempo y progreso.
- Una recomendación automática siempre tiene dos o más posturas.
- Ningún detector o validador corporal conoce el repositorio de sesiones.
- El LLM nunca decide la emoción y no recibe resultados personales.
