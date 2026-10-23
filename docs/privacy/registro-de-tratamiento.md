# Registro de tratamiento de datos personales

> Derivado del código (`src/emotv/infrastructure/persistence/models.py`), de las
> migraciones (`migrations/versions/`, hasta `20261025_22`) y de los servicios que
> aplican la retención. Si el código cambia, este registro debe actualizarse: la
> fuente de verdad son el código y las migraciones.
> Sujeto a revisión de la Facultad. Las bases de legitimación marcadas deben
> **verificarse con asesoría legal** según la Ley N.° 29733 y el D.S. 016-2024-JUS.

Responsable del tratamiento: `[1: RESPONSABLE DEL TRATAMIENTO]` ·
Ubicación del servidor y de los respaldos: `[12: UBICACIÓN DEL SERVIDOR Y DE LOS RESPALDOS]` ·
Inscripción del banco de datos: `[13: INSCRIPCIÓN DEL BANCO DE DATOS, SI CORRESPONDE]`.

## Convenciones

- **Quién accede**: «quien registró + docente» significa la regla central
  `can_access_participant`: la cuenta que registró al participante y el docente
  asignado en ese momento a esa cuenta. El administrador y el superadministrador
  nunca acceden (ver [matriz-de-accesos.md](matriz-de-accesos.md)).
- **Cifrado**: «Sí» indica que el campo se cifra en la aplicación con Fernet y
  `SENSITIVE_DATA_KEY` antes de guardarse. El resto se guarda sin cifrar dentro
  de PostgreSQL; el sistema no configura cifrado del disco ni del volumen
  `emotv_pgdata` (depende del servidor donde se instale). Los respaldos se
  cifran completos con `BACKUP_KEY`.
- **Meses**: el código cuenta un mes como 30 días (`DAYS_PER_MONTH = 30`).
- **Participantes vinculados**: las tablas de la lista
  `PARTICIPANT_LINKED_RECORDS` se eliminan junto con el participante, por
  retención o a pedido, en una transacción con verificación y acta.

## A. Participantes

Base de legitimación: **consentimiento** del participante adulto, o de su padre,
madre o tutor si es niño, más el asentimiento del niño; firmado en papel con dos
autorizaciones separadas (participación y cámara). `[Verificar con asesoría
legal: requisitos del consentimiento de menores y si la expresión facial
estimada se considera dato sensible.]`

Finalidad común: actividad formativa de Psicología — conducir la sesión,
describir lo registrado y la revisión docente. No hay decisiones automatizadas
sobre la persona: el sistema no calcula puntajes ni interpreta respuestas.

Retención común: **`PARTICIPANT_RETENTION_MONTHS` (12 por defecto, 360 días)
contados desde `participants.created_at`**, no desde la última sesión. La tarea
de retención corre al arrancar la API y luego una vez al día; también se
eliminan a pedido (cancelación) con acta.

| Tabla | Campos con datos personales | Finalidad específica | Quién accede | Cifrado | Retención |
| --- | --- | --- | --- | --- | --- |
| `participants` | `code` (aleatorio `P-XXXXXX`), `kind` (adulto o niño), `age_years`, `notes_encrypted`, `registered_by_user_id`, fechas de solicitud de eliminación y de retiro de autorización | Identificar al participante sin nombre, DNI ni foto | Quien registró + docente | `notes_encrypted`: Sí. Resto: No | Común |
| `participant_authorizations` | `form_version`, `signed_on`, `grantor` (participante o tutor), `participation`, `camera`, `child_assent`, retiro (`revoked_party`, `revoked_scope`) | Comprobar que hay autorización antes de cada sesión y registrar su retiro. No guarda datos de quien firma | Quien registró + docente | No | Común |
| `sessions` (con `participant_id`) | Expresión inicial y confianza (sesiones de actividad), modelo usado, protocolo y cuestionarios aplicados, fechas | Registro de la sesión | Quien registró + docente | No | Común |
| `guided_runs` | Fase, pasos, fechas, `stop_reason` (quién pidió parar), `view_token_hash` (SHA-256 del enlace de la vista del participante) | Estado de la sesión guiada | Quien condujo + docente | No (el enlace se guarda solo como hash) | Común |
| `expression_captures` | `emotion` y `calibrated_emotion` estimadas, `confidence`, `distribution`, `quality` y `quality_issues`, estímulo y segundos desde su aparición | Línea de tiempo y métricas descriptivas. **Nunca la imagen** | Quien registró + docente | No | Común |
| `questionnaire_responses` | `answers_encrypted`, `moment` (previo o posterior), `entry_mode` (lo respondió el participante o lo anotó quien conduce) | Mostrar las respuestas tal como se dieron | Quien registró + docente | `answers_encrypted`: Sí | Común |
| `session_markers` | `kind` (se distrajo, se rió, lloró, pidió parar, nota) y `note_encrypted` | Observaciones de quien conduce | Quien registró + docente | `note_encrypted`: Sí | Común |
| `verbal_responses` | `text_encrypted`: lo que el participante dice ver en una imagen abstracta | Registrar la respuesta sin interpretarla | Quien registró + docente | Sí | Común |
| `session_reports` | `narrative_encrypted`, estado, autor, aprobación | Reporte de la sesión y su revisión | Quien condujo + docente asignado | `narrative_encrypted`: Sí | Común |
| `report_comments` | `text_encrypted`, sección | Comentarios del docente | Quien condujo + docente asignado | Sí | Común |
| `report_events` | Acción (creado, enviado, aprobado, impreso…), cuenta y fecha. Sin contenido | Historial del reporte | Quien condujo + docente asignado | No | Común |
| `participant_deletion_records` (acta) | `participant_code`, fecha, cuenta que ejecutó y que solicitó, cantidades por tipo de registro, verificación | Evidencia de la eliminación, sin datos personales del participante | La cuenta que la ejecutó y la que la solicitó | No | **Sin retención automática**: se conserva indefinidamente |

El código del participante no identifica a la persona por sí solo: la relación
código–persona está en una ficha de papel que custodia el docente en
`[10: LUGAR DE CUSTODIA DE LAS FICHAS Y FORMATOS EN PAPEL]`. Mientras esa ficha
exista, el código sigue siendo un dato personal. `[Verificar con asesoría legal.]`

## B. Cuentas de usuarios y docentes

Base de legitimación: `[Verificar con asesoría legal: relación con la institución
o consentimiento.]` El análisis de la propia expresión exige aceptar la política
de consentimiento vigente (tabla `consents`; `CONSENT_MODE=production` exige una
política aprobada).

| Tabla | Campos con datos personales | Finalidad | Quién accede | Cifrado | Retención |
| --- | --- | --- | --- | --- | --- |
| `users` | `email`, `password_hash` (hash Argon2, nunca la contraseña), `role`, `is_active`, `is_test_account`, fechas | Autenticación y permisos | La propia cuenta; el administrador (docentes y usuarios) y el superadministrador (la cuenta de administrador) ven correo, papel y estado | No (la contraseña solo como hash) | **Sin retención automática**: las cuentas se desactivan, no se borran. Las de voluntarios (`PRUEBA-NN`) se borran con `scripts/testdata/delete_test_data.py` |
| `students` | `student_code`, `user_id` | Perfil de usuario para grupos y consentimiento | La propia cuenta, su docente y el administrador | No | Igual que `users` |
| `psychologist_assignments` | Docente, usuario, fecha y quién asignó | Grupo docente–usuarios | Administrador; el docente ve su grupo | No | Mientras exista la asignación |
| `consents` | Versión de la política aceptada, fechas de aceptación y revocación | Requisito para analizar la propia expresión | La propia cuenta | No | Sin retención automática |
| `commitment_acceptances` | Cuenta, tipo (compromiso o aviso de menores), versión y fecha | Evidencia de la aceptación del compromiso de confidencialidad | Uso interno del servidor; queda también en la auditoría | No | Sin retención automática |
| `sessions` (sin `participant_id`) | Expresión estimada propia y confianza, actividad, resultado y duración | Análisis de la propia expresión y actividad guiada | La propia cuenta y su docente | No | **Sin retención automática** |
| `login_attempts` | `email_hash` (SHA-256 del correo), `ip`, fecha, éxito | Limitar intentos de inicio de sesión | Nadie desde la API | No (el correo, solo como hash) | 24 horas: se purga en cada nuevo intento |
| `chat_conversations`, `chat_messages` | Cuenta, preguntas a Emi y respuestas (`content`), categoría | Historial del asistente Emi | Solo la propia cuenta | **No** | `CHAT_RETENTION_DAYS` (90). Se purga al arrancar la API y en cada pregunta. La persona puede borrar su conversación |
| `access_audit` | `actor_user_id`, `actor_role`, acción, tipo e id del recurso (puede ser el id de un participante), resultado | Rendición de cuentas de accesos. **Sin contenido** | Administrador y superadministrador (`GET /audit`) | No | `AUDIT_RETENTION_MONTHS` (24, 720 días); tarea diaria |

## C. Tablas sin datos personales de participantes

`activities`, `consent_policies`, `expression_info`, `emotion_activity_recommendations`,
`stimuli`, `protocols`, `protocol_steps`, `questionnaires` (preguntas, no
respuestas), `local_model_settings` y `chat_rejection_counts` (solo un contador
por categoría). Algunas guardan el id de la cuenta que creó, aprobó o revisó el
contenido. `stimuli` guarda imágenes subidas por docentes o el administrador,
reescritas sin metadatos; quien sube declara que no son fotos de participantes.

## D. Fuera de la base de datos

| Dónde | Qué contiene | Retención y control |
| --- | --- | --- |
| Cuadros de la cámara | Imagen de la cara | Se procesan en memoria y se descartan; nunca se escriben en disco. La base neutral de calibración vive solo en memoria |
| Logs de los contenedores (`api` y `web`) | IP de quien se conecta, método, ruta y código de respuesta (uvicorn y nginx registran el acceso). La ruta de la vista del participante incluye su enlace (`/participant-view/{token}`), válido solo mientras dura la sesión. Nunca cuerpos, notas, respuestas ni imágenes | **Docker Compose no configura rotación ni plazo de los logs**: ver el [checklist](checklist-despliegue-seguro.md) |
| Respaldos (`backups/*.dump.enc`) | Copia completa de la base | Cifrados con `BACKUP_KEY`. Se eliminan a mano: los de más de `PARTICIPANT_RETENTION_MONTHS` y, si contienen voluntarios, a los 30 días |
| Formatos firmados y fichas código–persona | Nombres y firmas | En papel, en `[10: LUGAR DE CUSTODIA DE LAS FICHAS Y FORMATOS EN PAPEL]`. El sistema no los conoce. `[Verificar con asesoría legal: plazo de conservación.]` |
| Servicios externos de Emi (n8n Cloud y Groq) | Pregunta de un usuario o docente, historial de su conversación y el conocimiento general de EMOtv. Nunca datos de participantes ni mensajes con DNI, correo o teléfono | n8n no guarda las ejecuciones exitosas de producción y sí las fallidas, con la pregunta ([chatbot/n8n-setup.md](../chatbot/n8n-setup.md)). `[Verificar con asesoría legal: flujo transfronterizo.]` |
