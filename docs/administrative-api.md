# API administrativa y persistencia de actividades

Todas las rutas de datos requieren `Authorization: Bearer <token>`.

| Ruta | Acceso |
| --- | --- |
| `GET /students` | Administración y psicología: todos; estudiante: perfil propio |
| `GET /students/{id}` | Administración, psicología y propietario |
| `GET /students/{id}/consents` | Administración, psicología y propietario |
| `GET /students/{id}/consents/active` | Igual; devuelve `null` si no hay consentimiento activo |
| `POST /students/{id}/consents` | Administración o propietario; cuerpo `{"policy_version":"v1"}` |
| `POST /students/{id}/consents/revoke` | Administración o propietario |
| `GET /users`, `GET /users/{id}` | Administración |
| `POST /users` | Administración: email, password (mínimo 12 caracteres), role y student_code para estudiantes |
| `PATCH /users/{id}` | Administración: email, password, role, is_active |
| `DELETE /users/{id}` | Desactivación lógica; conserva sesiones y consentimientos |
| `POST /sessions/{id}/complete` | Administración y psicología; finalización manual controlada |

El endpoint de finalización recibe `initial_emotion`, `emotion_confidence` (0–1),
`activity_id`, `exercise_result` (`completed`) y `exercise_duration_seconds`.
No permite cambiar la actividad de una sesión ya asociada. Los estudiantes
completan la sesión mediante el análisis del servidor en `/ws/activity`, no
mediante resultados declarados por el cliente.

No se permite desactivar la propia cuenta administrativa ni retirar su propio
rol. Los cambios hacia o desde el rol estudiante se rechazan para conservar la
integridad del perfil. Los hashes de contraseña nunca se incluyen en respuestas.

## Actividades PostgreSQL

`ActivityCatalog` conserva su interfaz y admite un `ActivityRepository`.
FastAPI utiliza `PostgresActivityRepository` cuando la base está configurada.
La migración `20260915_04` crea `activities`, sus restricciones y tres actividades
iniciales. Las sesiones conservan el identificador histórico aunque una actividad
se elimine; no hay borrado en cascada de resultados.

Antes de iniciar la API, aplicar la migración al entorno elegido:

```powershell
python -m alembic upgrade head
python -m alembic current
```

La implementación no aplica migraciones automáticamente durante el arranque.

## Cámara y WebSocket

La cámara del navegador usa `/ws/activity`. El primer mensaje debe ser
`{"type":"authenticate","token":"...","session_id":"...","activity_id":"..."}`.
Se verifican rol, propietario, sesión activa, token y consentimiento durante el
procesamiento. La revocación o pérdida de conexión cancela la sesión en progreso.

Las rutas antiguas `/video_feed`, `/emotion`, `/stats`, `/control` y
`/control/{action}`, y el WebSocket `/ws/emotions`, quedan reservados a
administración. Este último exige un primer mensaje de autenticación y revalida
token y cuenta durante la conexión. No enviar JWT en URLs. Un cliente de video
debe usar una petición autenticada, no un `<img>` sin cabecera Bearer.

## Verificación

```powershell
python -m pytest -q -p no:cacheprovider
python -m alembic upgrade head --sql
```

Las pruebas aisladas utilizan SQLite con los adaptadores SQLAlchemy; no sustituyen
las pruebas PostgreSQL del entorno de integración. No se modifican datos locales
de PostgreSQL durante estas pruebas aisladas.
