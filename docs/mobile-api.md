# API del aplicativo móvil (contrato)

Contrato entre la API de EMOtv y el aplicativo Android (repositorio
`EMOtv-android`). **Este archivo se copia al proyecto Android**; si cambia aquí,
se vuelve a copiar.

- Versión de la API: la que devuelve `GET /mobile/status` (`api_version`).
- Todas las rutas empiezan con `/mobile` y usan JSON en UTF-8, salvo el envío de
  cuadros (`image/jpeg`) y las imágenes de estímulos.
- La API móvil reutiliza los servicios de la web: las mismas reglas de acceso
  (`can_access_participant`), autorizaciones, compromiso de confidencialidad,
  protocolos, cuestionarios y sesión guiada. Lo que la web rechaza, el aplicativo
  también lo rechaza.

## Reglas generales

| Regla | Detalle |
| --- | --- |
| HTTPS | En producción (`ENVIRONMENT=production`), toda ruta `/mobile` responde `403 https_required` si la petición no llega por HTTPS |
| Quién usa el aplicativo | Solo **usuarios** (`student`) y **docentes** (`psychologist`). Administrador y superadministrador: `403 role_not_allowed` |
| Tokens | Acceso: 15 minutos, cabecera `Authorization: Bearer <access_token>`. Renovación: 30 días, cambia en cada renovación |
| Separación web/móvil | Un token del aplicativo no sirve en la web y uno de la web no sirve en `/mobile` (`401 invalid_token`) |
| Caché | Todas las respuestas llevan `Cache-Control: no-store`. El aplicativo no debe guardar respuestas en disco |
| Imágenes | **Ninguna imagen de una persona se guarda ni sale del servidor.** Los cuadros que envía el aplicativo se analizan en memoria con el modelo local y se descartan. Las únicas imágenes que el aplicativo descarga son los estímulos |
| Resultados | Ninguna respuesta incluye la expresión estimada ni probabilidades: el dispositivo lo ve el participante. Los resultados se consultan en la web |
| Registros | El servidor no registra cuerpos de peticiones (contraseñas, respuestas ni cuadros) |
| Auditoría | Se auditan, sin contenido: inicio y cierre de sesión (también los rechazados por papel), el resumen, cada consulta a un participante (también las denegadas), la sesión guiada y cada imagen de estímulo servida o rechazada |

## Errores

Todos los errores propios de `/mobile` tienen esta forma:

```json
{"detail": {"code": "invalid_credentials", "message": "Correo o contraseña incorrectos"}}
```

`message` está en español y se puede mostrar a la persona. El aplicativo decide
por `code`:

| HTTP | `code` | Cuándo |
| --- | --- | --- |
| 400 | `bad_request` | Petición mal formada |
| 401 | `unauthorized` | Falta la cabecera `Authorization` |
| 401 | `invalid_token` | Token de acceso vencido, revocado, de la web o de una cuenta desactivada: renovar o volver a iniciar sesión |
| 401 | `invalid_credentials` | Correo o contraseña incorrectos |
| 401 | `invalid_refresh_token` | Token de renovación vencido, revocado o reutilizado: volver a iniciar sesión |
| 403 | `https_required` | Petición sin HTTPS en producción |
| 403 | `role_not_allowed` | La cuenta es de administración |
| 403 | `password_change_required` | La cuenta tiene contraseña provisional: cambiarla en la web |
| 403 | `forbidden` | La cuenta no tiene acceso a ese participante o sesión |
| 403 | `invalid_or_expired_url` | URL de imagen vencida, alterada o de una sesión que ya no está activa |
| 404 | `not_found` | Participante, protocolo, cuestionario o sesión inexistente (o ajeno) |
| 409 | `conflict` | La acción no corresponde a la fase actual, falta la autorización o el protocolo no se puede usar |
| 413 | `too_large` | Cuadro de más de 1 000 000 bytes |
| 415 | `unsupported_media_type` | Cuadro sin `Content-Type: image/jpeg` |
| 422 | `invalid` | Datos rechazados por una regla (por ejemplo, falta una confirmación o una respuesta obligatoria) |
| 428 | `commitment_required` | La cuenta no aceptó el compromiso de confidencialidad vigente: aceptarlo en la web |
| 429 | `too_many_attempts` | Bloqueo por intentos fallidos de inicio de sesión. Cabecera `Retry-After` en segundos |
| 503 | `unavailable` | El servidor no tiene configurado el módulo (por ejemplo, falta la clave de cifrado) |

Excepción: si el **cuerpo JSON no cumple el esquema** (falta un campo, tipo
incorrecto), FastAPI responde `422` con su formato estándar:
`{"detail": [{"type": "missing", "loc": ["body", "password"], "msg": "Field required", ...}]}`.

## Flujo del aplicativo

```text
GET  /mobile/status                         pantalla de carga
POST /mobile/auth/login                     inicio de sesión
GET  /mobile/summary                        dashboard
GET  /mobile/protocols?participant_id=...   elegir protocolo
POST /mobile/sessions                       iniciar sesión con participante
POST /mobile/sessions/{id}/confirm          confirmación previa
loop:
  GET  /mobile/sessions/{id}/next           qué mostrar ahora
  ├─ cuestionario  → POST .../questionnaires/{pre|post}
  ├─ calibración   → POST .../calibration, luego cuadros
  ├─ estímulo      → GET image_url, cuadros si send_frames
  └─ fin           → finished o stopped
POST /mobile/sessions/{id}/stop             interrumpir en cualquier momento
POST /mobile/auth/refresh                   antes de que venza el acceso (o ante 401 invalid_token)
POST /mobile/auth/logout                    cerrar sesión
```

---

## Estado

### `GET /mobile/status`

Sin autenticación. No devuelve datos personales.

**200**

```json
{
  "status": "ok",
  "api_version": "1.0.0rc1",
  "min_app_version": "1.0.0",
  "server_time": "2026-10-23T14:04:10.922662+00:00",
  "services": {"login": true, "participant_sessions": true}
}
```

- `min_app_version` (`MOBILE_MIN_APP_VERSION`, forma `x.y.z`): si la versión del
  aplicativo es menor, debe pedir actualizarlo y no continuar.
- `services.login` falso: el servidor no tiene base de datos o clave de tokens.
- `services.participant_sessions` falso: falta la clave de cifrado de datos
  sensibles; no se pueden conducir sesiones.

## Autenticación

### `POST /mobile/auth/login`

Misma cuenta que la web. Respeta el bloqueo por intentos fallidos (por correo e
IP) y el cambio de contraseña obligatorio.

```json
{"email": "usuario1@example.com", "password": "********"}
```

**200**

```json
{
  "access_token": "<token de acceso>",
  "token_type": "bearer",
  "expires_in": 900,
  "refresh_token": "<token de renovación>",
  "refresh_expires_in": 2592000,
  "user": {"id": "user-3245af00-...", "email": "usuario1@example.com", "role": "student", "role_name": "Usuario"}
}
```

`expires_in` y `refresh_expires_in` en segundos. `role_name` es el texto que se
muestra: «Usuario» o «Docente».

Errores: `401 invalid_credentials`, `403 role_not_allowed`,
`403 password_change_required`, `429 too_many_attempts` (con `Retry-After`).

Guardar `refresh_token` solo en almacenamiento cifrado del sistema (Android
Keystore / EncryptedSharedPreferences); `access_token`, en memoria.

### `POST /mobile/auth/refresh`

```json
{"refresh_token": "<token de renovación>"}
```

**200**: el mismo cuerpo que el inicio de sesión, con un **nuevo**
`refresh_token`. El anterior deja de valer: si se vuelve a usar, el servidor
revoca la sesión completa (puede haberse copiado) y responde
`401 invalid_refresh_token`.

También responde `401 invalid_refresh_token` si la sesión venció (30 días desde
el inicio de sesión, sin extenderse), se cerró, la contraseña cambió o la cuenta
se desactivó.

### `POST /mobile/auth/logout`

Con `Authorization: Bearer <access_token>`, sin cuerpo. **204** sin contenido.
Revoca el token de renovación de esa sesión; el token de acceso también deja de
valer de inmediato (`401 invalid_token`).

## Dashboard

### `GET /mobile/summary?date=2026-10-23&utc_offset_minutes=-300`

| Parámetro | Por defecto | Uso |
| --- | --- | --- |
| `date` | hoy, según `utc_offset_minutes` | Día de «sesiones del día» (`YYYY-MM-DD`) |
| `utc_offset_minutes` | `-300` (Perú) | Desfase horario del dispositivo, entre -720 y 840 |

Solo datos de la cuenta que inició sesión: sus participantes y sus sesiones.
Un docente tampoco ve aquí los participantes de los usuarios de su grupo (se
revisan en la web).

**200**

```json
{
  "user": {"id": "user-3245af00-...", "email": "usuario1@example.com", "role": "student", "role_name": "Usuario"},
  "date": "2026-10-23",
  "today_sessions": [
    {"id": "221e2a72-...", "started_at": "2026-10-23T14:04:10.922662+00:00", "state": "in_progress",
     "guided_phase": "stimuli", "participant_id": "3e7ac862-...", "participant_code": "P-RGNYTB",
     "protocol_name": "Secuencia móvil"}
  ],
  "participants": [
    {
      "id": "3e7ac862-...", "code": "P-RGNYTB", "kind": "adult", "age_years": 30,
      "ready": true, "missing": [], "warnings": [],
      "last_session": {"id": "221e2a72-...", "started_at": "2026-10-23T14:04:10.922662+00:00",
                       "state": "in_progress", "guided_phase": "stimuli", "participant_id": "3e7ac862-...",
                       "participant_code": "P-RGNYTB", "protocol_name": "Secuencia móvil"}
    },
    {
      "id": "9a1c...", "code": "P-7KQ2MD", "kind": "child", "age_years": 9,
      "ready": false, "missing": ["child_assent"],
      "warnings": ["Falta el asentimiento del niño o la niña"], "last_session": null
    }
  ]
}
```

- `missing`: `participation`, `camera`, `child_assent`, `revoked` (se retiró
  una autorización: no hay sesiones nuevas) o `age` (registrado sin edad).
  `warnings` trae el texto para mostrar. Con `ready: false` no se puede iniciar
  una sesión.
- `state` de una sesión: `in_progress`, `completed` o `cancelled`
  (`created` y `recognized` solo en sesiones propias de la web).
- `guided_phase`: ver [fases](#fases-de-la-sesión-guiada); `null` si no es una
  sesión guiada.
- Las autorizaciones se registran en la web, a partir del formato firmado en papel.

## Sesión con participante

### Fases de la sesión guiada

| `phase` | Qué hace el aplicativo |
| --- | --- |
| `confirmation` | Mostrar el recordatorio y pedir las confirmaciones (`POST .../confirm`) |
| `pre_questionnaire` | Mostrar el cuestionario previo y enviarlo |
| `before_analyzer` | Mostrar una imagen abstracta **sin** enviar cuadros |
| `calibration` | Pedir el rostro relajado; `POST .../calibration` y enviar cuadros mientras `send_frames` |
| `stimuli` | Mostrar el estímulo y enviar cuadros mientras `send_frames` |
| `post_questionnaire` | Mostrar el cuestionario posterior y enviarlo |
| `finished` | Fin. Agradecer al participante |
| `stopped` | Se interrumpió (`stop_reason`: `participant`, `guardian` o `conductor`) |

El servidor lleva el tiempo de cada estímulo: el aplicativo consulta
`GET .../next` (por ejemplo, cada segundo o al terminar `remaining_seconds`).

### `GET /mobile/protocols?participant_id={id}`

Protocolos que la cuenta puede aplicar a ese participante: los que armó ella
misma, en su versión vigente y con todos sus estímulos activos; con niños,
además, preparados para niños, aprobados por el docente y con estímulos aptos
para su edad.

**200**

```json
[
  {"id": "98128891-...", "name": "Secuencia móvil", "version": 1, "for_children": false, "step_count": 1,
   "has_pre_questionnaire": true, "has_post_questionnaire": false}
]
```

Errores: `403 forbidden` (participante ajeno), `404 not_found`.

### `POST /mobile/sessions`

```json
{"participant_id": "3e7ac862-...", "protocol_id": "98128891-..."}
```

Exige, igual que en la web: compromiso de confidencialidad aceptado, que la
cuenta haya registrado al participante, autorizaciones vigentes (participación,
cámara y, con niños, asentimiento) y un protocolo utilizable.

**201**

```json
{
  "session_id": "221e2a72-...",
  "phase": "confirmation",
  "participant": {"id": "3e7ac862-...", "code": "P-RGNYTB", "kind": "adult"},
  "confirmation": {
    "reminder": "Recuerda tu compromiso de confidencialidad: los datos de la sesión son solo para tu práctica y la de tu docente.",
    "required": ["commitment_reminder", "authorization_confirmed"]
  }
}
```

Con un niño, `required` es `["commitment_reminder", "guardian_present", "child_assent"]`.

Errores: `403 forbidden`, `404 not_found`, `409 conflict` (falta autorización o
protocolo no utilizable), `428 commitment_required`, `503 unavailable`.

### `POST /mobile/sessions/{id}/confirm`

Las casillas empiezan sin marcar; quien conduce las marca en el aplicativo.

```json
{"commitment_reminder": true, "authorization_confirmed": true, "guardian_present": false, "child_assent": false}
```

**200**: el mismo cuerpo que `GET .../next` para la fase siguiente.
Errores: `422 invalid` si falta una confirmación requerida, `409 conflict` si ya
se confirmó o el participante perdió su autorización.

### `GET /mobile/sessions/{id}/next`

**200**, siempre con estos campos (los que no aplican, en `null`):

```json
{
  "session_id": "221e2a72-...",
  "phase": "stimuli",
  "stop_reason": null,
  "send_frames": true,
  "frame_interval_ms": 500,
  "capture_status": [],
  "questionnaire": null,
  "calibration": null,
  "stimulus": {
    "step_index": 0,
    "title": "Paisaje",
    "kind": "emotional",
    "exposure_seconds": 6,
    "remaining_seconds": 5.4,
    "image_url": "/mobile/stimulus-images/221e2a72-.../68f45199-...?expires=1792764370&signature=5129118438...",
    "image_expires_at": "2026-10-23T14:06:10+00:00",
    "abstract_notice": null,
    "records_verbal_response": false
  },
  "confirmation": null,
  "step_count": 1
}
```

- `send_frames`: enviar cuadros cada `frame_interval_ms` mientras sea `true`.
- `capture_status`: problemas de calidad del último cuadro, para orientar a
  quien conduce: `no_face`, `off_center`, `too_small`, `too_dark`,
  `too_bright`, `tilted`, `no_frame`. Nunca la expresión estimada.
- `stimulus.image_url`: ruta relativa al servidor, firmada y válida
  **120 segundos** (`image_expires_at`). Si vence, pedir `next` de nuevo.
- `stimulus.abstract_notice`: con imágenes abstractas, el aviso fijo para mostrar.
- `records_verbal_response`: lo que el participante dice ver lo registra quien
  conduce **desde la web**; el aplicativo no lo envía.

En `pre_questionnaire` o `post_questionnaire`:

```json
"questionnaire": {
  "moment": "pre", "id": "fb0b13be-...", "version": 1, "title": "Antes de empezar",
  "instructions": "Responde con calma.", "answered": false,
  "questions": [
    {"id": "animo", "kind": "faces", "text": "¿Cómo te sientes?", "required": true, "options": [],
     "scale_points": null, "min_label": null, "max_label": null},
    {"id": "energia", "kind": "scale", "text": "¿Cuánta energía tienes?", "required": true, "options": [],
     "scale_points": 5, "min_label": "Poca", "max_label": "Mucha"},
    {"id": "lugar", "kind": "single_choice", "text": "¿Dónde estás?", "required": false,
     "options": ["Casa", "Aula"], "scale_points": null, "min_label": null, "max_label": null}
  ]
}
```

En `calibration`:

```json
"calibration": {"state": "calibrating", "progress": 0.0, "notice": null}
```

`state`: `none` (falta `POST .../calibration`), `calibrating` (enviar cuadros) o
`calibrated`. `notice`: texto para repetir la calibración si no se logró.

En `confirmation`, `confirmation` trae `reminder` y `required` como en
`POST /mobile/sessions`.

### `POST /mobile/sessions/{id}/questionnaires/{pre|post}`

```json
{"answers": {"animo": 3, "energia": 4, "lugar": "Casa", "apoyos": ["Música"], "nota": "Bien"},
 "entry_mode": "participant"}
```

| `kind` | Valor |
| --- | --- |
| `faces` | Entero del 1 al 5 |
| `scale` | Entero del 1 a `scale_points` |
| `single_choice` | Una de `options` |
| `multiple_choice` | Lista con elementos de `options` |
| `short_text` | Texto |

`entry_mode`: `participant` (respondió en el dispositivo) o `conductor` (quien
conduce anotó lo que dijo). Las respuestas se guardan cifradas, no se puntúan
ni se interpretan, y **no se devuelven**.

**201**: `{"phase": "calibration"}` — se continúa a la fase siguiente.
Errores: `422 invalid` (falta una obligatoria o valor fuera de rango),
`409 conflict` (ya se respondió o no es la fase).

### `POST /mobile/sessions/{id}/advance`

Continúa tras un cuestionario ya respondido (por ejemplo, si se respondió en la
web). **200** `{"phase": "..."}`; `409 conflict` si falta responderlo.

### `POST /mobile/sessions/{id}/calibration`

Empieza la calibración neutral (unos 3 segundos de cuadros con el rostro
relajado). **200** `{"phase": "calibration"}`. Al terminar, la sesión pasa sola a
`stimuli`.

### `POST /mobile/sessions/{id}/frames`

Cuerpo: un cuadro **JPEG** (`Content-Type: image/jpeg`, máximo 1 000 000 bytes;
la web envía 640 × 480). El servidor lo analiza en memoria con el modelo
local, aplica el control de calidad (rostro, centrado, tamaño, iluminación e
inclinación) y lo descarta. Fuera de `calibration` y `stimuli` el cuadro se
ignora.

**200**

```json
{"phase": "stimuli", "capture_status": []}
```

Errores: `413 too_large`, `415 unsupported_media_type`, `422 invalid` (no es un
JPEG válido), `409 conflict` (la sesión terminó), `403 forbidden`.

### `POST /mobile/sessions/{id}/skip`

Salta el estímulo en curso. **200** `{"phase": "..."}`.

### `POST /mobile/sessions/{id}/stop`

Interrumpe de inmediato. Usar en cuanto el participante o su tutor pidan parar.

```json
{"reason": "participant"}
```

`reason`: `participant`, `guardian` o `conductor`. **200** `{"phase": "stopped"}`.

## Imágenes de estímulos

### `GET /mobile/stimulus-images/{session_id}/{stimulus_id}?expires=...&signature=...`

La URL la entrega `GET .../next`; no se arma en el aplicativo. No lleva token:
la firma nombra la sesión, el estímulo y el vencimiento. Solo vale mientras la
sesión de quien la recibió siga activa y el estímulo sea de su protocolo.

**200**: la imagen (`image/png`, `image/jpeg` o `image/webp`), sin metadatos.
No guardarla en la caché de disco del cargador de imágenes.

**403** `invalid_or_expired_url`: vencida, alterada, o la sesión ya terminó.

## Configuración del servidor

| Variable | Por defecto | Uso |
| --- | --- | --- |
| `MOBILE_MIN_APP_VERSION` | `1.0.0` | Versión mínima del aplicativo (`x.y.z`) |
| `ENVIRONMENT` | `development` | Con `production`, `/mobile` exige HTTPS |
| `LOGIN_MAX_FAILURES_PER_ACCOUNT`, `LOGIN_MAX_FAILURES_PER_IP`, `LOGIN_ATTEMPT_WINDOW_MINUTES` | 5, 20, 15 | Bloqueo por intentos fallidos (compartido con la web) |

Detrás de nginx, la API conoce el esquema por `X-Forwarded-Proto`: nginx
reenvía `https` cuando lo recibe del proxy TLS (Caddy o el de la institución).
