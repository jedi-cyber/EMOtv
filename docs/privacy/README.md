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
  (`P-XXXXXX`) que no se puede editar y con su edad en años (adulto: 18 o más),
  sin nombre, DNI, foto ni datos del tutor. La API rechaza cualquier otro dato.
  La relación entre el código y la persona se anota en una ficha de papel que
  custodia el docente; el sistema no puede recuperarla. No existe ningún
  registro ni inicio de sesión de participantes.
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

## Autorizaciones firmadas

Se registran a partir del formato firmado en papel: versión del formato, fecha
de la firma y dos casillas independientes, que empiezan sin marcar:

- (a) participación y registro de la expresión estimada;
- (b) uso de la cámara.

Las otorga el propio participante si es adulto y su padre, madre o tutor si es
niño; con niños se registra además el **asentimiento** del niño o la niña,
explicado de acuerdo con su edad. No se guarda ningún dato de quien firma.

Una sesión con participante se inicia solo si la última autorización registrada
tiene (a), (b) y, en niños, el asentimiento. La inicia únicamente quien registró
al participante.

**Retiro.** Se registra quién retiró (el participante o el tutor) y qué retiró
(participación, cámara o asentimiento). Desde ese momento no se inician sesiones
nuevas ni se registran autorizaciones nuevas, y el participante queda marcado
para que el docente decida su eliminación con el procedimiento de eliminación y
acta. Si la persona quiere volver a participar, se registra con un código nuevo.
Cada registro y cada retiro quedan en la auditoría.

## Banco de estímulos y protocolos

- Los estímulos los crean los docentes (para los usuarios de su grupo) y el
  administrador (para toda la institución); los usuarios los usan en sus
  protocolos, pero no los crean. Cada uno tiene tipo (emocional o abstracta),
  categoría, expresión que se espera provocar (solo en los emocionales),
  intensidad (leve o moderada), edad mínima, y origen y licencia obligatorios.
- **Nunca son fotos de participantes**: quien sube la imagen lo declara. Las
  abstractas son de creación propia o con una licencia que lo permita; no se
  incluyen láminas de pruebas proyectivas publicadas (también se declara).
- La imagen se decodifica y se vuelve a codificar antes de guardarse, lo que
  descarta los metadatos (EXIF, ubicación, autor). Solo PNG, JPEG o WebP de
  hasta 5 MB y 4096 px de lado.
- El sistema solo muestra y registra: no relaciona ninguna imagen con una
  condición ni interpreta lo que el participante dice ver.
- **Con niños** solo se ofrecen estímulos leves, aprobados, vigentes y con edad
  mínima adecuada. Un protocolo para niños se usa solo cuando el docente lo
  aprueba; con adultos se usa sin aprobación.
- Una versión de un protocolo usada en una sesión no se edita: editarla crea una
  versión nueva, que vuelve a pedir aprobación. La sesión conserva la versión
  que aplicó.

## Cuestionarios

- Los crea quien conduce la sesión (usuario o docente); el docente puede
  compartir uno suyo con su grupo como plantilla, que los usuarios copian y
  modifican. EMOtv no los valida como instrumento, no calcula puntajes ni
  interpreta respuestas; una nota fija bajo cada cuestionario lo dice.
- Un cuestionario usado en una sesión no se edita: se crea una versión nueva.
  Cada respuesta queda asociada a la versión exacta que se respondió.
- El previo se responde antes de iniciar el analizador (el servidor no permite
  la calibración sin él); el posterior, si lo hay, al terminar. Responde quien
  participa en la vista de participante, o quien conduce la sesión registra las
  respuestas a mano; queda anotado cuál de las dos.
- Las respuestas se guardan **cifradas** con `SENSITIVE_DATA_KEY`. Las ven quien
  condujo la sesión y su docente, nunca los administradores; cada consulta, y
  cada acceso denegado, queda en la auditoría sin el contenido.
- Se muestran tal como se dieron, sin sumarlas ni interpretarlas. La eliminación
  y la retención de un participante incluyen sus respuestas.

## Sesión guiada

- No empieza sin la confirmación de quien conduce la sesión: con un adulto, que
  dio su autorización; con un niño, que su padre, madre o tutor está presente y
  que el niño dio su asentimiento. Antes se muestra un recordatorio del
  compromiso de confidencialidad.
- La vista del participante se abre con un enlace propio (token aleatorio que el
  servidor guarda solo como hash), sin cuenta y sin la navegación de la
  aplicación; deja de valer cuando la sesión termina. Solo recibe lo que debe
  mostrar: nunca expresiones, probabilidades, calidad ni notas.
- Los cuadros de su cámara se analizan en memoria y se descartan. La tabla
  `expression_captures` guarda solo la expresión estimada, la confianza, la
  distribución, el indicador de calidad, el estímulo y el tiempo desde su
  aparición; ninguna imagen ni dato de identidad. La base de la calibración
  neutral vive solo en memoria.
- Las notas de quien conduce la sesión y lo que el participante dice ver en una
  imagen abstracta se guardan cifrados. EMOtv no interpreta esa respuesta ni la
  relaciona con ninguna condición.
- El participante puede pedir parar con un botón visible; si lo pide él o su
  tutor, la sesión termina de inmediato y queda registrado quién lo pidió.
- La eliminación y la retención de un participante incluyen su sesión guiada,
  capturas, marcadores y respuestas.

## Línea de tiempo, métricas y tendencias

- Las ven solo quien condujo la sesión y su docente (`can_access_participant`, o
  `can_access_session` en una sesión propia); nunca los administradores. Cada
  consulta, permitida o denegada, queda en la auditoría.
- Describen lo registrado sin interpretarlo: cuántos estímulos emocionales
  coincidieron con la expresión esperada, nunca valoraciones sobre la persona.
  Las imágenes abstractas no tienen métricas de coincidencia y llevan el aviso
  fijo. El carril del ritmo cardíaco queda vacío hasta que exista el sensor.

## Reporte de sesión

- Lo redacta quien condujo la sesión y lo revisa su docente asignado, que
  comenta por secciones y aprueba o devuelve el reporte. El texto y los
  comentarios se guardan cifrados; el historial no guarda contenido.
- Indica siempre que las expresiones son estimaciones de apoyo y no una
  evaluación, y qué modelo se usó. Muestra el código del participante, nunca su
  nombre.
- Solo el reporte aprobado se imprime, desde el navegador, sin generar archivos
  en el servidor; cada impresión queda en la auditoría. Si el participante
  adulto o el tutor de un niño pide una copia, el docente la imprime y se la
  entrega: no hay portal para participantes ni envío por correo.
- La eliminación y la retención del participante incluyen sus reportes,
  comentarios e historial.

## Imágenes

Ningún endpoint, pantalla ni exportación devuelve imágenes de participantes:
los cuadros de la cámara se procesan en memoria y se descartan. La prueba
`tests/integration/test_no_participant_images.py` revisa el esquema de la API y
recorre cada ruta GET con los cuatro papeles para comprobarlo. Las únicas
imágenes guardadas son estímulos subidos por docentes o por el administrador,
nunca fotos de participantes; `GET /stimuli/{id}/file` es la única ruta que
sirve una imagen y la prueba la trata como excepción explícita.

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
