# API HTTP de EMOtv

## Ejecución

Configura `DATABASE_URL` y `JWT_SECRET_KEY` en `.env`, aplica las migraciones y
arranca FastAPI desde la raíz del proyecto:

```powershell
.venv\Scripts\python.exe -m alembic upgrade head
.venv\Scripts\python.exe scripts/run_api.py
```

La documentación interactiva queda disponible en `/docs` en desarrollo y se
deshabilita en modo producción. `.env.example` solo
debe contener valores de referencia seguros para versionar, nunca credenciales.

## Autenticación

`POST /auth/token` recibe el formulario OAuth2 con `username` (correo) y
`password`. Las demás rutas protegidas usan:

```http
Authorization: Bearer <access_token>
```

`GET /auth/me` devuelve la identidad actual. `GET /auth/users` requiere permiso
administrativo.

## Papeles, participantes, compromiso y auditoría

Papeles: `superadmin` (Superadministrador), `admin` (Administrador),
`psychologist` (Docente) y `student` (Usuario). El administrador y el
superadministrador nunca acceden a participantes, sesiones ni resultados. Ver
[privacidad](privacy/README.md).

| Método | Ruta | Acceso |
| --- | --- | --- |
| `GET`, `POST` | `/users` | Superadministrador: cuenta de administrador (máximo `MAX_ADMIN_ACCOUNTS`). Administrador: docentes y usuarios |
| `PATCH`, `DELETE` | `/users/{id}` | Igual que arriba; el papel no se cambia |
| `POST` | `/users/{id}/reset-password` | Igual que arriba; contraseña temporal visible una vez, aviso en el siguiente ingreso y auditoría |
| `PUT`, `DELETE` | `/users/{docente}/assigned-students/{student_id}` | Administrador; asignar a otro docente mueve al usuario |
| `GET` | `/commitment`, `/commitment/child-notice` | Texto versionado y si la cuenta debe aceptarlo |
| `POST` | `/commitment/accept`, `/commitment/child-notice/accept` | Usuarios y docentes, con la versión vigente |
| `GET`, `POST` | `/participants` | Usuarios y docentes (el docente ve también los de su grupo); `428` sin compromiso o, para el primer niño, sin el aviso. El registro pide `kind` y `age_years` (adulto: 18 o más) y rechaza cualquier otro dato de identidad (`422`) |
| `GET` | `/participants/{id}` | `can_access_participant` |
| `GET` | `/participants/expiring` | Docente: vencen en los próximos 30 días |
| `GET`, `POST` | `/participants/{id}/authorizations` | `can_access_participant`; registra el formato firmado (`form_version`, `signed_on`, `participation`, `camera` y, en niños, `child_assent`) |
| `POST` | `/participants/{id}/authorizations/{auth_id}/revoke` | `can_access_participant`; `party` y `scope`. Bloquea sesiones nuevas y marca al participante |
| `POST` | `/participants/{id}/deletion-request` | Quien registró al participante |
| `POST` | `/participants/{id}/delete` | Docente con acceso; devuelve el acta |
| `GET` | `/participant-deletions`, `/participant-deletions/{id}` | Quien solicitó o ejecutó |
| `POST` | `/participant-deletions/{id}/print` | Registra la impresión del acta |
| `GET` | `/audit` | Administrador y superadministrador, con filtros; no hay operaciones de escritura |

Sin `SENSITIVE_DATA_KEY`, las rutas de participantes responden `503`.

## Estímulos y protocolos

| Método | Ruta | Acceso |
| --- | --- | --- |
| `GET` | `/stimuli` | Usuarios (institucionales y los de su docente), docentes (los suyos e institucionales) y administrador (institucionales). `?child_age=N`: solo leves, aprobados, vigentes y con edad mínima ≤ N |
| `POST` | `/stimuli` | Docente (alcance de grupo) o administrador (institución), con `multipart/form-data`: imagen PNG, JPEG o WebP de hasta 5 MB, título, tipo, categoría, expresión esperada (solo emocionales), intensidad, edad mínima, origen, licencia y las declaraciones `not_a_participant_photo` y, en abstractas, `not_a_projective_test`. Los usuarios reciben `403` |
| `GET` | `/stimuli/{id}`, `/stimuli/{id}/file` | Quien puede verlo; `/file` es la única ruta que sirve una imagen, siempre un estímulo reescrito sin metadatos |
| `POST` | `/stimuli/{id}/approve` | Quien lo gestiona |
| `PUT` | `/stimuli/{id}/active` | Quien lo gestiona: retirar o volver a ofrecer |
| `GET`, `POST` | `/protocols` | Usuarios y docentes; el docente ve también los de su grupo |
| `GET`, `PUT` | `/protocols/{id}` | `PUT` solo quien lo armó. Si la versión se usó en una sesión, responde con una versión nueva (otro `id`, mismo `family_id`) sin aprobación |
| `POST` | `/protocols/{id}/approve` | Docente del autor (o el docente que lo armó); solo protocolos para niños |

`pre_questionnaire_id` queda reservado para el cuestionario previo (P6A); hasta
que exista ese módulo, cualquier valor responde `422`.

## Sesiones

| Método | Ruta | Acceso |
| --- | --- | --- |
| `POST` | `/sessions` | Usuario (sus sesiones) o docente (sesiones propias); exige el compromiso aceptado (`428`) |
| `POST` | `/sessions/{id}/cancel` | Solo quien conduce la sesión |
| `GET` | `/sessions/{id}` | Quien la conduce o el docente de su grupo |
| `GET` | `/sessions` | Propias (usuario) o las propias y las de su grupo (docente) |
| `GET` | `/sessions?student_id={id}` | Sesiones de un usuario del grupo del docente |

Para un usuario, el servidor fuerza el alcance al perfil propio y rechaza un
`student_id` ajeno con `403`. El registro manual del resultado
(`/sessions/{id}/complete`) ya no existe. Una sesión inexistente devuelve `404`. Iniciar una
sesión asociada exige consentimiento activo.

Cada sesión guarda su `session_type`: `propia` (quien inicia sesión se analiza a
sí mismo, sin participante), `participante_adulto` o `participante_infantil`.
`POST /sessions` acepta `session_type` (por defecto `propia`), `participant_id`
(obligatorio en los tipos con participante) y `protocol_id` (opcional). Con
participante, solo quien lo registró inicia la sesión y el servidor exige la
última autorización con participación (a), cámara (b) y, en niños,
asentimiento; sin ellas, o tras un retiro, responde `409`. Un protocolo para
niños se aplica solo aprobado y con estímulos adecuados a la edad (`409`).

## Actividades

| Método | Ruta | Acceso |
| --- | --- | --- |
| `GET` | `/activities` | Cualquier usuario autenticado |
| `GET` | `/activities/{id}` | Cualquier usuario autenticado |
| `POST` | `/activities` | Administración |
| `PUT` | `/activities/{id}` | Administración |
| `DELETE` | `/activities/{id}` | Administración |

Ejemplo para crear o reemplazar una actividad:

```json
{
  "id": "arms_open_8s",
  "name": "Apertura de brazos",
  "description": "Mantén ambos brazos abiertos a la altura de los hombros.",
  "required_posture": "arms_open",
  "duration_seconds": 8.0,
  "repetitions": 2
}
```

Al actualizar, el ID del cuerpo y el de la ruta deben coincidir. El catálogo es
persistente en PostgreSQL cuando se ejecuta FastAPI con la base configurada.
La migración `20260915_04` crea y carga tres actividades iniciales.

## Catálogo informativo de expresiones

| Método | Ruta | Acceso |
| --- | --- | --- |
| `GET` | `/expressions` | Cualquier usuario autenticado |
| `GET` | `/expressions/{key}` | Cualquier usuario autenticado; `404` si la clave no existe |
| `PUT` | `/expressions/{key}` | Administración; `422` si un texto no cumple la longitud |

Cada registro trae `label_es`, `what_it_is`, `why_it_occurs`, `facial_cues`,
`practice_tip`, `limitation_note`, `common_limitation`, `review_status`
(`draft` o `reviewed`), `reviewed_by_user_id`, `reviewed_at` y `updated_at`.
Detalles y reglas de redacción en [Catálogo de expresiones](expression-catalog.md).

## Identidades, consentimiento y análisis web

Las rutas `/users`, `/students` y `/students/{id}/consents` están descritas en
[API administrativa](administrative-api.md), incluidos permisos y desactivación lógica.
`/auth/users` conserva el listado administrativo anterior.

`/ws/activity` recibe primero autenticación y referencias de sesión/actividad,
después JPEG binarios. Devuelve progreso, estado, emoción y landmarks opcionales.
El servidor valida la finalización de la actividad; no acepta que el usuario
declare un resultado completado mediante REST. La cámara pertenece al navegador,
no al servidor: no existen rutas de cámara del servidor.

### Análisis en vivo (sesión sin actividad previa)

| Dirección | Mensaje | Contenido |
| --- | --- | --- |
| servidor → cliente | `ready` | `state: "live"`, `emotion_model_id` usado, `live_stable_seconds`, `live_min_confidence`, `calibration_seconds`, `calibration_min_increase` |
| servidor → cliente | `live` | uno por frame procesado: `face_detected`, `emotion` (clave del modelo, estabilizada), `emotion_confidence`, `distribution` (todas las clases de mayor a menor; con calibración, también `baseline` y `change`), `calibration` (`state`: `none`/`calibrating`/`calibrated`, `progress`, `suggested`, `notice`), `stable_seconds`, `required_stable_seconds`, `can_confirm`, `blocked_reason` |
| cliente → servidor | `calibrate` | opcional, antes de registrar; responde `calibration_started` con `seconds` |
| cliente → servidor | `confirm_expression` | sin etiqueta; cualquier `emotion` enviada se ignora |
| servidor → cliente | `confirm_rejected` | `message` con el motivo (sin rostro, sin expresión estable, confianza baja o poco tiempo estable) |
| servidor → cliente | `recognized` | la expresión que el servidor **realmente** registró y `recognized_at`; después llega `recommendation` |
| servidor → cliente | `recommendation` | actividad sugerida (o `null`), actividades disponibles, `expression` con todos los campos del catálogo y `notice` si la recomendación no se pudo calcular |
| servidor → cliente | `error` con `stage` | etapa que falló: `recognition`, `activity`, `persistence` o `server`; el detalle técnico queda solo en el log del servidor |
| cliente → servidor | `select_activity` | `activity_id`; inicia la actividad |
| cliente → servidor | `finish_without_activity` | cierra como `completed` con `exercise_result: "skipped"` |
| cliente → servidor | `cancel` | responde `cancelled` con `recognition_kept` |

El navegador envía un cuadro solo después de recibir la respuesta al anterior.
El servidor descarta, sin responder, los cuadros que lleguen mientras analiza
otro. Si no hay cupo de sesión o de análisis tras
`ANALYSIS_BUSY_WAIT_SECONDS`, responde `error` con "El servidor está ocupado;
intenta de nuevo en un momento" y `code: 1013`. Si no llegan cuadros durante
`LIVE_IDLE_TIMEOUT_SECONDS` mientras se esperan, responde `error` con
`code: 4408` y libera la sesión. Ver
[protección de carga](architecture.md#protección-de-carga-del-análisis).

La fase en vivo no escribe en la base de datos ni genera recomendación. El
registro solo se acepta si hay rostro y la expresión lleva al menos
`LIVE_STABLE_SECONDS` sin cambiar (1 por defecto) con confianza media de al
menos `LIVE_MIN_CONFIDENCE` (0.5 por defecto), ambos configurables en `.env`.
El servidor envía un mensaje `live` por frame procesado y el navegador envía el
siguiente frame solo al recibir la respuesta, así que no hay mensajes extra.
Con la expresión ya registrada, desconectarse o cancelar conserva la sesión
(`completed` con `exercise_result: "cancelled"`); ver [Sesiones](sessions.md).

La calibración neutral promedia la distribución durante `calibration_seconds`
(3) con el rostro relajado. La base vive solo en memoria durante esa conexión:
no se escribe en la base de datos. `suggested` es la clase con mayor aumento
respecto a la base (diferencia de probabilidad), si alcanza
`LIVE_CALIBRATION_MIN_INCREASE` (0.10 por defecto). La calibración no cambia lo
que se registra ni el umbral de registro.

Sin `emotion_model_id`, la sesión usa el modelo local predeterminado que fija el
superadministrador (HSEmotion, `hsemotion_enet_b0_8_best_afew`, mientras nadie
lo cambie). Si el predeterminado no tiene admisión vigente, usa el otro modelo
local y lo registra; si ninguno está admitido, el socket se cierra con el motivo.
Quien conduce la sesión puede pedir FER+ o HSEmotion para esa sesión; un modelo
pedido sin admisión se rechaza (`4409`) y cualquier otro modelo, con `4403`
(salvo el superadministrador, que conserva el experimental). Cada sesión registra el
modelo que usó.

`GET /analysis/models` lista, para quien conduce la sesión, los modelos locales
con `state` e `is_default`; el superadministrador recibe además la evaluación completa
de admisión.

| Método | Ruta | Acceso |
| --- | --- | --- |
| `GET` | `/admin/models` | Solo superadministrador (rol `admin` hasta P5): estado de HSEmotion y FER+ (pesos verificados, medición vigente, latencia p95), predeterminado, quién lo cambió y cuándo, último uso del respaldo |
| `PUT` | `/admin/models/default` | Solo superadministrador: `{"model_id": ...}`; `409` si el modelo no tiene admisión vigente |

El cambio rige desde la siguiente sesión, sin reiniciar el servidor. Cada
clasificador se carga una vez por proceso y lo comparten las sesiones.

`GET /` devuelve `{"service": "emotv-api", "status": "running"}`. `GET /health`
comprueba base de datos y pesos (200 o 503) y lo usa Docker.

CORS y validación de origen WebSocket se configuran por separado. Consultar
[preparación para producción](production-readiness.md).

## Respuestas de error

- `401`: token ausente, inválido o vencido;
- `403`: el rol o la propiedad no permite la operación;
- `404`: recurso inexistente;
- `409`: estado incompatible, ID duplicado o actualización inconsistente;
- `422`: cuerpo o parámetros inválidos;
- `503`: servicio no configurado.

## Verificación previa al commit

```powershell
.venv\Scripts\python.exe -m pytest -q
.venv\Scripts\python.exe -m compileall -q src scripts tests
.venv\Scripts\python.exe -m alembic current
git diff --check
git status --short
git diff --stat
```

Revisa que `.env`, pesos, entornos virtuales y cachés no aparezcan entre los
archivos que se versionarán. Evita ejecutar `git add .` antes de revisar el
estado del repositorio.
