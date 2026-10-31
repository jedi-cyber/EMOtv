# API del aplicativo móvil (contrato)

Contrato entre la API de EMOtv y el aplicativo Android (repositorio
`EMOtv-android`). **Este archivo es la fuente de verdad y se copia tal cual al
proyecto Android** (`docs/mobile-api.md`). Si cambia aquí, se vuelve a copiar.

| | |
| --- | --- |
| Revisión del contrato | 4.1 (2026-10-30). Ver [historial](#historial). **Incompatible con la revisión 3**; la 4.1 solo agrega campos opcionales a la 4 |
| Versión de la API | La que devuelve `GET /mobile/status` en `api_version` (hoy `1.0.0rc1`) |
| Prefijo | Todas las rutas empiezan con `/mobile` |
| Formato | JSON en UTF-8 |

**El aplicativo no conduce sesiones.** Las sesiones se conducen en la web (el
Analizador), donde la cámara se obtiene en el navegador. El aplicativo sirve
para consultar lo ya registrado y actuar sobre el reporte:

- **Mis sesiones y su detalle**: lista por código, línea de tiempo y métricas
  descriptivas.
- **Reportes**: estado y comentarios. El Usuario redacta, corrige y envía su
  reporte; el Docente lo comenta, lo devuelve o lo aprueba.
- **Estadísticas agregadas**: cuentan sesiones, no personas.
- **Pendientes del Docente**: reportes que los usuarios de su grupo enviaron a
  revisión.

Ninguna ruta `/mobile` recibe imágenes: ninguna captura del rostro sale del
teléfono.

La API móvil no tiene reglas propias: llama a los mismos servicios que la web
(`can_access_session`, línea de tiempo, métricas, reporte y estadísticas).
**Lo que la web rechaza, el aplicativo también lo rechaza**, y toda restricción
la impone el servidor.

## Contenido

1. [Reglas generales](#reglas-generales)
2. [Convenciones](#convenciones)
3. [Compatibilidad entre versiones](#compatibilidad-entre-versiones)
4. [Errores](#errores)
5. [Autenticación y tokens](#autenticación-y-tokens)
6. [Flujo del aplicativo](#flujo-del-aplicativo)
7. [Endpoints](#endpoints)
8. [Tipos de datos](#tipos-de-datos)
9. [Valores enumerados](#valores-enumerados)
10. [Reintentos e idempotencia](#reintentos-e-idempotencia)
11. [Obligaciones de privacidad del aplicativo](#obligaciones-de-privacidad-del-aplicativo)
12. [Configuración del servidor](#configuración-del-servidor)
13. [Historial](#historial)

---

## Reglas generales

| Regla | Detalle |
| --- | --- |
| HTTPS | En producción (`ENVIRONMENT=production`), toda ruta `/mobile` responde `403 https_required` si la petición no llega por HTTPS |
| Quién usa el aplicativo | Solo **usuarios** (`student`) y **docentes** (`psychologist`). Administrador y superadministrador: `403 role_not_allowed`. Las personas evaluadas no se registran ni tienen cuenta |
| Tokens | Acceso: 15 minutos, cabecera `Authorization: Bearer <token de acceso>`. Renovación: 30 días desde el inicio de sesión, cambia en cada renovación |
| Separación web/móvil | Un token del aplicativo no sirve en la web y uno de la web no sirve en `/mobile` (`401 invalid_token`) |
| Caché | Todas las respuestas llevan `Cache-Control: no-store`. El aplicativo no guarda respuestas en disco |
| Imágenes | **Ninguna imagen de una persona se guarda ni sale del servidor**, y el aplicativo no envía ni descarga imágenes |
| Qué ve cada cuenta | El Usuario, sus sesiones. El Docente, las suyas y las de los usuarios de su grupo. Es lo mismo que ve en la web |
| Resultados | La línea de tiempo y las métricas muestran **expresiones estimadas** por un modelo, como en la web. No son una evaluación, no diagnostican y no indican lo que la persona sentía. Los avisos (`estimates_notice`, `abstract_notice`, `notice`) se muestran tal cual |
| Personas evaluadas | No se registran. Cada sesión se identifica solo por su **código** (`S-4F7K2Q`). Ninguna respuesta trae nombre, DNI ni foto |
| Estadísticas | Cuentan sesiones, no personas. En el aplicativo no se desglosan por usuario |
| Registros | El servidor no registra cuerpos de peticiones (contraseñas ni textos de reportes) |
| Auditoría | Se auditan, sin contenido: inicio y cierre de sesión (también los rechazados por papel), el resumen, la lista de sesiones, cada línea de tiempo, métricas y reporte consultados (también los denegados), cada acción sobre un reporte, las estadísticas y la lista de pendientes |

## Convenciones

| Tema | Regla |
| --- | --- |
| URL base | Las rutas de este documento son absolutas desde la raíz del servidor (`https://servidor/mobile/...`) |
| Cabeceras | `Authorization: Bearer <token de acceso>` en todo endpoint marcado «Con token». `Content-Type: application/json` en los cuerpos JSON |
| Campos desconocidos en peticiones | Se rechazan: un cuerpo con un campo que no está en este contrato responde `422` con el formato de FastAPI. No enviar campos de más |
| Campos desconocidos en respuestas | El aplicativo **debe ignorarlos** (`ignoreUnknownKeys`). El servidor puede agregar campos sin cambiar la revisión mayor |
| Nulos | Un campo marcado «nulable» viene siempre, con valor o `null`. Ningún campo documentado se omite |
| Identificadores | Cadenas opacas (UUID o `user-<uuid>`). No se interpretan ni se arman en el aplicativo |
| Fechas y horas | ISO 8601 con zona: `2026-10-23T14:04:10.922662+00:00` (UTC). La fracción de segundo es opcional. Las fechas sin hora: `YYYY-MM-DD` |
| Tiempos de la línea de tiempo | Segundos (número, puede tener decimales) desde el inicio de la sesión |
| Textos | En español y listos para mostrar: `message`, `notice`, `estimates_notice`, `abstract_notice`, `few_sessions_notice`, `sentence` y `role_name`. El aplicativo no los traduce ni los reescribe |
| Códigos HTTP de éxito | `200`, salvo `201` en `POST /mobile/sessions/{id}/report` y `204` sin cuerpo en `POST /mobile/auth/logout` |

## Compatibilidad entre versiones

- **Cambios compatibles** (no exigen actualizar el aplicativo): campos nuevos en
  respuestas, endpoints nuevos, valores nuevos en enumeraciones marcadas como
  «abiertas» en [valores enumerados](#valores-enumerados) y mensajes distintos.
- **Cambios incompatibles** (quitar o renombrar un campo, cambiar un tipo, cambiar
  el significado de un `code`): suben `MOBILE_MIN_APP_VERSION`. El aplicativo
  que queda por debajo lo detecta en `GET /mobile/status` y pide actualizarse.
- Ante un valor desconocido de una enumeración abierta, el aplicativo no falla:
  muestra el valor tal cual o lo ignora, y usa `message` si lo hay.
- `api_version` es informativa (puede tener sufijos como `rc1`). Solo
  `min_app_version` se compara, siempre con la forma `x.y.z`.

## Errores

Todos los errores propios de `/mobile` tienen esta forma:

```json
{"detail": {"code": "invalid_credentials", "message": "Correo o contraseña incorrectos"}}
```

`message` está en español y se puede mostrar. **El aplicativo decide por
`code`, nunca por `message`** (el texto puede cambiar).

| HTTP | `code` | Cuándo | Qué hace el aplicativo |
| --- | --- | --- | --- |
| 400 | `bad_request` | Petición mal formada | Error interno: mostrar `message` y registrar el fallo sin datos |
| 401 | `unauthorized` | Falta la cabecera `Authorization` | Renovar una vez; si falla, volver al inicio de sesión |
| 401 | `invalid_token` | Token de acceso vencido, revocado, de la web, de una cuenta desactivada o anterior a un cambio de contraseña | Renovar una vez y repetir la llamada; si la renovación falla, volver al inicio de sesión |
| 401 | `invalid_credentials` | Correo o contraseña incorrectos (también si la cuenta está desactivada) | Mostrar `message` en el formulario |
| 401 | `invalid_refresh_token` | Token de renovación vencido, revocado o reutilizado | Borrar los tokens y volver al inicio de sesión |
| 403 | `https_required` | Petición sin HTTPS en producción | Error de configuración: mostrar `message`. No reintentar |
| 403 | `role_not_allowed` | La cuenta es de administración | Mostrar `message`; no guardar nada |
| 403 | `password_change_required` | La cuenta tiene contraseña provisional | Explicar que se cambia en la web y volver al inicio de sesión |
| 403 | `forbidden` | La cuenta no tiene acceso a esa sesión o reporte, o la acción no le corresponde (por ejemplo, un Usuario que intenta aprobar, o un Docente que no es el asignado) | Mostrar `message` y volver a la pantalla anterior |
| 404 | `not_found` | Sesión o reporte inexistente, o sesión sin reporte en `GET .../report` | En `GET .../report`: la sesión aún no tiene reporte. En lo demás: mostrar `message` y recargar la lista |
| 409 | `conflict` | La acción no corresponde al estado del reporte (ya enviado, ya aprobado, versión reemplazada) o la sesión no terminó o ya tiene reporte | Mostrar `message` y volver a pedir el reporte |
| 422 | `invalid` | Datos rechazados por una regla: reporte sin texto al enviarlo, texto o comentario demasiado largo, fechas invertidas | Mostrar `message` y dejar corregir |
| 429 | `too_many_attempts` | Bloqueo por intentos fallidos de inicio de sesión. Cabecera `Retry-After` en segundos | Deshabilitar el botón durante `Retry-After` segundos |
| 503 | `unavailable` | El servidor no tiene configurado el módulo (sin base de datos, sin clave de tokens o sin clave de cifrado) | Mostrar `message`. Reintentar más tarde |
| 5xx | (sin forma garantizada) | Error inesperado del servidor o del proxy | Tratar como sin conexión: reintentar con espera creciente |

**Errores de esquema.** Si el cuerpo JSON no cumple el esquema (falta un campo,
tipo incorrecto, campo de más) o un parámetro de consulta es inválido, FastAPI
responde `422` con su formato estándar, donde `detail` es una **lista**:

```json
{"detail": [{"type": "missing", "loc": ["body", "password"], "msg": "Field required", "input": {"email": "x"}}]}
```

Es siempre un error del aplicativo: no se muestra al usuario tal cual.

**Sin respuesta** (tiempo agotado, sin red, certificado no válido): no hay
cuerpo. Ver [reintentos](#reintentos-e-idempotencia).

## Autenticación y tokens

| Token | Duración | Dónde se guarda | Uso |
| --- | --- | --- | --- |
| Acceso | 15 minutos (`expires_in`) | **Solo en memoria** | Cabecera `Authorization` |
| Renovación | 30 días desde el inicio de sesión (`refresh_expires_in`); no se extiende al renovar | Almacenamiento cifrado con una clave del Android Keystore | Solo en `POST /mobile/auth/refresh` |

**Renovación.**

- Renovar antes de que venza el acceso (por ejemplo, cuando falten 60 segundos)
  o al recibir `401 invalid_token` o `401 unauthorized`, **una sola vez** por
  llamada rechazada.
- **Una renovación a la vez.** Cada renovación entrega un token de renovación
  nuevo e invalida el anterior. Si se vuelve a usar uno ya reemplazado, el
  servidor lo trata como copiado: **revoca la sesión del dispositivo** y responde
  `401 invalid_refresh_token`. Dos renovaciones en paralelo con el mismo token
  terminan así. El aplicativo debe serializarlas (por ejemplo, con un mutex) y,
  si otra llamada ya renovó mientras esperaba, usar el token nuevo sin renovar.
- **Respuesta perdida.** Si `refresh` no recibe respuesta (sin red, tiempo
  agotado), el servidor pudo haber renovado igual. Reintentar con el mismo token
  puede responder `401 invalid_refresh_token`; en ese caso hay que volver a
  iniciar sesión. Guardar el token nuevo antes de usarlo reduce esta ventana.

**La sesión del dispositivo termina** (y el siguiente `refresh` responde
`401 invalid_refresh_token`) cuando:

- se cierra sesión (`POST /mobile/auth/logout`);
- pasan 30 días desde el inicio de sesión;
- se reutiliza un token de renovación ya reemplazado;
- se cambia o se restablece la contraseña de la cuenta (el token de acceso
  también deja de valer de inmediato);
- la cuenta se desactiva.

Cada inicio de sesión crea una sesión de dispositivo independiente: cerrar una
no cierra las otras.

## Flujo del aplicativo

```text
GET  /mobile/status                         pantalla de carga: versión mínima y servicios
POST /mobile/auth/login                     inicio de sesión
GET  /mobile/summary                        inicio: sesiones de hoy y recientes; del Docente, cuántos reportes esperan su revisión
GET  /mobile/sessions                       mis sesiones (y las del grupo, para el Docente)
GET  /mobile/sessions/{id}                  detalle: línea de tiempo y métricas
GET  /mobile/sessions/{id}/report           reporte de la sesión (404 si aún no tiene)
  Usuario:  POST /mobile/sessions/{id}/report → PUT /mobile/reports/{id} → POST .../submit
  Docente:  POST .../comments, POST .../return o POST .../approve
GET  /mobile/reviews                        del Docente: reportes por revisar
GET  /mobile/statistics                     estadísticas agregadas
POST /mobile/auth/refresh                   antes de que venza el acceso (o ante 401 invalid_token)
POST /mobile/auth/logout                    cerrar sesión
```

Las acciones sobre un reporte devuelven el reporte actualizado, con
`can_edit` y `can_review` recalculados: el aplicativo muestra los botones según
esos campos y no deduce permisos por su cuenta.

---

## Endpoints

Resumen:

| Método y ruta | Token | Éxito | Seguro reintentar |
| --- | --- | --- | --- |
| `GET /mobile/status` | No | 200 | Sí |
| `POST /mobile/auth/login` | No | 200 | Sí |
| `POST /mobile/auth/refresh` | No | 200 | No (ver [renovación](#autenticación-y-tokens)) |
| `POST /mobile/auth/logout` | Sí | 204 | Sí |
| `GET /mobile/summary` | Sí | 200 | Sí |
| `GET /mobile/sessions` | Sí | 200 | Sí |
| `GET /mobile/sessions/{id}` | Sí | 200 | Sí |
| `GET /mobile/sessions/{id}/report` | Sí | 200 | Sí |
| `POST /mobile/sessions/{id}/report` | Sí | 201 | Sí (el segundo responde `409`) |
| `GET /mobile/reports/{id}` | Sí | 200 | Sí |
| `PUT /mobile/reports/{id}` | Sí | 200 | Sí |
| `POST /mobile/reports/{id}/submit` | Sí | 200 | Sí (el segundo responde `409`) |
| `POST /mobile/reports/{id}/comments` | Sí | 200 | **No**: dejaría el comentario dos veces |
| `POST /mobile/reports/{id}/return` | Sí | 200 | Sí (el segundo responde `409`) |
| `POST /mobile/reports/{id}/approve` | Sí | 200 | Sí (el segundo responde `409`) |
| `GET /mobile/reviews` | Sí | 200 | Sí |
| `GET /mobile/statistics` | Sí | 200 | Sí |

### Estado

#### `GET /mobile/status`

Sin token. No devuelve datos personales. Primera llamada al abrir el aplicativo.

**200** — [`Status`](#status)

```json
{
  "status": "ok",
  "api_version": "1.0.0rc1",
  "min_app_version": "1.0.0",
  "server_time": "2026-10-29T14:04:10.922662+00:00",
  "services": {"login": true, "sessions": true, "reports": true, "statistics": true}
}
```

- Si la versión del aplicativo es menor que `min_app_version`, pedir que se
  actualice y no continuar.
- `services.login` falso: el servidor no tiene base de datos o clave de tokens.
  No mostrar el inicio de sesión.
- `services.sessions`, `services.reports` o `services.statistics` falsos: esa
  sección no está disponible (por ejemplo, falta la clave de cifrado). Se
  muestra un aviso en su lugar.
- `server_time`: hora del servidor. Sirve para detectar un reloj del dispositivo
  muy desfasado.

### Autenticación

#### `POST /mobile/auth/login`

Sin token. Misma cuenta que la web. Respeta el bloqueo por intentos fallidos
(por correo y por IP, compartido con la web) y el cambio de contraseña
obligatorio.

| Campo | Tipo | Regla |
| --- | --- | --- |
| `email` | string | 3 a 320 caracteres. No distingue mayúsculas |
| `password` | string | 1 a 256 caracteres |

```json
{"email": "usuario1@example.com", "password": "********"}
```

**200** — [`Tokens`](#tokens)

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

Errores: `401 invalid_credentials`, `403 role_not_allowed`,
`403 password_change_required`, `429 too_many_attempts` (con `Retry-After`),
`503 unavailable`.

#### `POST /mobile/auth/refresh`

Sin token de acceso: el token de renovación va en el cuerpo.

```json
{"refresh_token": "<token de renovación>"}
```

**200** — [`Tokens`](#tokens), con un **nuevo** `refresh_token`.
`refresh_expires_in` es lo que le queda a la sesión del dispositivo: renovar no
la extiende y vence a los 30 días del inicio de sesión.

Errores: `401 invalid_refresh_token` (ver [cuándo termina la
sesión](#autenticación-y-tokens)), `503 unavailable`.

#### `POST /mobile/auth/logout`

Con token, sin cuerpo. **204** sin contenido. Revoca la sesión del dispositivo:
el token de renovación y el de acceso dejan de valer de inmediato.

Si no hay conexión, el aplicativo borra igual sus tokens; la sesión del servidor
vence sola.

### Inicio

#### `GET /mobile/summary`

Con token.

| Parámetro | Tipo | Por defecto | Uso |
| --- | --- | --- | --- |
| `date` | `YYYY-MM-DD` | hoy, según `utc_offset_minutes` | Día de «sesiones de hoy» |
| `utc_offset_minutes` | entero, -720 a 840 | `-300` (Perú) | Desfase horario del dispositivo |
| `limit` | entero, 1 a 50 | `10` | Cuántas sesiones trae `recent_sessions` |

Las sesiones son las mismas que la cuenta ve en la web: las propias y, del
Docente, también las de los usuarios de su grupo.

**200** — [`Summary`](#summary)

```json
{
  "user": {"id": "user-3245af00-...", "email": "docente.a@example.com", "role": "psychologist", "role_name": "Docente"},
  "date": "2026-10-29",
  "today_sessions": [],
  "recent_sessions": [
    {"id": "221e2a72-...", "code": "S-4F7K2Q", "started_at": "2026-10-28T14:04:10.922662+00:00",
     "state": "completed", "audience": "adulto", "protocol_name": "Secuencia breve",
     "mine": false, "report_status": "submitted"}
  ],
  "pending_reviews": 1
}
```

- `today_sessions` y `recent_sessions` van de la más reciente a la más antigua.
- `pending_reviews`: del Docente, cuántos reportes esperan su revisión
  (`GET /mobile/reviews`). Del Usuario, siempre `0`.

Errores: `503 unavailable`. Un parámetro inválido responde `422` de esquema.

### Sesiones

#### `GET /mobile/sessions`

Con token.

| Parámetro | Tipo | Por defecto | Uso |
| --- | --- | --- | --- |
| `limit` | entero, 1 a 500 | `100` | Cuántas sesiones trae |

**200** — lista de [`SessionSummary`](#sessionsummary), de la más reciente a la
más antigua. Puede estar vacía.

Errores: `503 unavailable`.

#### `GET /mobile/sessions/{id}`

Con token. Detalle de una sesión a la que la cuenta tiene acceso
(`can_access_session`: quien la condujo y el Docente de ese usuario).

**200** — [`SessionDetail`](#sessiondetail)

```json
{
  "session": {"id": "221e2a72-...", "code": "S-4F7K2Q", "started_at": "2026-10-28T14:04:10.922662+00:00",
              "state": "completed", "audience": "adulto", "protocol_name": "Secuencia breve",
              "mine": true, "report_status": null},
  "timeline": {
    "session_id": "221e2a72-...", "session_code": "S-4F7K2Q",
    "started_at": "2026-10-28T14:04:10.922662+00:00", "duration_seconds": 31.5,
    "lanes": {
      "questionnaires": [{"time": 2.0, "moment": "pre", "title": "Antes de empezar",
                          "answers": [{"question": "¿Cómo estás?", "kind": "faces", "answer": 4}]}],
      "stimuli": [{"step_index": 0, "title": "Paisaje", "kind": "emotional", "start": 8.1, "end": 14.1, "skipped": false},
                  {"step_index": 1, "title": "", "kind": "practice", "start": 14.1, "end": 21.3, "skipped": false,
                   "target_expression": "happiness", "outcome": "achieved", "seconds_to_achieve": 4.5}],
      "captures": [{"time": 10.1, "step_index": 0, "emotion": "happiness", "probability": 0.8, "quality": "good"}],
      "said": [{"time": 25.0, "step_index": 2, "title": "Mancha", "text": "Una nube"}],
      "markers": [{"time": 11.0, "kind": "laughed", "note": null}],
      "heart_rate": []
    }
  },
  "metrics": {
    "session_id": "221e2a72-...",
    "emotional": [{"step_index": 0, "stimulus_id": "...", "title": "Paisaje", "category": "alegría", "skipped": false,
                   "expected_expression": "happiness", "captures": [], "counted": true,
                   "matches_expected": true, "excluded_captures": 0}],
    "abstract": [],
    "totals": {"emotional_stimuli": 1, "counted": 1, "matched": 1, "excluded_captures": 0,
               "sentence": "En 1 de 1 estímulo la expresión estimada coincidió con la esperada."},
    "abstract_notice": null,
    "practice": {
      "exercises": [{"step_index": 1, "target_expression": "happiness", "hold_seconds": 2, "max_seconds": 15,
                     "outcome": "achieved", "seconds_to_achieve": 4.5, "peak_level": 0.86,
                     "relative_to_calibration": true, "feedback_visible": true}],
      "totals": {"exercises": 1, "applied": 1, "achieved": 1, "skipped": 0, "stopped": 0, "not_reached": 0,
                 "average_seconds_to_achieve": 4.5, "feedback_visible": 1,
                 "sentence": "Logró la expresión pedida en 1 de 1 ejercicio.",
                 "average_sentence": "Tiempo promedio hasta lograrla: 4,5 s (solo los ejercicios logrados).",
                 "feedback_sentence": "La señal visual estuvo activa en todos los ejercicios."},
      "by_target": [{"target_expression": "happiness", "applied": 1, "achieved": 1, "skipped": 0, "stopped": 0,
                     "average_seconds_to_achieve": 4.5}],
      "notice": "Los modelos de expresión se entrenaron principalmente con rostros de adultos y su precisión con niños no está validada. El resultado describe el ejercicio, no el estado emocional de la persona."
    }
  }
}
```

- `timeline` y `metrics` son los mismos objetos que la web
  (`GET /sessions/{id}/timeline` y `GET /sessions/{id}/metrics`). El aplicativo
  usa los campos que necesita e ignora el resto.
- `metrics.totals.sentence` y `metrics.abstract_notice` se muestran tal cual.
  Si `abstract_notice` no es `null`, va junto a las imágenes abstractas.
- `heart_rate` está reservado para un sensor futuro y viene vacío.
- Desde la revisión 4.1, `metrics.practice` trae los ejercicios de práctica
  ([`Practice`](#practice)) y es `null` si el protocolo no tenía ninguno. En
  `lanes.stimuli`, un ejercicio llega con `kind` `practice` y los campos
  `target_expression`, `outcome` y `seconds_to_achieve`. Un aplicativo que
  ignore estos campos sigue funcionando.
- Si `metrics.practice` no es `null`, `practice.notice` se muestra siempre junto
  a los ejercicios. `practice.totals.sentence`, `average_sentence` y
  `feedback_sentence` se muestran tal cual (los dos últimos, si no son `null`).

Errores: `403 forbidden`, `404 not_found`, `503 unavailable`.

### Reporte

Lo redacta quien condujo la sesión y lo revisa el Docente asignado a ese
Usuario. Si quien condujo es un Docente, al enviarlo queda aprobado sin
revisión. Estados: `draft` → `submitted` → `changes_requested` o `approved`;
con observaciones, el Usuario corrige el texto y lo vuelve a enviar. Un reporte
aprobado no se edita desde el aplicativo (las versiones nuevas se crean en la
web).

#### `GET /mobile/sessions/{id}/report`

Con token. El reporte vigente de la sesión.

**200** — [`Report`](#report). Errores: `403 forbidden`; `404 not_found` si la
sesión no existe **o aún no tiene reporte** (si `session.mine` es verdadero y
la sesión terminó, el aplicativo ofrece «Empezar el reporte»).

#### `POST /mobile/sessions/{id}/report`

Con token, sin cuerpo. Solo quien condujo la sesión, cuando ya terminó. Crea el
reporte en borrador.

**201** — [`Report`](#report). Errores: `403 forbidden` (no la condujo),
`409 conflict` (la sesión no terminó o ya tiene reporte), `404 not_found`.

#### `GET /mobile/reports/{id}`

Con token. **200** — [`Report`](#report). Errores: `403`, `404`.

#### `PUT /mobile/reports/{id}`

Con token. Solo el autor, con `can_edit` verdadero (borrador o con
observaciones). Así responde el Usuario a los comentarios del Docente.

| Campo | Tipo | Regla |
| --- | --- | --- |
| `narrative` | string | Hasta 8000 caracteres |

```json
{"narrative": "La persona observó las imágenes con atención y pidió una pausa breve."}
```

**200** — [`Report`](#report). Errores: `403 forbidden`, `409 conflict` (en
revisión o aprobado), `422 invalid`.

#### `POST /mobile/reports/{id}/submit`

Con token, sin cuerpo. Solo el autor. Envía a revisión (o, si el autor es
Docente, queda aprobado).

**200** — [`Report`](#report). Errores: `403 forbidden`, `409 conflict` (ya
enviado o el Usuario no tiene Docente asignado), `422 invalid` (sin texto).

#### `POST /mobile/reports/{id}/comments`

Con token. Solo el Docente asignado, con el reporte en `submitted`.

| Campo | Tipo | Regla |
| --- | --- | --- |
| `section` | string | [`section`](#valores-enumerados). Opcional, por defecto `general` |
| `text` | string | 1 a 2000 caracteres |

```json
{"section": "narrative", "text": "Describe la pausa con más detalle."}
```

**200** — [`Report`](#report) con el comentario en `comments`. Errores:
`403 forbidden`, `409 conflict`, `422 invalid`.

#### `POST /mobile/reports/{id}/return`

Con token, sin cuerpo. Solo el Docente asignado. Devuelve el reporte con
observaciones (`changes_requested`).

**200** — [`Report`](#report). Errores: `403 forbidden`, `409 conflict`.

#### `POST /mobile/reports/{id}/approve`

Con token, sin cuerpo. Solo el Docente asignado. **200** — [`Report`](#report)
en `approved`. Errores: `403 forbidden`, `409 conflict`.

### Pendientes del Docente

#### `GET /mobile/reviews`

Con token. Solo Docente (`403 forbidden` para el Usuario).

**200** — lista de [`SessionSummary`](#sessionsummary) con un campo más,
`report_id` (string), de las sesiones de su grupo cuyo reporte vigente espera su
revisión. De la más reciente a la más antigua; puede estar vacía.

### Estadísticas

#### `GET /mobile/statistics`

Con token.

| Parámetro | Tipo | Por defecto | Uso |
| --- | --- | --- | --- |
| `scope` | `mine` o `group` | `mine` | `group` solo para el Docente: las sesiones de su grupo (`403` para el Usuario) |
| `date_from` | `YYYY-MM-DD` | sin límite | Desde (inclusive) |
| `date_to` | `YYYY-MM-DD` | sin límite | Hasta (inclusive). Anterior a `date_from`: `422 invalid` |

**200** — [`Statistics`](#statistics)

```json
{
  "scope": "mine",
  "notice": "Estas estadísticas cuentan sesiones, no personas, y son estimaciones. ...",
  "few_sessions_notice": "Hay pocas sesiones para sacar conclusiones.",
  "sessions": {"total": 3, "completed": 2, "interrupted": 1, "average_duration_seconds": 184.5},
  "expressions": {"counted_captures": 12, "excluded_captures": 3,
                  "rows": [{"expression": "happiness", "captures": 6, "percent": 50.0, "sessions": 2}]},
  "coincidence": {"compared": 4, "matched": 3},
  "practice": {
    "sessions": 2,
    "totals": {"applied": 3, "achieved": 2, "skipped": 1, "stopped": 0, "average_seconds_to_achieve": 3.0,
               "feedback_visible": 2, "sentence": "Logró la expresión pedida en 2 de 3 ejercicios.",
               "average_sentence": "Tiempo promedio hasta lograrla: 3 s (solo los ejercicios logrados).",
               "feedback_sentence": "La señal visual estuvo activa en 2 de 3 ejercicios."},
    "by_protocol": [{"family_id": "...", "name": "Alegría y sorpresa", "sessions": 2, "applied": 3, "achieved": 2,
                     "skipped": 1, "stopped": 0, "average_seconds_to_achieve": 3.0}],
    "by_target": [{"target_expression": "happiness", "applied": 2, "achieved": 2, "skipped": 0, "stopped": 0,
                   "average_seconds_to_achieve": 3.0},
                  {"target_expression": "surprise", "applied": 1, "achieved": 0, "skipped": 1, "stopped": 0,
                   "average_seconds_to_achieve": null}],
    "notice": "Los modelos de expresión se entrenaron principalmente con rostros de adultos y su precisión con niños no está validada. El resultado describe el ejercicio, no el estado emocional de la persona."
  }
}
```

- `notice` se muestra siempre; `few_sessions_notice` cuando no es `null`.
- No hay filas por usuario ni por persona.
- Desde la revisión 4.1, `practice` trae los ejercicios de práctica agregados
  ([`StatisticsPractice`](#statisticspractice)), aparte de `coincidence`; es
  `null` si ninguna sesión tuvo ejercicios. `practice.notice` se muestra siempre
  junto a ellos. A diferencia de la web, no trae el desglose por usuario.

Errores: `403 forbidden`, `422 invalid`, `503 unavailable`.

---

## Tipos de datos

Columna «Nulo»: **sí** si el campo puede ser `null` (siempre viene). Tipos:
`string`, `int` (entero), `number` (entero o decimal), `boolean`, `datetime`
(ISO 8601 con zona), `date` (`YYYY-MM-DD`).

### `Status`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `status` | string | no | Siempre `ok` |
| `api_version` | string | no | Informativa |
| `min_app_version` | string | no | `x.y.z` |
| `server_time` | datetime | no | UTC |
| `services.login` | boolean | no | |
| `services.sessions` | boolean | no | Sesiones y su detalle |
| `services.reports` | boolean | no | |
| `services.statistics` | boolean | no | |

### `Tokens`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `access_token` | string | no | Opaco. No se decodifica en el aplicativo |
| `token_type` | string | no | Siempre `bearer` |
| `expires_in` | int | no | Segundos (900) |
| `refresh_token` | string | no | Opaco, hasta 256 caracteres |
| `refresh_expires_in` | int | no | Segundos que le quedan a la sesión del dispositivo |
| `user` | [`User`](#user) | no | |

### `User`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `id` | string | no | |
| `email` | string | no | |
| `role` | string | no | `student` o `psychologist` |
| `role_name` | string | no | Texto visible: «Usuario» o «Docente» |

### `Summary`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `user` | [`User`](#user) | no | |
| `date` | date | no | Día consultado |
| `today_sessions` | lista de [`SessionSummary`](#sessionsummary) | no | Puede estar vacía |
| `recent_sessions` | lista de [`SessionSummary`](#sessionsummary) | no | Las `limit` más recientes. Puede estar vacía |
| `pending_reviews` | int | no | Reportes que esperan la revisión de este Docente; `0` para el Usuario |

### `SessionSummary`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `id` | string | no | |
| `code` | string | sí | Código de la sesión (`S-` y 6 caracteres). `null` solo en sesiones anteriores a la revisión 3 |
| `started_at` | datetime | no | |
| `state` | string | no | [`state`](#valores-enumerados) |
| `audience` | string | no | [`audience`](#valores-enumerados) |
| `protocol_name` | string | sí | `null` sin protocolo |
| `mine` | boolean | no | `true` si la condujo esta cuenta; `false` en las del grupo del Docente |
| `report_status` | string | sí | [`report_status`](#valores-enumerados) del reporte vigente; `null` si no tiene |

### `SessionDetail`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `session` | [`SessionSummary`](#sessionsummary) | no | |
| `timeline` | [`Timeline`](#timeline) | no | |
| `metrics` | [`Metrics`](#metrics) | no | |

### `Timeline`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `session_code` | string | sí | |
| `duration_seconds` | number | no | Último tiempo registrado |
| `lanes.questionnaires[]` | objeto | no | `time` (number, nulo), `moment` (`pre`/`post`), `title`, `answers[]` con `question`, `kind` y `answer` (cualquier tipo JSON, nulo si no respondió) |
| `lanes.stimuli[]` | objeto | no | `step_index` (int), `title`, `kind` ([`kind`](#valores-enumerados)), `start` y `end` (number, nulos), `skipped` (boolean). Con `kind` `practice` (4.1): `target_expression` (string), `outcome` ([`practice_outcome`](#valores-enumerados), nulo si el ejercicio sigue en curso) y `seconds_to_achieve` (number, nulo) |
| `lanes.captures[]` | objeto | no | `time` (number), `step_index` (int, nulo), `emotion` (string, nulo: expresión **estimada**), `probability` (number, nulo), `quality` ([`quality`](#valores-enumerados)) |
| `lanes.said[]` | objeto | no | Lo que la persona dijo ver en una imagen abstracta: `time`, `step_index`, `title`, `text` |
| `lanes.markers[]` | objeto | no | `time`, `kind` ([`marker`](#valores-enumerados)), `note` (nulo) |
| `lanes.heart_rate` | lista | no | Reservado; siempre vacía |

### `Metrics`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `emotional[]` | objeto | no | Por estímulo emocional: `step_index`, `title`, `category`, `skipped`, `expected_expression` (nulo), `counted` (boolean), `matches_expected` (boolean, nulo), `excluded_captures` (int) |
| `abstract[]` | objeto | no | Por imagen abstracta: `step_index`, `title`, `skipped`, `said` (string, nulo) |
| `totals.emotional_stimuli` | int | no | |
| `totals.counted` | int | no | Estímulos con una captura de buena calidad |
| `totals.matched` | int | no | |
| `totals.excluded_captures` | int | no | |
| `totals.sentence` | string | no | Texto para mostrar |
| `abstract_notice` | string | sí | Aviso de que una sesión breve no permite concluir |
| `practice` | [`Practice`](#practice) | sí | Desde 4.1. Ejercicios de práctica; `null` si el protocolo no tenía ninguno. Puede faltar en un servidor anterior: tratarlo como `null` |

### `Practice`

Ejercicios de práctica de una sesión (revisión 4.1). Se pide una expresión y se
registra si la persona la sostuvo. Describen el ejercicio; no valoran a nadie.
Un ejercicio cuenta en el total cuando llegó a su final (logrado o con el tiempo
vencido); los saltados, el que quedó a medias al detener la sesión y los no
aplicados se informan aparte.

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `exercises[]` | objeto | no | Por ejercicio, en orden: `step_index` (int), `target_expression` (string), `hold_seconds` (int), `max_seconds` (int), `outcome` ([`practice_outcome`](#valores-enumerados), nulo si la sesión no llegó a él), `seconds_to_achieve` (number, nulo), `peak_level` (number de 0 a 1, nulo), `relative_to_calibration` (boolean, nulo), `feedback_visible` (boolean, nulo) |
| `totals` | [`PracticeTotals`](#practicetotals) | no | Además: `exercises` (int, todos los del protocolo) y `not_reached` (int) |
| `by_target[]` | [`PracticeRow`](#practicerow) | no | Por expresión pedida, con `target_expression` |
| `notice` | string | no | Aviso fijo: se muestra siempre junto a los ejercicios |

### `PracticeTotals`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `applied` | int | no | Ejercicios que llegaron a su final |
| `achieved` | int | no | |
| `skipped`, `stopped` | int | no | No cuentan en `applied` |
| `average_seconds_to_achieve` | number | sí | Solo de los logrados |
| `feedback_visible` | int | no | De los `applied`, en cuántos estuvo activa la señal visual |
| `sentence` | string | no | Texto para mostrar |
| `average_sentence`, `feedback_sentence` | string | sí | Textos para mostrar |

### `PracticeRow`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `applied`, `achieved`, `skipped`, `stopped` | int | no | |
| `average_seconds_to_achieve` | number | sí | Solo de los logrados |

### `Report`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `id` | string | no | |
| `version` | int | no | |
| `status` | string | no | [`report_status`](#valores-enumerados) |
| `current` | boolean | no | `false` si una versión nueva la reemplazó |
| `narrative` | string | no | Texto del reporte (vacío en un borrador nuevo) |
| `created_at`, `updated_at` | datetime | no | |
| `approved_at` | datetime | sí | |
| `session_code` | string | sí | |
| `estimates_notice` | string | no | Se muestra siempre junto a las expresiones |
| `abstract_notice` | string | sí | |
| `timeline` | [`Timeline`](#timeline) | no | |
| `metrics` | [`Metrics`](#metrics) | no | |
| `authored_by_me` | boolean | no | |
| `requires_review` | boolean | no | `false` si el autor es Docente |
| `can_edit` | boolean | no | Mostrar «Editar» y «Enviar» |
| `can_review` | boolean | no | Mostrar «Comentar», «Devolver» y «Aprobar» |
| `comments[]` | objeto | no | `id`, `section` ([`section`](#valores-enumerados)), `text`, `created_at` |
| `history[]` | objeto | no | Sin contenido: `action` ([`report_action`](#valores-enumerados)), `occurred_at`, `version` (int, nulo), `by` (`author` o `docente`) |

### `Statistics`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `scope` | string | no | `mine` o `group` |
| `notice` | string | no | |
| `few_sessions_notice` | string | sí | |
| `sessions.total`, `sessions.completed`, `sessions.interrupted` | int | no | Número de sesiones |
| `sessions.average_duration_seconds` | number | sí | De las sesiones completas |
| `expressions.counted_captures`, `expressions.excluded_captures` | int | no | |
| `expressions.rows[]` | objeto | no | `expression`, `captures` (int), `percent` (number), `sessions` (int) |
| `coincidence.compared`, `coincidence.matched` | int | no | Estímulos emocionales comparados y en los que coincidió la expresión estimada |
| `practice` | [`StatisticsPractice`](#statisticspractice) | sí | Desde 4.1; `null` si ninguna sesión tuvo ejercicios. Puede faltar en un servidor anterior |

### `StatisticsPractice`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `sessions` | int | no | Sesiones con ejercicios |
| `totals` | [`PracticeTotals`](#practicetotals) | no | |
| `by_protocol[]` | [`PracticeRow`](#practicerow) | no | Con `family_id`, `name` y `sessions` (int) |
| `by_target[]` | [`PracticeRow`](#practicerow) | no | Con `target_expression` |
| `notice` | string | no | Aviso fijo: se muestra siempre junto a los ejercicios |

## Valores enumerados

«Abierta»: el servidor puede agregar valores sin subir la revisión mayor; el
aplicativo debe tolerar valores desconocidos (ver
[compatibilidad](#compatibilidad-entre-versiones)).

| Enumeración | Valores | Abierta |
| --- | --- | --- |
| `role` | `student` (Usuario), `psychologist` (Docente) | No |
| `audience` | `propia` (Conmigo), `adulto` (Un adulto), `infantil` (Un niño o niña) | No |
| `state` (sesión) | `in_progress`, `completed`, `cancelled`; `created` y `recognized` en sesiones de actividades de la web | Sí |
| `report_status` | `draft` (borrador), `submitted` (en revisión), `changes_requested` (con observaciones), `approved` (aprobado) | No |
| `section` | `timeline`, `metrics`, `questionnaires`, `narrative`, `general` | No |
| `report_action` | `created`, `edited`, `submitted`, `commented`, `returned`, `approved`, `closed`, `new_version`, `printed` | Sí |
| `kind` (estímulo) | `emotional`, `abstract`; `practice` (4.1) en la línea de tiempo | Sí |
| `practice_outcome` | `achieved` (logró la expresión pedida), `timed_out` (terminó el tiempo), `skipped` (se saltó), `stopped` (la sesión se detuvo) | Sí |
| `target_expression` | `happiness`, `surprise`, `sadness`, `anger`, `fear`, `disgust`, `neutral` (cara tranquila) | Sí |
| `quality` (captura) | `good`, `flagged` | Sí |
| `marker` | `distracted`, `laughed`, `asked_to_stop`, `cried`, `note` | Sí |
| `expression` / `emotion` | Claves de expresión del modelo (`happiness`, `neutral`, `sadness`, …). Se muestran con su nombre en español, sin colores ni valoraciones | Sí |

## Reintentos e idempotencia

| Situación | Qué hacer |
| --- | --- |
| Sin respuesta en una lectura (`GET`) | Reintentar con espera creciente (1, 2, 4… hasta 30 segundos) |
| Sin respuesta en `POST .../report`, `submit`, `return` o `approve` | Volver a pedir el reporte (`GET`) y decidir según su `status` |
| Sin respuesta en `PUT /mobile/reports/{id}` | Reintentar con el mismo texto |
| Sin respuesta en `comments` | No reintentar: volver a pedir el reporte y ver si el comentario quedó |
| Sin respuesta en `refresh` | Ver [respuesta perdida](#autenticación-y-tokens) |
| `5xx` | Igual que sin respuesta |
| `429 too_many_attempts` | Esperar `Retry-After` segundos antes de otro inicio de sesión |

Tiempo de espera sugerido: 10 segundos.

## Obligaciones de privacidad del aplicativo

El servidor hace cumplir el acceso; estas obligaciones son del aplicativo, porque
el servidor no las puede comprobar:

- El aplicativo no usa la cámara ni envía imágenes.
- Ningún dato de las sesiones (línea de tiempo, métricas, reporte, comentarios ni
  estadísticas) se guarda en disco, caché ni registros. Vive en memoria mientras
  se muestra.
- Solo se guarda el token de renovación (cifrado con el Android Keystore). Al
  cerrar sesión se borra todo.
- Ningún token, respuesta, código de sesión ni texto de reporte aparece en los
  registros.
- No se pide ni se muestra el nombre, el DNI ni una foto de nadie: la sesión se
  identifica solo por su código.
- Las expresiones se muestran como **estimadas**, con `estimates_notice` o
  `notice` a la vista, sin colores ni valoraciones por expresión. El aplicativo no
  calcula puntajes ni interpreta respuestas.
- Los ejercicios de práctica se muestran con su `notice` a la vista y con los
  textos del servidor; el aplicativo no los valora («bien», «mal») ni los
  presenta como el estado emocional de la persona.

## Configuración del servidor

| Variable | Por defecto | Uso |
| --- | --- | --- |
| `MOBILE_MIN_APP_VERSION` | `1.0.0` | Versión mínima del aplicativo (`x.y.z`). Con la revisión 4 debe ser la primera versión del aplicativo que la usa |
| `ENVIRONMENT` | `development` | Con `production`, `/mobile` exige HTTPS |
| `LOGIN_MAX_FAILURES_PER_ACCOUNT`, `LOGIN_MAX_FAILURES_PER_IP`, `LOGIN_ATTEMPT_WINDOW_MINUTES` | 5, 20, 15 | Bloqueo por intentos fallidos (compartido con la web) |

Detrás de nginx, la API conoce el esquema por `X-Forwarded-Proto`: nginx
reenvía `https` cuando lo recibe del proxy TLS (Caddy o el de la institución).
En Docker, la web y la API se publican en el puerto `8080` del equipo (nginx);
la API (`8000`) no se publica fuera de Docker.

## Historial

| Revisión | Fecha | Cambios |
| --- | --- | --- |
| 4.1 | 2026-10-30 | Compatible con la 4: solo campos nuevos y opcionales. `GET /mobile/sessions/{id}` agrega `metrics.practice` ([`Practice`](#practice)) y, en `lanes.stimuli`, los ejercicios con `kind` `practice`, `target_expression`, `outcome` y `seconds_to_achieve`. `GET /mobile/statistics` agrega `practice` ([`StatisticsPractice`](#statisticspractice)), sin desglose por usuario. Los reportes (`metrics`) traen el mismo bloque. Nuevas enumeraciones `practice_outcome` y `target_expression`. No hay rutas nuevas: el aplicativo sigue sin conducir sesiones ni enviar imágenes |
| 4 | 2026-10-29 | **Incompatible**: el aplicativo deja de conducir sesiones, para que ninguna captura del rostro salga del teléfono. Se quitan `GET /mobile/protocols`, `POST /mobile/sessions`, `next`, cuestionarios, `advance`, `calibration`, `frames`, `skip`, `finish`, `stop` y las imágenes de estímulos. `Summary` quita `protocols` y `audiences` y agrega `pending_reviews`; incluye las sesiones del grupo del Docente. `SessionSummary` quita `guided_phase` y agrega `mine` y `report_status`. Nuevos: `GET /mobile/sessions`, `GET /mobile/sessions/{id}` (línea de tiempo y métricas), reporte (`GET`/`POST /mobile/sessions/{id}/report`, `GET`/`PUT /mobile/reports/{id}`, `submit`, `comments`, `return`, `approve`), `GET /mobile/reviews` y `GET /mobile/statistics`. `services` agrega `reports` y `statistics`. Se quitan los errores `413`, `415`, `428` y `invalid_or_expired_url` |
| 3 | 2026-10-26 | **Incompatible**: se quitan los participantes. `POST /mobile/sessions` recibe `protocol_id` o `session_type` (propia, adulto, infantil) y `authorization_confirmed`; ya no recibe `participant_id`. Se quita `POST .../confirm` y la fase `confirmation`. `GET /mobile/protocols` no lleva parámetros y trae `audience` y `confirmation`. `Summary` cambia `participants` por `recent_sessions`, `protocols` y `audiences`; `SessionSummary` cambia `participant_id`/`participant_code` por `code` y `audience`. `services.participant_sessions` pasa a `services.sessions`. Nueva fase `live` y `POST .../finish` para sesiones sin protocolo. `next` y `StartedSession` traen el `code` de la sesión. Nuevo error `428 child_notice_required` |
| 2 | 2026-10-24 | Solo documentación; la API no cambió. Se agregan: convenciones (nulos, fechas, campos de más), reglas de compatibilidad y enumeraciones abiertas, acción del aplicativo para cada error, renovación serializada y respuesta perdida, tabla de reintentos e idempotencia, tipos de cada objeto con nulabilidad, máquina de fases, detalles de calibración y capturas, cómo retomar una sesión, `stop` idempotente, `404` de imágenes y obligaciones de privacidad del aplicativo |
| 1 | 2026-10-23 | Primera versión del contrato con la API móvil |
