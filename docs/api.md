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

El aplicativo Android usa sus propias rutas `/mobile` (tokens de acceso cortos y
de renovación revocables, solo usuarios y docentes): contrato completo en
[mobile-api.md](mobile-api.md). Un token del aplicativo no sirve en estas rutas
y uno de la web no sirve en `/mobile`.

## Papeles, compromiso y auditoría

Papeles: `superadmin` (Superadministrador), `admin` (Administrador),
`psychologist` (Docente) y `student` (Usuario). El administrador y el
superadministrador nunca acceden a sesiones ni resultados. Ver
[privacidad](privacy/README.md).

| Método | Ruta | Acceso |
| --- | --- | --- |
| `GET`, `POST` | `/users` | Superadministrador: cuenta de administrador (máximo `MAX_ADMIN_ACCOUNTS`). Administrador: docentes y usuarios |
| `PATCH`, `DELETE` | `/users/{id}` | Igual que arriba; el papel no se cambia |
| `POST` | `/users/{id}/reset-password` | Igual que arriba; contraseña temporal visible una vez, aviso en el siguiente ingreso y auditoría |
| `PUT`, `DELETE` | `/users/{docente}/assigned-students/{student_id}` | Administrador; asignar a otro docente mueve al usuario |
| `GET` | `/commitment`, `/commitment/child-notice` | Texto versionado y si la cuenta debe aceptarlo |
| `POST` | `/commitment/accept`, `/commitment/child-notice/accept` | Usuarios y docentes, con la versión vigente |
| `GET` | `/audit` | Administrador y superadministrador, con filtros; no hay operaciones de escritura |

Las personas evaluadas no se registran: no hay participantes ni cuentas para
ellas. Cada sesión lleva un código aleatorio (`S-4F7K2Q`) que se anota en el
formato firmado en papel.

## Estímulos y protocolos

| Método | Ruta | Acceso |
| --- | --- | --- |
| `GET` | `/stimuli` | Usuarios (institucionales, los de su docente y sus imágenes propias aprobadas; nunca las pendientes), docentes (los suyos e institucionales) y administrador (institucionales). `?for_children=true`: solo los que admite un protocolo para niños (leves, aprobados y vigentes; la edad no se registra, así que no se filtra por edad mínima) |
| `POST` | `/stimuli` | Docente (alcance de grupo) o administrador (institución), con `multipart/form-data`: imagen PNG, JPEG o WebP de hasta 5 MB, título, tipo, categoría, expresión esperada (solo emocionales), intensidad, edad mínima, origen, licencia y las declaraciones `not_a_participant_photo` (no es una foto de una persona evaluada) y, en abstractas, `not_a_projective_test`. Queda aprobado al subirlo (no pasa por revisión). Los usuarios reciben `403`: suben sus imágenes en `/own-stimuli` |
| `GET` | `/stimuli/{id}`, `/stimuli/{id}/file` | Quien puede verlo; `/file` es la única ruta que sirve una imagen, siempre un estímulo reescrito sin metadatos |
| `POST` | `/stimuli/{id}/approve` | Quien lo gestiona |
| `PUT` | `/stimuli/{id}/active` | Quien lo gestiona: retirar o volver a ofrecer |
| `GET`, `POST` | `/protocols` | Usuarios y docentes; el docente ve también los de su grupo. `for_children` es obligatorio («¿Para adultos o para niños?») |
| `GET`, `PUT` | `/protocols/{id}` | `PUT` solo quien lo armó. Si la versión se usó en una sesión, responde con una versión nueva (otro `id`, mismo `family_id`) |

Un protocolo es una receta guardada: qué aplicar en una sesión. Se guarda sin
ejecutarlo y no necesita la aprobación del docente. Uno para niños solo admite
estímulos «Para niños» (`audience: "children"`, leves) y aprobados; uno para
adultos admite los dos. Una imagen propia pendiente no se admite en ninguno
(`422` al guardarlo y `409` al usarlo si alguno dejó de servir). `needs_image`
indica que el docente eliminó o reclasificó una imagen del protocolo: hay que
reemplazarla.

### Imágenes propias

En la API son estímulos de alcance `user` (`/own-stimuli`): ninguna ruta de
consulta se llama como una imagen.

| Método | Ruta | Acceso |
| --- | --- | --- |
| `POST` | `/own-stimuli` | Usuario con docente asignado. `multipart/form-data` con listas paralelas `files`, `titles`, `origins` («¿De dónde es esta imagen?»), `audiences` (`children` o `adults`) y `rights_confirmed` (debe ser `true`). Hasta 20 por lote y `IMAGE_UPLOAD_LIMIT_PER_USER` en total. Cada imagen se reescribe sin metadatos y pasa por la detección de personas en memoria: `results[i].accepted=false` con el mensaje de rechazo si la confianza llega a `IMAGE_PERSON_REJECT_CONFIDENCE` (no se guarda); si no, queda `pending`, con `possible_person` desde `IMAGE_PERSON_REVIEW_CONFIDENCE`. `503` si los modelos de detección no están instalados. Docentes y administración reciben `403` |
| `GET` | `/own-stimuli` | El usuario: sus imágenes, con `status` (`pending` o `approved`) y, si está pendiente, `expires_at` |
| `GET` | `/own-stimuli/{id}/file` | Quien la subió y su docente. `?preview=true`: vista ampliada del docente (se audita) |
| `GET` | `/own-stimuli/review` | Docente: pendientes de su grupo agrupadas por lote (`uploaded_by` con el correo, `uploaded_at`) y las aprobadas |
| `GET` | `/own-stimuli/review/count` | Docente: `{pending}` para el contador del menú |
| `POST` | `/own-stimuli/review` | Docente del usuario: `{image_ids, decision: "children" \| "adults" \| "delete", reason?}`. Aprueba o reclasifica, o elimina (archivo y registro; si una sesión o un protocolo la nombran, queda solo un registro sin imagen). El motivo llega al usuario como aviso |
| `GET` | `/notices` | La propia cuenta: avisos sin leer (imagen eliminada o por vencer, protocolo que necesita una imagen) |
| `POST` | `/notices/{id}/read` | La propia cuenta: marca un aviso como leído (`204`) |

La detección de personas no es infalible: el docente revisa todas las imágenes.
Las pendientes se eliminan a los `IMAGE_REVIEW_DAYS` días (aviso siete días
antes). Un protocolo puede indicar `pre_questionnaire_id` y `post_questionnaire_id`
(cuestionarios propios o la plantilla que el docente comparte); al iniciar la
sesión se aplica la versión vigente de cada uno.

## Cuestionarios

Los crea quien conduce la sesión. EMOtv solo los presenta y registra las
respuestas tal como se dieron: no los valida, no calcula puntajes ni interpreta
respuestas. Ninguna respuesta de la API incluye sumas ni resultados.

| Método | Ruta | Acceso |
| --- | --- | --- |
| `GET`, `POST` | `/questionnaires` | Usuarios y docentes: los propios y las plantillas que su docente comparte. Preguntas: `scale` (2 a 7 puntos, etiquetas de los extremos obligatorias), `single_choice`, `multiple_choice` (2 a 10 opciones), `short_text` (hasta 500 caracteres) y `faces` (cinco caritas, extremos opcionales); cada una puede ser `required` |
| `POST` | `/questionnaires/starter` | Copia a la cuenta la plantilla inicial editable (dos preguntas de caritas) |
| `GET`, `PUT` | `/questionnaires/{id}` | `PUT` solo su autor. Si la versión se usó en una sesión, responde con una versión nueva (otro `id`, mismo `family_id`) |
| `POST` | `/questionnaires/{id}/copy` | Copia propia y editable (de un cuestionario propio o de una plantilla del docente) |
| `PUT` | `/questionnaires/{id}/share` | Docente: comparte un cuestionario suyo con su grupo como plantilla |
| `GET`, `POST` | `/sessions/{id}/questionnaires/{pre\|post}` | Solo quien conduce la sesión: el cuestionario que espera y el registro de las respuestas (`answers`, `entry_mode`: `participant` o `conductor`). `422` si falta una obligatoria; `409` si ya se respondió |
| `GET` | `/sessions/{id}/questionnaire-responses` | Quien condujo la sesión y su docente (`can_access_session`); nunca los administradores. Cada consulta queda en la auditoría |

Las respuestas se guardan cifradas con `SENSITIVE_DATA_KEY`; sin esa clave los
cuestionarios se pueden armar, pero una sesión no puede aplicar ninguno (`503`).

## Sesiones

| Método | Ruta | Acceso |
| --- | --- | --- |
| `POST` | `/sessions` | Usuario (sus sesiones) o docente (sesiones propias); exige el compromiso aceptado (`428`) |
| `POST` | `/sessions/{id}/cancel` | Solo quien conduce la sesión |
| `GET` | `/sessions/{id}` | `can_access_session`: quien la condujo y el docente de ese usuario |
| `GET` | `/sessions` | Propias (usuario) o las propias y las de su grupo (docente) |
| `GET` | `/sessions?student_id={id}` | Sesiones de un usuario del grupo del docente |
| `POST` | `/sessions/{id}/deletion-request` | Solo quien condujo la sesión |
| `POST` | `/sessions/{id}/delete` | Docente: sus sesiones y las de su grupo, terminadas (`409` en curso). Borra todos los registros, verifica que no quede ninguno y devuelve el acta |
| `GET` | `/session-deletions`, `/session-deletions/{id}` | Actas que la cuenta pidió o ejecutó |
| `POST` | `/session-deletions/{id}/print` | Registra la impresión del acta en la auditoría |

Para un usuario, el servidor fuerza el alcance al perfil propio y rechaza un
`student_id` ajeno con `403`. El registro manual del resultado
(`/sessions/{id}/complete`) ya no existe. Una sesión inexistente devuelve `404`. Iniciar una
sesión asociada exige consentimiento activo. El administrador y el
superadministrador nunca acceden a sesiones.

Toda sesión se inicia en el Analizador. `POST /sessions` acepta `protocol_id`
(opcional), `session_type` (`propia`, `adulto` o `infantil`),
`authorization_confirmed` y `child_notice_version`; otros campos responden
`422`.

- Con protocolo, el público lo decide el protocolo (`for_children`); no hace
  falta `session_type`, y uno que lo contradiga responde `422` (con un
  protocolo para adultos se admite `propia`). Se aplica la versión vigente de
  sus cuestionarios.
- Sin protocolo, `session_type` es obligatorio (`422`): la respuesta a «¿Con
  quién es la sesión?». Una sesión infantil sin protocolo no muestra imágenes ni
  cuestionarios.
- `authorization_confirmed` debe ser `true` (`422`): la única confirmación de la
  sesión, según su público. Se guarda la fecha y hora de la confirmación.
- La primera sesión infantil exige el aviso sobre datos de menores: se acepta en
  la misma petición con `child_notice_version`; si falta, `428` con la cabecera
  `X-EMOtv-Required: child_notice`.

Cada sesión guarda un `code` aleatorio (`S-` y seis caracteres), que la web
muestra al empezar, al terminar y en el reporte. Las sesiones se eliminan solas
al cumplir `SESSION_RETENTION_MONTHS` (12 por defecto) desde su inicio; la
auditoría registra solo la cantidad.

## Sesión con protocolo

Orden: cuestionario previo, imágenes abstractas marcadas "antes del analizador"
(sin capturas), calibración neutral, estímulos del protocolo con capturas y, si
el protocolo lo indica, cuestionario posterior. Sin protocolo, después de la
calibración la fase es `live`: una lectura cada 3 segundos hasta que quien
conduce termina. La confirmación ya se dio al crear la sesión: aquí no se pide
otra. El servidor lleva el tiempo de cada exposición, así quien conduce y la
persona evaluada pueden usar dispositivos distintos. Las rutas internas
conservan el nombre `participant-view` (pantalla de la persona).

| Método | Ruta | Acceso |
| --- | --- | --- |
| `POST` | `/guided-sessions/{session_id}` | Quien conduce una sesión en progreso; devuelve una sola vez `view_token`, el enlace de la pantalla de la persona |
| `POST` | `/guided-sessions/{id}/view-link` | Reemplaza el enlace (el anterior deja de valer) |
| `GET` | `/guided-sessions/{id}` | Quien conduce: código, público, fase, paso, tiempo restante, estado de la captura, capturas, marcadores y lo que la persona dijo ver |
| `POST` | `/guided-sessions/{id}/advance` | Continúa tras el cuestionario previo o posterior (`409` si falta responderlo) |
| `POST` | `/guided-sessions/{id}/calibration` | Inicia la calibración neutral (solo después del cuestionario previo) |
| `POST` | `/guided-sessions/{id}/skip` | Salta el estímulo en curso |
| `POST` | `/guided-sessions/{id}/stop` | `reason`: `participant` (la persona), `guardian` o `conductor`; termina de inmediato y cancela la sesión |
| `POST` | `/guided-sessions/{id}/markers` | `kind`: `distracted`, `laughed`, `asked_to_stop` (termina la sesión), `cried` o `note` (con `note`, cifrada) |
| `POST` | `/guided-sessions/{id}/verbal-responses` | `step_index` y `text`: lo que la persona dice ver en una abstracta que lo pide, cifrado |
| `GET` | `/sessions/{id}/guided-results` | Quien condujo y su docente (`can_access_session`); se audita |
| `GET` | `/participant-view/{token}` | Pantalla de la persona, sin cuenta: fase, indicación y estímulo actual. Nunca expresiones, probabilidades, calidad ni notas |
| `GET` | `/participant-view/{token}/stimulus` | La imagen del estímulo que se muestra ahora (nunca la de una persona) |
| `POST` | `/participant-view/{token}/frames` | Un cuadro JPEG (hasta 1 MB); se analiza en memoria y se descarta. Responde solo `{"received": true}` |
| `POST` | `/participant-view/{token}/stop` | La persona pide parar: la sesión termina de inmediato |

Antes de cada captura se revisa rostro, centrado, tamaño, iluminación e
inclinación de la cabeza; si falla, se reintenta 3 segundos y luego se guarda
marcada con su problema (`quality: flagged`, `quality_issues`). Un estímulo
emocional se captura una vez; una imagen abstracta, cada 3 segundos durante la
exposición. Cada captura (`expression_captures`) guarda el modelo local, la
expresión estimada, la confianza, la distribución, la calidad, el estímulo y el
tiempo desde su aparición; nunca la imagen. Las pantallas con imágenes
abstractas muestran: "Registro descriptivo. Una sesión breve no permite sacar
conclusiones a partir de una imagen."

## Línea de tiempo y métricas

Describen lo registrado; no interpretan. El acceso pasa por
`can_access_session` (quien condujo la sesión y su docente). Cada consulta,
también las denegadas, queda en la auditoría (`session_timeline`,
`session_metrics`). No hay tendencias ni seguimiento por persona.

| Método | Ruta | Contenido |
| --- | --- | --- |
| `GET` | `/sessions/{id}/timeline` | Un solo eje en segundos desde el inicio: respuestas de cuestionarios, aparición de cada estímulo, expresión estimada de cada captura, lo que la persona dijo ver, marcadores y el carril `heart_rate`, vacío y reservado para el sensor |
| `GET` | `/sessions/{id}/metrics` | Por estímulo emocional: expresión estimada, probabilidad, segundos desde la aparición, calidad y si coincide con la esperada. Las capturas marcadas se muestran pero no cuentan; la primera de buena calidad decide. Las abstractas solo traen sus expresiones y lo que dijo ver, sin coincidencia, y `abstract_notice` |

Los textos describen: "En 3 de 5 estímulos la expresión estimada coincidió con
la esperada". Nunca valoran a la persona.

## Estadísticas agregadas

`GET /statistics` cuenta sesiones, no personas. Se calcula en el servidor solo
con las sesiones a las que la cuenta tiene acceso (`can_access_session`); cada
consulta, también las denegadas, se audita sin contenido (`session_statistics`).
No se generan archivos: la interfaz copia la tabla al portapapeles.

| Parámetro | Valores |
| --- | --- |
| `scope` | `mine` (sesiones que condujo la cuenta) o `group` (solo docentes: las de los usuarios de su grupo). La administración recibe `403` |
| `date_from`, `date_to` | Fechas `AAAA-MM-DD` de inicio de la sesión (UTC), inclusive |
| `protocol` | Familia del protocolo (todas sus versiones) o `none` (sin protocolo) |
| `audience` | `propia`, `adulto` o `infantil` |
| `questionnaire_id` | Versión exacta de un cuestionario de la lista `questionnaires` |

Responde:
- `sessions`: total, completadas, interrumpidas (canceladas o detenidas) y
  duración promedio de las completadas.
- `expressions`: por cada una de las 8 expresiones, el porcentaje de las
  capturas de buena calidad, con la cantidad de capturas y de sesiones. Las de
  mala calidad no cuentan (`excluded_captures`).
- `coincidence`: estímulos emocionales comparados y en cuántos coincidió la
  expresión estimada con la esperada (la primera captura de buena calidad de
  cada uno decide).
- `by_user` (solo `group`): sesiones, completadas e interrumpidas por correo
  del usuario; nada más de cada sesión.
- `questionnaire`: por pregunta, cuántas veces se eligió cada opción o punto, y
  cuántas quedaron sin responder. No se suman ni se interpretan. En las de
  texto, `counts` es nulo: solo se informa cuántas respuestas hubo.
- `notice` (fijo) y, con menos de 5 sesiones, `few_sessions_notice`.

## Reporte de sesión

Lo redacta quien condujo una sesión con protocolo, cuando terminó, y lo revisa
su docente asignado. Estados: `draft` (borrador), `submitted` (enviado a
revisión), `changes_requested` (con observaciones) y `approved`. Si quien condujo
es un docente, cerrar el reporte lo deja aprobado sin revisión. Un reporte
aprobado no se edita: `new-version` crea la siguiente, en borrador, que vuelve a
revisión. El texto y los comentarios se guardan cifrados; el historial solo dice
quién hizo qué y cuándo. Todo acceso pasa por `can_access_session` y queda
en la auditoría.

| Método | Ruta | Acceso |
| --- | --- | --- |
| `POST`, `GET` | `/sessions/{id}/report` | Crea (solo quien condujo, con la sesión terminada) o devuelve la versión vigente |
| `GET`, `PUT` | `/reports/{id}` | `PUT` (`narrative`) solo quien la redactó, en borrador o con observaciones; aprobado, `409` |
| `POST` | `/reports/{id}/submit` | Envía a revisión, o cierra y aprueba si quien redacta es docente |
| `POST` | `/reports/{id}/comments` | Docente asignado: `section` (`timeline`, `metrics`, `questionnaires`, `narrative`, `general`) y `text` |
| `POST` | `/reports/{id}/approve`, `/reports/{id}/return` | Docente asignado, con el reporte enviado a revisión |
| `POST` | `/reports/{id}/new-version` | Quien lo redactó, sobre la versión aprobada vigente |
| `POST` | `/reports/{id}/print` | Solo aprobado: registra la impresión en la auditoría y devuelve el contenido imprimible. El navegador imprime; el servidor no genera archivos |

El reporte incluye la línea de tiempo, las métricas, las respuestas de los
cuestionarios, el código de la sesión (nunca un nombre), el modelo usado, el
aviso de que las expresiones son estimaciones de apoyo y no una evaluación y, si
hubo imágenes abstractas, su aviso fijo.

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
