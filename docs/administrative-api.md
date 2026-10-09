# API administrativa y persistencia de actividades

Todas las rutas de datos requieren `Authorization: Bearer <token>`.

## Primer acceso y consentimiento

`POST /users` acepta `email`, `role` y `student_code` para estudiantes. El
servidor genera una contraseña provisional única y la
devuelve **una sola vez** en `temporary_password`; no se almacena en claro.
El administrador debe entregarla por un canal seguro. La cuenta nueva queda
marcada para cambio obligatorio. `POST /users/{id}/reset-password` permite
emitir una nueva clave provisional para una cuenta existente, incluida una
cuenta de demostración, e invalida sus JWT anteriores.

Tras ingresar, el usuario cambia la clave mediante `POST /auth/change-password`
con `current_password` y `new_password` (mínimo 12 caracteres). La respuesta
incluye un JWT nuevo; el anterior deja de funcionar. Mientras la clave sea
provisional, las demás rutas protegidas no están disponibles.

La decisión facial corresponde al estudiante, no al alta administrativa. La
pantalla `/consent` muestra el texto activo, permite aceptar o seguir sin
aceptar y ofrece revocación posterior. La aceptación guarda el identificador
inmutable `código:versión`; no se crea automáticamente.

`CONSENT_MODE=development` omite la exigencia solo para pruebas técnicas.
`CONSENT_MODE=demo` es el valor inicial local: activa automáticamente
`docs/consent-demo.md` si no existe otra política activa y **sí exige** que el
estudiante la acepte. `CONSENT_MODE=production` exige una política marcada
como aprobada, no demo, y aceptación de la versión vigente. `ENVIRONMENT=production`
rechaza cualquier modo menos estricto. No usar desarrollo/demo con personas reales.

Administración dispone de `GET /consent-policies`, `POST /consent-policies` y
`POST /consent-policies/{id}/activate` para cargar el texto completo, código,
versión, fecha de vigencia y aprobación, y activar una versión sin modificar
Python o React. Activar una nueva conserva las anteriores como históricas y
requiere una nueva aceptación de cada estudiante para futuros análisis.
`docs/privacy-data-governance.md` sigue siendo una guía/borrador de despliegue,
**no** el consentimiento estudiantil. Aplique la migración `20260918_07` antes
de reiniciar FastAPI.

| Ruta | Acceso |
| --- | --- |
| `GET /students` | Administración: todos; psicología: solo sus asignados; estudiante: perfil propio |
| `GET /students/{id}` | Administración, psicología asignada y propietario |
| `GET /students/{id}/consents` | Administración, psicología asignada y propietario |
| `GET /students/{id}/consents/active` | Igual; devuelve `null` si no hay consentimiento activo |
| `POST /students/{id}/consents` | Solo estudiante propietario; cuerpo `{"policy_version":"versión vigente"}` |
| `POST /students/{id}/consents/revoke` | Administración o propietario |
| `GET /users`, `GET /users/{id}` | Administración |
| `POST /users` | Administración: email, role y student_code para estudiantes; clave provisional generada por servidor |
| `PATCH /users/{id}` | Administración: email, role, is_active; no permite establecer contraseñas compartidas |
| `DELETE /users/{id}` | Desactivación lógica; conserva sesiones y consentimientos |
| `POST /sessions/{id}/complete` | Solo administración; finalización manual controlada |
| `GET /users/{id}/assigned-students` | Administración: estudiantes asignados a una cuenta de psicología |
| `PUT /users/{id}/assigned-students/{student_id}` | Administración: asigna (idempotente) |
| `DELETE /users/{id}/assigned-students/{student_id}` | Administración: retira la asignación; `404` si no existía |
| `GET /expressions`, `GET /expressions/{key}` | Cualquier usuario autenticado |
| `PUT /expressions/{key}` | Administración: edita textos; `review_status: "reviewed"` registra quién y cuándo |
| `GET /recommendations`, `GET /recommendations/{key}` | Administración: actividades recomendadas por expresión, en orden de prioridad |
| `PUT /recommendations/{key}` | Administración: `{"activity_ids": [...]}`; el orden es la prioridad; `422` si una actividad no existe, se repite o tiene menos de dos pasos |
| `PUT /activities/{id}` | `409` si la actividad está recomendada y quedaría con menos de dos pasos; el mensaje nombra las expresiones afectadas |

El endpoint de finalización recibe `initial_emotion`, `emotion_confidence` (0–1),
`activity_id`, `exercise_result` (solo `completed`) y `exercise_duration_seconds`.
Si el estudiante ya registró su expresión en vivo, esa expresión se conserva.
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

El campo opcional `emotion_model_id` solo puede ser distinto de `ferplus_onnx`
para administración, que consulta la admisión en `GET /analysis/models`. No
enviar JWT en URLs. El servidor no abre cámaras propias ni ofrece streaming de
video.

## Verificación

```powershell
python -m pytest -q -p no:cacheprovider
python -m alembic upgrade head --sql
```

Las pruebas aisladas utilizan SQLite con los adaptadores SQLAlchemy; no sustituyen
las pruebas PostgreSQL del entorno de integración. No se modifican datos locales
de PostgreSQL durante estas pruebas aisladas.
