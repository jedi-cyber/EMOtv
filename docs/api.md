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

## Sesiones

| Método | Ruta | Acceso |
| --- | --- | --- |
| `POST` | `/sessions` | Estudiante propio o administración |
| `POST` | `/sessions/{id}/cancel` | Propietario o administración |
| `POST` | `/sessions/{id}/complete` | Solo administración; resultado manual controlado |
| `GET` | `/sessions/{id}` | Propietario, psicología asignada o administración |
| `GET` | `/sessions` | Propias (estudiante), de estudiantes asignados (psicología) o todas (administración) |
| `GET` | `/sessions?student_id={id}` | Sesiones del estudiante indicado |

Para estudiantes, el servidor fuerza el alcance al perfil propio y rechaza un
`student_id` ajeno con `403`. Una sesión inexistente devuelve `404`. Iniciar una
sesión asociada exige consentimiento activo.

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
El servidor valida la finalización estudiantil; no acepta que un estudiante
declare un resultado completado mediante REST. La cámara pertenece al navegador,
no al servidor: no existen rutas de cámara del servidor.

### Análisis en vivo (sesión sin actividad previa)

| Dirección | Mensaje | Contenido |
| --- | --- | --- |
| servidor → cliente | `ready` | `state: "live"`, `live_stable_seconds`, `live_min_confidence` |
| servidor → cliente | `live` | uno por frame procesado: `face_detected`, `emotion` (clave del modelo, estabilizada), `emotion_confidence`, `top` (tres clases más probables si el modelo da la distribución), `stable_seconds`, `required_stable_seconds`, `can_confirm`, `blocked_reason` |
| cliente → servidor | `confirm_expression` | sin etiqueta; cualquier `emotion` enviada se ignora |
| servidor → cliente | `confirm_rejected` | `message` con el motivo (sin rostro, sin expresión estable, confianza baja o poco tiempo estable) |
| servidor → cliente | `recognized` | la expresión que el servidor **realmente** registró y `recognized_at`; después llega `recommendation` |
| servidor → cliente | `recommendation` | actividad sugerida (o `null`), actividades disponibles, `expression` con todos los campos del catálogo y `notice` si la recomendación no se pudo calcular |
| servidor → cliente | `error` con `stage` | etapa que falló: `recognition`, `activity`, `persistence` o `server`; el detalle técnico queda solo en el log del servidor |
| cliente → servidor | `select_activity` | `activity_id`; inicia la actividad |
| cliente → servidor | `finish_without_activity` | cierra como `completed` con `exercise_result: "skipped"` |
| cliente → servidor | `cancel` | responde `cancelled` con `recognition_kept` |

La fase en vivo no escribe en la base de datos ni genera recomendación. El
registro solo se acepta si hay rostro y la expresión lleva al menos
`LIVE_STABLE_SECONDS` sin cambiar (1 por defecto) con confianza media de al
menos `LIVE_MIN_CONFIDENCE` (0.5 por defecto), ambos configurables en `.env`.
El servidor envía un mensaje `live` por frame procesado y el navegador envía el
siguiente frame solo al recibir la respuesta, así que no hay mensajes extra.
Con la expresión ya registrada, desconectarse o cancelar conserva la sesión
(`completed` con `exercise_result: "cancelled"`); ver [Sesiones](sessions.md).

`GET /analysis/models` es solo para administración. El estudiante analiza
siempre con FER+; si envía un `emotion_model_id` distinto, el WebSocket lo
rechaza con `4403`.

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
