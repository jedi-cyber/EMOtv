# Privacidad y control de acceso

Cómo protege EMOtv los datos de los participantes antes de guardar cualquiera de
ellos. Todo lo que se describe aquí lo aplica el servidor (FastAPI); ocultar un
botón en la interfaz nunca es la única protección.

EMOtv **estima una expresión facial**: no diagnostica, no determina el estado
psicológico de nadie y no sustituye a un profesional.

## Papeles

| Papel (interno) | En pantalla | Para qué | Nunca accede a |
| --- | --- | --- | --- |
| `superadmin` | Superadministrador | Soporte técnico: modelos, catálogos, políticas, la cuenta de administrador y la auditoría. Restablece solo la contraseña del administrador. | Participantes, sesiones, cuestionarios, respuestas y reportes |
| `admin` | Administrador | Persona con cargo superior en la Facultad: crea y desactiva docentes y usuarios, arma los grupos, restablece sus contraseñas y consulta la auditoría. | Participantes, sesiones, cuestionarios, respuestas y reportes |
| `psychologist` | Docente | Ve los resultados de los participantes de los usuarios de su grupo y los suyos. Conduce sesiones propias. | Datos de otros grupos |
| `student` | Usuario | Conduce sesiones con sus participantes y ve solo lo suyo. | Datos de otros usuarios |

- Solo el superadministrador crea o desactiva la cuenta de administrador. Por
  defecto puede haber **una** activa (`MAX_ADMIN_ACCOUNTS`).
- Un docente tiene varios usuarios; **un usuario tiene un solo docente**
  (restricción única en `psychologist_assignments.student_id`). Solo el
  administrador mueve un usuario a otro grupo: el acceso del docente sigue la
  asignación vigente y el cambio queda en la auditoría.
- Los **participantes no tienen cuenta**: se identifican con un código aleatorio
  (`P-XXXXXX`), sin nombre, DNI ni foto. No existe ningún registro ni inicio de
  sesión de participantes.
- La cuenta de superadministrador se crea con `scripts/security/create_admin.py`
  y su contraseña se recupera con `scripts/security/reset_admin_password.py`
  (solo en el servidor).

## Control de acceso central

`AuthorizationService.can_access_participant(usuario, participante)` es la única
regla de acceso a un participante y a todo lo suyo (sesiones, capturas,
cuestionarios y reportes). Acceden:

1. la cuenta que registró al participante;
2. el docente asignado **en este momento** a esa cuenta.

El administrador y el superadministrador nunca acceden. Una sesión con
participante usa la misma regla (`can_access_session`); una sesión propia la ven
quien la conduce y su docente. Solo quien conduce una sesión puede enviar su
cámara o cancelarla.

## Imágenes

Ningún endpoint, pantalla ni exportación devuelve imágenes de participantes:
los cuadros de la cámara se procesan en memoria y se descartan. La prueba
`tests/integration/test_no_participant_images.py` revisa el esquema de la API y
recorre cada ruta GET con los cuatro papeles para comprobarlo. Las únicas
imágenes que se podrán guardar son estímulos subidos por docentes o por el
administrador, nunca fotos de participantes.

## Compromiso de confidencialidad

- Texto versionado en `src/emotv/resources/confidentiality_commitment.md`,
  marcado como **provisional** hasta que la Facultad lo revise.
- Usuarios y docentes lo aceptan en su primer ingreso y cada vez que cambia la
  versión. Sin aceptarlo, el servidor rechaza registrar participantes e iniciar
  sesiones (`428`).
- Antes de registrar al primer participante niño aparece un aviso reforzado
  (`src/emotv/resources/child_data_notice.md`): los datos de menores son más
  sensibles.
- Cada aceptación queda en la auditoría con su versión.

## Cifrado de campos sensibles

- Se cifran en reposo con Fernet: notas libres, marcadores con texto, respuestas
  de cuestionarios, respuestas a imágenes abstractas, comentarios del docente y
  texto de reportes. Hoy existe el primero (notas del participante); los demás
  usan la misma utilidad (`emotv.shared.security.field_encryption`) cuando se
  agreguen.
- La clave es `SENSITIVE_DATA_KEY` (vacía en los archivos de ejemplo; nunca en
  el repositorio). Generar una:
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- **Rotación:** `SENSITIVE_DATA_KEY=nueva,anterior`. La primera clave cifra y
  todas descifran; cuando todos los datos estén cifrados con la nueva, se retira
  la anterior.
- Sin clave válida, el módulo de sesiones con participantes **no se activa**
  (`503`) y la API registra el motivo en el log.

## Auditoría

Tabla `access_audit`: fecha, cuenta que actúa y su papel, acción, tipo e id del
recurso, y resultado (`success`, `denied`, `failure`). **Nunca** guarda notas,
respuestas, correos ni imágenes.

- Se registran consultas, creaciones, impresiones, aprobaciones, eliminaciones,
  solicitudes de eliminación, cambios de autorización, restablecimientos de
  contraseña, cambios de grupo, creación y desactivación de cuentas, y
  aceptaciones del compromiso. Los accesos denegados a un participante también.
- La API solo la consulta (`GET /audit`, con filtros), para el administrador y
  el superadministrador. No existe ninguna operación para editarla o borrarla.
- Se conserva `AUDIT_RETENTION_MONTHS` meses (24 por defecto).

## Retención y eliminación

- **Retención:** una tarea que corre al arrancar la API y luego una vez al día
  elimina los participantes con más de `PARTICIPANT_RETENTION_MONTHS` meses (12
  por defecto) con todos sus registros. La auditoría anota solo la cantidad.
  Treinta días antes, el docente ve la lista de participantes por vencer para
  decidir si imprime el reporte aprobado.
- **Eliminación a pedido:** el usuario la solicita y el docente la ejecuta; el
  docente también puede iniciarla. Es una sola transacción: borra al
  participante y sus registros, verifica que no quede ninguno y, si la
  verificación falla, revierte todo. Genera un **acta imprimible** con el código
  del participante, la fecha, la cantidad de registros por tipo y el resultado de
  la verificación, sin datos personales. Imprimirla queda en la auditoría.
- Cada tabla nueva con datos de participantes se agrega a
  `PARTICIPANT_LINKED_RECORDS`, así la retención y la eliminación la incluyen.

## Registros y respuestas HTTP

- Los logs no incluyen cuerpos de peticiones, notas, respuestas ni imágenes.
- Todas las respuestas de la API llevan `Cache-Control: no-store`,
  `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` y
  `X-Frame-Options: DENY`; `Strict-Transport-Security` cuando se sirven por
  HTTPS.

## Respaldos

`scripts/docker/backup_db.py` cifra el respaldo completo con `BACKUP_KEY`, una
clave Fernet **distinta** de `SENSITIVE_DATA_KEY` (el script se niega si son
iguales o si falta). El volcado en claro nunca se escribe en disco y
`restore_db.py` solo acepta respaldos `.dump.enc`. `BACKUP_KEY` vive en
`.env.docker` y no se pasa a la API.

Un respaldo conserva datos que la aplicación ya eliminó: **elimina los
respaldos con más antigüedad que `PARTICIPANT_RETENTION_MONTHS`**, y los de
cuentas de voluntarios a los 30 días.

## Configuración

| Variable | Por defecto | Uso |
| --- | --- | --- |
| `SENSITIVE_DATA_KEY` | vacía | Claves Fernet de los campos sensibles (separadas por comas) |
| `BACKUP_KEY` | vacía | Clave Fernet de los respaldos (solo en el anfitrión) |
| `MAX_ADMIN_ACCOUNTS` | 1 | Cuentas de administrador activas a la vez |
| `PARTICIPANT_RETENTION_MONTHS` | 12 | Retención de participantes y sus registros |
| `AUDIT_RETENTION_MONTHS` | 24 | Retención de la auditoría |
