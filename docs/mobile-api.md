# API del aplicativo móvil (contrato)

Contrato entre la API de EMOtv y el aplicativo Android (repositorio
`EMOtv-android`). **Este archivo es la fuente de verdad y se copia tal cual al
proyecto Android** (`docs/mobile-api.md`). Si cambia aquí, se vuelve a copiar.

| | |
| --- | --- |
| Revisión del contrato | 2 (2026-10-24). Ver [historial](#historial) |
| Versión de la API | La que devuelve `GET /mobile/status` en `api_version` (hoy `1.0.0rc1`) |
| Prefijo | Todas las rutas empiezan con `/mobile` |
| Formato | JSON en UTF-8, salvo el envío de cuadros (`image/jpeg`) y las imágenes de estímulos |

La API móvil no tiene reglas propias: llama a los mismos servicios que la web
(`can_access_participant`, autorizaciones, compromiso de confidencialidad,
protocolos, cuestionarios y sesión guiada). **Lo que la web rechaza, el
aplicativo también lo rechaza**, y toda restricción la impone el servidor.

## Contenido

1. [Reglas generales](#reglas-generales)
2. [Convenciones](#convenciones)
3. [Compatibilidad entre versiones](#compatibilidad-entre-versiones)
4. [Errores](#errores)
5. [Autenticación y tokens](#autenticación-y-tokens)
6. [Flujo del aplicativo](#flujo-del-aplicativo)
7. [Endpoints](#endpoints)
8. [Sesión guiada: fases y ciclo](#sesión-guiada-fases-y-ciclo)
9. [Tipos de datos](#tipos-de-datos)
10. [Valores enumerados](#valores-enumerados)
11. [Reintentos e idempotencia](#reintentos-e-idempotencia)
12. [Obligaciones de privacidad del aplicativo](#obligaciones-de-privacidad-del-aplicativo)
13. [Configuración del servidor](#configuración-del-servidor)
14. [Historial](#historial)

---

## Reglas generales

| Regla | Detalle |
| --- | --- |
| HTTPS | En producción (`ENVIRONMENT=production`), toda ruta `/mobile` responde `403 https_required` si la petición no llega por HTTPS |
| Quién usa el aplicativo | Solo **usuarios** (`student`) y **docentes** (`psychologist`). Administrador y superadministrador: `403 role_not_allowed`. Los participantes no tienen cuenta |
| Tokens | Acceso: 15 minutos, cabecera `Authorization: Bearer <token de acceso>`. Renovación: 30 días desde el inicio de sesión, cambia en cada renovación |
| Separación web/móvil | Un token del aplicativo no sirve en la web y uno de la web no sirve en `/mobile` (`401 invalid_token`) |
| Caché | Todas las respuestas llevan `Cache-Control: no-store`. El aplicativo no guarda respuestas en disco |
| Imágenes | **Ninguna imagen de una persona se guarda ni sale del servidor.** Los cuadros se analizan en memoria con el modelo local y se descartan. Las únicas imágenes que el aplicativo descarga son los estímulos |
| Resultados | Ninguna respuesta incluye la expresión estimada, probabilidades ni capturas: el dispositivo lo ve el participante. Los resultados se consultan en la web |
| Participantes | Solo se identifican por código, tipo y edad. Ninguna respuesta trae nombre, DNI ni foto |
| Registros | El servidor no registra cuerpos de peticiones (contraseñas, respuestas ni cuadros) |
| Auditoría | Se auditan, sin contenido: inicio y cierre de sesión (también los rechazados por papel), el resumen, cada consulta a un participante (también las denegadas), la sesión guiada y cada imagen de estímulo servida o rechazada |

## Convenciones

| Tema | Regla |
| --- | --- |
| URL base | Las rutas de este documento son absolutas desde la raíz del servidor (`https://servidor/mobile/...`). `image_url` también es una ruta: se resuelve contra la misma URL base |
| Cabeceras | `Authorization: Bearer <token de acceso>` en todo endpoint marcado «Con token». `Content-Type: application/json` en los cuerpos JSON e `image/jpeg` en los cuadros |
| Campos desconocidos en peticiones | Se rechazan: un cuerpo con un campo que no está en este contrato responde `422` con el formato de FastAPI. No enviar campos de más |
| Campos desconocidos en respuestas | El aplicativo **debe ignorarlos** (`ignoreUnknownKeys`). El servidor puede agregar campos sin cambiar la revisión mayor |
| Nulos | Un campo marcado «nulable» viene siempre, con valor o `null`. Ningún campo documentado se omite |
| Identificadores | Cadenas opacas (UUID o `user-<uuid>`). No se interpretan ni se arman en el aplicativo |
| Fechas y horas | ISO 8601 con zona: `2026-10-23T14:04:10.922662+00:00` (UTC). La fracción de segundo es opcional. Las fechas sin hora: `YYYY-MM-DD` |
| Duraciones | `expires_in` y `refresh_expires_in` en segundos enteros; `exposure_seconds` y `remaining_seconds` en segundos (número, puede tener decimales); `frame_interval_ms` en milisegundos enteros |
| Textos | En español y listos para mostrar: `message`, `warnings`, `reminder`, `notice`, `abstract_notice`, `role_name` y los textos de cuestionarios. El aplicativo no los traduce ni los reescribe |
| Códigos HTTP de éxito | `200`, salvo `201` en `POST /mobile/sessions` y `POST .../questionnaires/{moment}`, y `204` sin cuerpo en `POST /mobile/auth/logout` |

## Compatibilidad entre versiones

- **Cambios compatibles** (no exigen actualizar el aplicativo): campos nuevos en
  respuestas, endpoints nuevos, valores nuevos en enumeraciones marcadas como
  «abiertas» en [valores enumerados](#valores-enumerados) y mensajes distintos.
- **Cambios incompatibles** (quitar o renombrar un campo, cambiar un tipo, cambiar
  el significado de un `code`): suben `MOBILE_MIN_APP_VERSION`. El aplicativo
  que queda por debajo lo detecta en `GET /mobile/status` y pide actualizarse.
- Ante un valor desconocido de una enumeración abierta, el aplicativo no falla:
  - `phase` desconocida: no envía cuadros, muestra «Espera un momento» y sigue
    consultando `GET .../next`.
  - `capture_status`, `missing` o `code` desconocidos: usa el texto
    (`warnings`, `message`) si lo hay; si no, lo ignora.
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
| 403 | `forbidden` | La cuenta no tiene acceso a ese participante o sesión | Mostrar `message`; en una sesión, salir del modo sesión |
| 403 | `invalid_or_expired_url` | URL de imagen vencida, alterada o de una sesión que ya no está activa | Pedir `GET .../next` (trae una URL nueva o la fase terminal) |
| 404 | `not_found` | Participante, protocolo, cuestionario, sesión o imagen inexistente (o ajeno) | Mostrar `message`; recargar el resumen |
| 409 | `conflict` | La acción no corresponde a la fase actual, la sesión terminó, falta la autorización o el protocolo no se puede usar | Pedir `GET .../next` y seguir la fase que indique. Al iniciar una sesión: mostrar `message` |
| 413 | `too_large` | Cuadro de más de 1 000 000 bytes | Bajar la calidad o la resolución del siguiente cuadro |
| 415 | `unsupported_media_type` | Cuadro sin `Content-Type: image/jpeg` | Error interno |
| 422 | `invalid` | Datos rechazados por una regla: falta una confirmación, una respuesta obligatoria, valor fuera de rango o cuadro que no es un JPEG válido | Mostrar `message` y dejar corregir. En cuadros: descartar y enviar el siguiente |
| 428 | `commitment_required` | La cuenta no aceptó el compromiso de confidencialidad vigente | Explicar que se acepta en la web |
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
GET  /mobile/summary                        dashboard (y sesiones en curso para retomar)
GET  /mobile/protocols?participant_id=...   elegir protocolo
POST /mobile/sessions                       iniciar sesión con participante
POST /mobile/sessions/{id}/confirm          confirmación previa
loop:
  GET  /mobile/sessions/{id}/next           qué mostrar ahora
  ├─ cuestionario  → POST .../questionnaires/{pre|post}  (o .../advance si answered)
  ├─ calibración   → POST .../calibration, luego cuadros mientras send_frames
  ├─ estímulo      → GET image_url, cuadros mientras send_frames
  └─ fin           → finished o stopped
POST /mobile/sessions/{id}/stop             interrumpir en cualquier momento
POST /mobile/auth/refresh                   antes de que venza el acceso (o ante 401 invalid_token)
POST /mobile/auth/logout                    cerrar sesión
```

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
| `GET /mobile/protocols` | Sí | 200 | Sí |
| `POST /mobile/sessions` | Sí | 201 | **No**: puede crear dos sesiones |
| `POST /mobile/sessions/{id}/confirm` | Sí | 200 | Sí (el segundo responde `409`) |
| `GET /mobile/sessions/{id}/next` | Sí | 200 | Sí |
| `POST /mobile/sessions/{id}/questionnaires/{moment}` | Sí | 201 | Sí (el segundo responde `409`) |
| `POST /mobile/sessions/{id}/advance` | Sí | 200 | Sí (el segundo responde `409`) |
| `POST /mobile/sessions/{id}/calibration` | Sí | 200 | Sí, pero reinicia la calibración |
| `POST /mobile/sessions/{id}/frames` | Sí | 200 | No: se descarta y se envía el siguiente |
| `POST /mobile/sessions/{id}/skip` | Sí | 200 | **No**: saltaría otro estímulo |
| `POST /mobile/sessions/{id}/stop` | Sí | 200 | Sí |
| `GET /mobile/stimulus-images/...` | No (URL firmada) | 200 | Sí, hasta que vence |

### Estado

#### `GET /mobile/status`

Sin token. No devuelve datos personales. Primera llamada al abrir el aplicativo.

**200** — [`Status`](#status)

```json
{
  "status": "ok",
  "api_version": "1.0.0rc1",
  "min_app_version": "1.0.0",
  "server_time": "2026-10-23T14:04:10.922662+00:00",
  "services": {"login": true, "participant_sessions": true}
}
```

- Si la versión del aplicativo es menor que `min_app_version`, pedir que se
  actualice y no continuar.
- `services.login` falso: el servidor no tiene base de datos o clave de tokens.
  No mostrar el inicio de sesión.
- `services.participant_sessions` falso: no se pueden conducir sesiones (por
  ejemplo, falta la clave de cifrado). Se puede iniciar sesión, pero no iniciar
  sesiones con participantes.
- `server_time`: hora del servidor. Sirve para detectar un reloj del dispositivo
  muy desfasado; los tiempos de la sesión los lleva siempre el servidor.

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

### Dashboard

#### `GET /mobile/summary`

Con token.

| Parámetro | Tipo | Por defecto | Uso |
| --- | --- | --- | --- |
| `date` | `YYYY-MM-DD` | hoy, según `utc_offset_minutes` | Día de «sesiones del día» |
| `utc_offset_minutes` | entero, -720 a 840 | `-300` (Perú) | Desfase horario del dispositivo |

Solo datos de la cuenta que inició sesión: sus participantes y sus sesiones.
Un docente tampoco ve aquí los participantes de los usuarios de su grupo (se
revisan en la web).

**200** — [`Summary`](#summary)

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

- Con `ready: false` no se puede iniciar una sesión; `warnings` trae el texto
  para mostrar, en el mismo orden que `missing`.
- Las autorizaciones se registran en la web, a partir del formato firmado en papel.
- `today_sessions` va de la más reciente a la más antigua e incluye sesiones
  propias sin participante (`participant_id` y `participant_code` en `null`).
- Una sesión con `state: "in_progress"` y `guided_phase` no terminal se puede
  [retomar](#retomar-una-sesión).

Errores: `503 unavailable`. Un parámetro inválido responde `422` de esquema.

### Sesión con participante

#### `GET /mobile/protocols?participant_id={id}`

Con token. Protocolos que la cuenta puede aplicar a ese participante: los que
armó ella misma, en su versión vigente y con todos sus estímulos activos; con
niños, además, preparados para niños, aprobados por el docente y con estímulos
aptos para su edad. Una lista vacía significa que no hay ninguno utilizable (se
arman en la web).

**200** — lista de [`Protocol`](#protocol)

```json
[
  {"id": "98128891-...", "name": "Secuencia móvil", "version": 1, "for_children": false, "step_count": 1,
   "has_pre_questionnaire": true, "has_post_questionnaire": false}
]
```

Errores: `403 forbidden` (participante ajeno), `404 not_found`, `503 unavailable`.

#### `POST /mobile/sessions`

Con token.

```json
{"participant_id": "3e7ac862-...", "protocol_id": "98128891-..."}
```

Exige, igual que en la web: compromiso de confidencialidad aceptado, que la
cuenta haya registrado al participante, autorizaciones vigentes (participación,
cámara y, con niños, asentimiento) y un protocolo utilizable. Se aplica la
versión vigente de los cuestionarios del protocolo.

**201** — [`StartedSession`](#startedsession)

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

Errores: `403 forbidden` (participante registrado por otra cuenta), `404 not_found`,
`409 conflict` (falta o se retiró una autorización, falta la edad o el protocolo
no es utilizable), `422 invalid`, `428 commitment_required`, `503 unavailable`.

Iniciar una sesión nueva **no** cierra otra que siga en curso. **No reintentar a
ciegas** si no hubo respuesta: consultar primero `GET /mobile/summary` y, si la
sesión se creó, retomarla o detenerla.

#### `POST /mobile/sessions/{id}/confirm`

Con token. Las casillas empiezan sin marcar; quien conduce las marca en el
aplicativo antes de entregar el dispositivo.

| Campo | Tipo | Por defecto | Obligatorio en `true` cuando |
| --- | --- | --- | --- |
| `commitment_reminder` | boolean | `false` | Siempre |
| `authorization_confirmed` | boolean | `false` | Participante adulto |
| `guardian_present` | boolean | `false` | Niño o niña |
| `child_assent` | boolean | `false` | Niño o niña |

```json
{"commitment_reminder": true, "authorization_confirmed": true, "guardian_present": false, "child_assent": false}
```

**200** — [`SessionStep`](#sessionstep) de la fase siguiente (el mismo cuerpo que
`GET .../next`).

Errores: `422 invalid` (falta una confirmación requerida), `409 conflict` (ya se
confirmó o el participante perdió su autorización), `403 forbidden`, `404 not_found`.

#### `GET /mobile/sessions/{id}/next`

Con token. Qué mostrar ahora. El servidor avanza las fases que dependen del
tiempo (fin de cada estímulo) en esta misma llamada.

**200** — [`SessionStep`](#sessionstep)

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

En `pre_questionnaire` o `post_questionnaire`, `questionnaire` es un
[`Questionnaire`](#questionnaire):

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

En `calibration`, `calibration` es un [`Calibration`](#calibration):

```json
"calibration": {"state": "calibrating", "progress": 0.4, "notice": null}
```

En `confirmation`, `confirmation` trae `reminder` y `required` como en
`POST /mobile/sessions`.

Errores: `403 forbidden` (sesión de otra cuenta), `404 not_found`, `503 unavailable`.
Una sesión terminada **no** da error: responde con `phase` `finished` o `stopped`.

#### `POST /mobile/sessions/{id}/questionnaires/{moment}`

Con token. `moment` es `pre` o `post`.

| Campo | Tipo | Regla |
| --- | --- | --- |
| `answers` | objeto | Clave: `id` de una pregunta de ese cuestionario (otra clave responde `422`). Valor según la tabla siguiente. Una pregunta sin responder se omite; `null`, `""` y `[]` también cuentan como sin responder |
| `entry_mode` | `participant` \| `conductor` | Por defecto `participant`. `conductor` si quien conduce anotó lo que dijo el participante |

| `kind` | Valor |
| --- | --- |
| `faces` | Entero del 1 al 5 |
| `scale` | Entero del 1 a `scale_points` |
| `single_choice` | Una cadena de `options`, idéntica |
| `multiple_choice` | Lista de cadenas de `options` (se guarda en el orden de `options`) |
| `short_text` | Texto de hasta 500 caracteres (se quitan los espacios de los extremos) |

```json
{"answers": {"animo": 3, "energia": 4, "lugar": "Casa", "apoyos": ["Música"], "nota": "Bien"},
 "entry_mode": "participant"}
```

Las respuestas se guardan cifradas, no se puntúan ni se interpretan, y **no se
devuelven**. Tras guardarlas, la sesión avanza sola a la fase siguiente.

**201** — [`PhaseResult`](#phaseresult): `{"phase": "calibration"}`.

Errores: `422 invalid` (falta una obligatoria o un valor está fuera de rango),
`409 conflict` (ya se respondió o no es la fase), `403 forbidden`, `404 not_found`,
`503 unavailable`.

#### `POST /mobile/sessions/{id}/advance`

Con token, sin cuerpo. Continúa tras un cuestionario que ya figura como
respondido (`questionnaire.answered: true`, por ejemplo porque se respondió en la
web). **200** — [`PhaseResult`](#phaseresult).

Errores: `409 conflict` (falta responder el cuestionario o no hay nada que
continuar en esta fase).

#### `POST /mobile/sessions/{id}/calibration`

Con token, sin cuerpo. Empieza la calibración neutral, o la **reinicia** si ya
estaba en curso. **200** — `{"phase": "calibration"}`. Ver
[calibración](#calibración).

Errores: `409 conflict` (la sesión no está en `calibration`).

#### `POST /mobile/sessions/{id}/frames`

Con token. Cuerpo: un cuadro **JPEG** (`Content-Type: image/jpeg`, máximo
1 000 000 bytes; la web envía 640 × 480, cara visible y centrada). El servidor lo
analiza en memoria con el modelo local, aplica el control de calidad (rostro,
centrado, tamaño, iluminación e inclinación) y lo descarta.

En fases que no son `calibration` ni `stimuli` el cuadro se acepta y se ignora.

**200** — [`FrameResult`](#frameresult)

```json
{"phase": "stimuli", "capture_status": ["too_dark"]}
```

Si `phase` cambió respecto a la última conocida, pedir `GET .../next` de inmediato.

Errores: `413 too_large`, `415 unsupported_media_type`, `422 invalid` (no es un
JPEG válido), `409 conflict` (la sesión terminó), `403 forbidden`, `404 not_found`.

#### `POST /mobile/sessions/{id}/skip`

Con token, sin cuerpo. Salta el estímulo en curso (en `before_analyzer` o
`stimuli`); queda registrado como saltado. Es una acción de quien conduce: en el
aplicativo, solo tras el PIN. **200** — [`PhaseResult`](#phaseresult).

Errores: `409 conflict` (no hay un estímulo en curso).

#### `POST /mobile/sessions/{id}/stop`

Con token. Interrumpe de inmediato: la sesión pasa a `stopped` y se cancela. Usar
en cuanto el participante o su tutor pidan parar.

```json
{"reason": "participant"}
```

`reason`: `participant`, `guardian` o `conductor` (ver
[`stop_reason`](#valores-enumerados)). **200** — `{"phase": "stopped"}`.

Si la sesión ya había terminado, no cambia nada y responde **200** con su fase
(`finished` o `stopped`): es seguro reintentar.

Errores: `403 forbidden`, `404 not_found`.

### Imágenes de estímulos

#### `GET /mobile/stimulus-images/{session_id}/{stimulus_id}?expires=...&signature=...`

Sin token: la URL la entrega `GET .../next` (`stimulus.image_url`) y no se arma
en el aplicativo. La firma nombra la sesión, el estímulo y el vencimiento
(**120 segundos**, `image_expires_at`). Solo vale mientras la sesión de quien la
recibió siga activa y el estímulo sea de su protocolo.

**200**: la imagen (`image/png`, `image/jpeg` o `image/webp`), sin metadatos.

Errores: `403 invalid_or_expired_url` (vencida, alterada o la sesión ya
terminó: pedir `GET .../next`), `404 not_found` (el estímulo ya no existe).

La imagen se guarda solo en memoria mientras se muestra. No usar la caché de
disco del cargador de imágenes. Identificar la imagen por `session_id` +
`step_index`, no por la URL (la firma cambia en cada `next`).

---

## Sesión guiada: fases y ciclo

### Fases

```text
confirmation ──confirm──▶ pre_questionnaire* ──respuestas──▶ before_analyzer* ──tiempo──▶
calibration ──cuadros (≈3 s)──▶ stimuli ──tiempo, por estímulo──▶ post_questionnaire* ──respuestas──▶ finished

* se omite si el protocolo no la tiene. Desde cualquier fase activa: stop ──▶ stopped
```

| `phase` | Qué muestra el aplicativo | Envía cuadros | Cómo avanza |
| --- | --- | --- | --- |
| `confirmation` | Recordatorio y casillas de `confirmation.required` (lo ve quien conduce) | No | `POST .../confirm` |
| `pre_questionnaire` | El cuestionario previo | No | `POST .../questionnaires/pre` (o `.../advance` si `answered`) |
| `before_analyzer` | Imagen abstracta y `abstract_notice`, **sin cámara** | No | El servidor, al cumplirse `exposure_seconds` de cada estímulo |
| `calibration` | «Mira a la pantalla con el rostro relajado» y `progress` | Mientras `send_frames` | `POST .../calibration` y cuadros; el servidor pasa solo a `stimuli` |
| `stimuli` | El estímulo (y `abstract_notice` si es abstracto) | Mientras `send_frames` | El servidor, al cumplirse `exposure_seconds` de cada estímulo |
| `post_questionnaire` | El cuestionario posterior | No | `POST .../questionnaires/post` (o `.../advance`) |
| `finished` | Agradecer al participante. Fin | No | Terminal |
| `stopped` | Se interrumpió (`stop_reason`). Fin | No | Terminal |

Las fases terminales son `finished` y `stopped`. Una sesión también puede pasar a
`stopped` desde la web; el aplicativo lo ve en el siguiente `next` o como
`409 conflict` al enviar un cuadro.

### Ciclo recomendado

- **Consultar `next`** cada segundo mientras la sesión avanza, y además de
  inmediato tras cada acción (`confirm`, cuestionario, `calibration`) o cuando un
  cuadro devuelve otra `phase`. El servidor lleva todos los tiempos:
  `remaining_seconds` solo sirve para mostrar una cuenta regresiva.
- **Enviar cuadros** cada `frame_interval_ms` mientras `send_frames` sea `true`,
  con **un solo cuadro en vuelo** a la vez. Si un envío tarda más que el
  intervalo, se espera al siguiente intervalo: no se acumulan cuadros.
- **Parar de inmediato** de enviar cuadros cuando `send_frames` pasa a `false`,
  la sesión se pausa en el aplicativo (por ejemplo, «Quiero parar») o no hay
  conexión. Sin conexión no se toman cuadros ni se guardan para después.

### Calibración

1. En `calibration`, `calibration.state` empieza en `none`: mostrar la indicación
   y llamar `POST .../calibration` cuando el participante esté listo.
2. Con `state: "calibrating"` (`send_frames: true`), enviar cuadros. `progress`
   va de `0.0` a `1.0` en unos **3 segundos**.
3. Se completa con el primer cuadro recibido después de esos 3 segundos, si hubo
   al menos **5 cuadros con rostro**. Entonces la sesión pasa sola a `stimuli`.
4. Si no hubo rostros suficientes, `state` vuelve a `none` y `notice` trae el
   texto para mostrar: repetir desde el paso 1.

`capture_status` no se informa durante la calibración. El estado de la
calibración vive en la memoria del servidor: si el servidor se reinicia, `state`
vuelve a `none` y hay que llamar de nuevo `POST .../calibration`.

### Capturas durante los estímulos

- Cada estímulo tiene un momento de captura (configurado en el protocolo, en la
  web). Los cuadros anteriores a ese momento se aceptan, pero no se analizan.
- Si el cuadro del momento de captura tiene problemas de calidad,
  `capture_status` los informa y el servidor reintenta con los cuadros siguientes
  durante **3 segundos**. Después guarda la captura marcada con su problema.
- Por eso conviene enviar cuadros durante **todo** el estímulo, no solo al inicio.
- `capture_status` orienta a quien conduce (por ejemplo, «Acércate» o «Busca más
  luz»). Nunca indica la expresión estimada.

### Retomar una sesión

Si el aplicativo se cierra o se reinicia durante una sesión, la sesión sigue en
curso en el servidor (los estímulos siguen corriendo por tiempo):

1. Tras iniciar sesión, `GET /mobile/summary` lista en `today_sessions` las
   sesiones con `state: "in_progress"`.
2. Para retomarla se sigue con `GET /mobile/sessions/{id}/next`. Recomendado:
   antes de devolver el dispositivo, quien conduce vuelve a comprobar en el
   aplicativo que el participante (y, con niños, su tutor) sigue presente; el
   servidor no lo pide de nuevo.
3. Si no se va a retomar, detenerla con `POST .../stop` y `reason: "conductor"`.
   Una sesión abandonada sigue `in_progress` hasta que se detiene en el
   aplicativo o en la web.

Solo la cuenta que inició la sesión puede retomarla (`403 forbidden` para
cualquier otra).

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
| `services.participant_sessions` | boolean | no | |

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
| `participants` | lista de [`ParticipantSummary`](#participantsummary) | no | Puede estar vacía |

### `SessionSummary`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `id` | string | no | |
| `started_at` | datetime | no | |
| `state` | string | no | [`state`](#valores-enumerados) |
| `guided_phase` | string | sí | [`phase`](#valores-enumerados); `null` si no es una sesión guiada |
| `participant_id` | string | sí | `null` en sesiones propias |
| `participant_code` | string | sí | `null` en sesiones propias |
| `protocol_name` | string | sí | `null` sin protocolo |

### `ParticipantSummary`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `id` | string | no | |
| `code` | string | no | Código aleatorio, por ejemplo `P-RGNYTB` |
| `kind` | string | no | `adult` o `child` |
| `age_years` | int | sí | `null` si se registró sin edad (no puede tener sesiones) |
| `ready` | boolean | no | `true` si se puede iniciar una sesión |
| `missing` | lista de string | no | [`missing`](#valores-enumerados); vacía si `ready` |
| `warnings` | lista de string | no | Texto de cada elemento de `missing`, en el mismo orden |
| `last_session` | [`SessionSummary`](#sessionsummary) | sí | La más reciente de esta cuenta con ese participante |

### `Protocol`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `id` | string | no | |
| `name` | string | no | |
| `version` | int | no | Versión vigente |
| `for_children` | boolean | no | |
| `step_count` | int | no | Número de estímulos |
| `has_pre_questionnaire` | boolean | no | |
| `has_post_questionnaire` | boolean | no | |

### `StartedSession`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `session_id` | string | no | |
| `phase` | string | no | Siempre `confirmation` |
| `participant.id` | string | no | |
| `participant.code` | string | no | |
| `participant.kind` | string | no | `adult` o `child` |
| `confirmation` | [`Confirmation`](#confirmation) | no | |

### `Confirmation`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `reminder` | string | no | Recordatorio del compromiso, para mostrar |
| `required` | lista de string | no | Casillas que deben ir en `true` en `POST .../confirm` |

### `SessionStep`

Respuesta de `GET .../next` y de `POST .../confirm`.

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `session_id` | string | no | |
| `phase` | string | no | [`phase`](#valores-enumerados) |
| `stop_reason` | string | sí | Solo en `stopped` |
| `send_frames` | boolean | no | `true` solo en `calibration` con `state: "calibrating"` y en `stimuli` |
| `frame_interval_ms` | int | no | Hoy 500 |
| `capture_status` | lista de string | no | [`capture_status`](#valores-enumerados); vacía si no hay problemas |
| `questionnaire` | [`Questionnaire`](#questionnaire) | sí | Solo en `pre_questionnaire` y `post_questionnaire` |
| `calibration` | [`Calibration`](#calibration) | sí | Solo en `calibration` |
| `stimulus` | [`Stimulus`](#stimulus) | sí | Solo en `before_analyzer` y `stimuli` |
| `confirmation` | [`Confirmation`](#confirmation) | sí | Solo en `confirmation` |
| `step_count` | int | no | Número de estímulos del protocolo |

### `Questionnaire`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `moment` | string | no | `pre` o `post` |
| `id` | string | no | |
| `version` | int | no | |
| `title` | string | no | |
| `instructions` | string | no | Puede ser cadena vacía |
| `answered` | boolean | no | `true`: ya se respondió; usar `POST .../advance` |
| `questions` | lista de [`Question`](#question) | no | En el orden en que se muestran |

### `Question`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `id` | string | no | Clave en `answers` |
| `kind` | string | no | [`kind`](#valores-enumerados) |
| `text` | string | no | |
| `required` | boolean | no | |
| `options` | lista de string | no | Solo con `single_choice` y `multiple_choice`; si no, vacía |
| `scale_points` | int | sí | Solo con `scale` (2 a 7) |
| `min_label` | string | sí | Extremo inicial de `scale` y `faces` |
| `max_label` | string | sí | Extremo final de `scale` y `faces` |

### `Calibration`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `state` | string | no | `none`, `calibrating` o `calibrated` |
| `progress` | number | no | 0.0 a 1.0 |
| `notice` | string | sí | Texto para repetir la calibración si no se logró |

### `Stimulus`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `step_index` | int | no | Desde 0, en el orden del protocolo |
| `title` | string | no | Para quien conduce. **No se muestra al participante** |
| `kind` | string | no | `emotional` o `abstract` |
| `exposure_seconds` | number | no | Duración total del estímulo |
| `remaining_seconds` | number | no | Lo que falta según el reloj del servidor |
| `image_url` | string | no | Ruta firmada, válida 120 segundos |
| `image_expires_at` | datetime | no | Vencimiento de `image_url` |
| `abstract_notice` | string | sí | Con `kind: "abstract"`: aviso fijo que se muestra junto a la imagen |
| `records_verbal_response` | boolean | no | `true`: quien conduce registra **en la web** lo que el participante dice ver. El aplicativo no lo envía |

### `PhaseResult`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `phase` | string | no | Fase después de la acción |

### `FrameResult`

| Campo | Tipo | Nulo | Notas |
| --- | --- | --- | --- |
| `phase` | string | no | Fase después de analizar el cuadro |
| `capture_status` | lista de string | no | Problemas de calidad del cuadro pendiente; vacía si no hay |

## Valores enumerados

«Abierta»: el servidor puede agregar valores sin subir la revisión mayor; el
aplicativo debe tolerar valores desconocidos (ver
[compatibilidad](#compatibilidad-entre-versiones)).

| Enumeración | Valores | Abierta |
| --- | --- | --- |
| `role` | `student` (Usuario), `psychologist` (Docente) | No |
| `kind` (participante) | `adult`, `child` | No |
| `missing` | `participation` (autorización de participación), `camera` (uso de la cámara), `child_assent` (asentimiento del niño), `revoked` (se retiró una autorización: no hay sesiones nuevas), `age` (registrado sin edad) | Sí |
| `state` (sesión) | `in_progress`, `completed`, `cancelled`; `created` y `recognized` solo en sesiones propias de la web | Sí |
| `phase` | `confirmation`, `pre_questionnaire`, `before_analyzer`, `calibration`, `stimuli`, `post_questionnaire`, `finished`, `stopped` | Sí |
| `stop_reason` | `participant` (el participante pidió parar), `guardian` (lo pidió su tutor), `conductor` (quien conduce terminó) | No |
| `capture_status` | `no_face`, `off_center`, `too_small`, `too_dark`, `too_bright`, `tilted`, `no_frame` | Sí |
| `calibration.state` | `none`, `calibrating`, `calibrated` | No |
| `kind` (estímulo) | `emotional`, `abstract` | Sí |
| `kind` (pregunta) | `faces`, `scale`, `single_choice`, `multiple_choice`, `short_text` | Sí |
| `entry_mode` | `participant`, `conductor` | No |
| `moment` | `pre`, `post` | No |

## Reintentos e idempotencia

| Situación | Qué hacer |
| --- | --- |
| Sin respuesta en una lectura (`status`, `summary`, `protocols`, `next`, imagen) | Reintentar con espera creciente (1, 2, 4… hasta 30 segundos) |
| Sin respuesta en `POST /mobile/sessions` | No reintentar: consultar `GET /mobile/summary` y retomar o detener la sesión que se haya creado |
| Sin respuesta en `confirm`, cuestionario, `advance` o `stop` | Reintentar: si la acción ya se aplicó, la respuesta es `409 conflict` (o `200` en `stop`); luego pedir `next` |
| Sin respuesta en un cuadro | Descartarlo. No se reenvía: se envía el siguiente cuadro nuevo |
| Sin respuesta en `skip` | No reintentar: pedir `next` y decidir de nuevo |
| Sin respuesta en `refresh` | Ver [respuesta perdida](#autenticación-y-tokens) |
| Sin conexión durante una sesión | Pausar la sesión en el aplicativo, dejar de capturar y avisar a quien conduce. Los estímulos siguen corriendo en el servidor; al volver la conexión, pedir `next` |
| `5xx` | Igual que sin respuesta |
| `429 too_many_attempts` | Esperar `Retry-After` segundos antes de otro inicio de sesión |

Tiempos de espera sugeridos: 10 segundos para JSON y 5 segundos para cuadros
(un cuadro que llega tarde ya no sirve).

## Obligaciones de privacidad del aplicativo

El servidor hace cumplir el acceso; estas obligaciones son del aplicativo, porque
el servidor no las puede comprobar:

- Ningún cuadro, imagen de estímulo ni dato de participante se guarda en disco,
  galería, caché ni registros. Los cuadros viven en memoria, se envían una vez y
  se descartan.
- Solo se guardan el token de renovación (cifrado con el Android Keystore) y lo
  propio del dispositivo (por ejemplo, el hash del PIN). Al cerrar sesión se borra
  todo.
- Ningún token, respuesta, código de participante ni cuerpo de petición aparece
  en los registros.
- No se muestran el nombre ni datos de un participante: solo código, tipo y edad.
- El participante no ve resultados, `capture_status` como juicio, ni el `title`
  del estímulo.
- Lo que el participante dice ver de una imagen abstracta lo registra quien
  conduce en la web.

## Configuración del servidor

| Variable | Por defecto | Uso |
| --- | --- | --- |
| `MOBILE_MIN_APP_VERSION` | `1.0.0` | Versión mínima del aplicativo (`x.y.z`) |
| `ENVIRONMENT` | `development` | Con `production`, `/mobile` exige HTTPS |
| `LOGIN_MAX_FAILURES_PER_ACCOUNT`, `LOGIN_MAX_FAILURES_PER_IP`, `LOGIN_ATTEMPT_WINDOW_MINUTES` | 5, 20, 15 | Bloqueo por intentos fallidos (compartido con la web) |

Detrás de nginx, la API conoce el esquema por `X-Forwarded-Proto`: nginx
reenvía `https` cuando lo recibe del proxy TLS (Caddy o el de la institución).
En Docker, la web y la API se publican en el puerto `8080` del equipo (nginx);
la API (`8000`) no se publica fuera de Docker.

## Historial

| Revisión | Fecha | Cambios |
| --- | --- | --- |
| 2 | 2026-10-24 | Solo documentación; la API no cambió. Se agregan: convenciones (nulos, fechas, campos de más), reglas de compatibilidad y enumeraciones abiertas, acción del aplicativo para cada error, renovación serializada y respuesta perdida, tabla de reintentos e idempotencia, tipos de cada objeto con nulabilidad, máquina de fases, detalles de calibración y capturas, cómo retomar una sesión, `stop` idempotente, `404` de imágenes y obligaciones de privacidad del aplicativo |
| 1 | 2026-10-23 | Primera versión del contrato con la API móvil |
