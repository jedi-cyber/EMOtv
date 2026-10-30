# Privacidad y protección de datos personales

Documentación de la protección de datos personales de EMOtv, derivada del código
y de las migraciones, para que la Facultad de Psicología de la UNHEVAL la revise
y la apruebe. Se refiere a la Ley N.° 29733 y a su reglamento (Decreto Supremo
016-2024-JUS). No interpreta la norma: los puntos que dependen de su
interpretación están marcados **«verificar con asesoría legal»**.

EMOtv **estima una expresión facial**: no diagnostica, no determina el estado
psicológico de nadie y no sustituye a un profesional.

## Datos que debe completar la Facultad

Los documentos usan estos campos entre corchetes, con su número (por ejemplo,
`[3: CONTACTO PARA EJERCER DERECHOS]`). No se rellenan con datos supuestos: los
completa la Facultad antes de aprobar los documentos.

1. `[1: RESPONSABLE DEL TRATAMIENTO]`: institución y unidad responsable.
2. `[2: DOMICILIO DEL RESPONSABLE]`.
3. `[3: CONTACTO PARA EJERCER DERECHOS]`: correo u oficina donde se presentan
   las solicitudes de acceso, rectificación, cancelación y oposición.
4. `[4: RESPONSABLE TÉCNICO DE LA PLATAFORMA]`: quien opera el servidor.
5. `[5: FECHA DE APROBACIÓN DE LA POLÍTICA]`.
6. `[6: ÓRGANO QUE APRUEBA]`.
7. `[7: VERSIÓN DEL FORMATO DE AUTORIZACIÓN]`: la del formato en papel donde se anota el código de cada sesión.
8. `[8: FECHA DE APROBACIÓN DEL COMPROMISO]`.
9. `[9: PLAZO DE RETENCIÓN APROBADO]`: hoy `SESSION_RETENTION_MONTHS=12`.
10. `[10: LUGAR DE CUSTODIA DE LAS FICHAS Y FORMATOS EN PAPEL]`.
11. `[11: RESPONSABLE DE INCIDENTES]`.
12. `[12: UBICACIÓN DEL SERVIDOR Y DE LOS RESPALDOS]`.
13. `[13: INSCRIPCIÓN DEL BANCO DE DATOS, SI CORRESPONDE]` (verificar con
    asesoría legal).
14. `[14: UBICACIÓN DEL REGISTRO DE SOLICITUDES]`.
15. `[15: UBICACIÓN DEL REGISTRO DE INCIDENTES]`.
16. `[16: CANAL DE COMUNICACIÓN CON LA AUTORIDAD]` de protección de datos
    personales.

## Índice

| Documento | Para quién | Contenido |
| --- | --- | --- |
| [politica-de-privacidad.md](politica-de-privacidad.md) | Personas evaluadas y tutores | Qué datos se tratan, para qué, quién accede, cuánto tiempo, servicios externos y derechos |
| [formato-consentimiento.md](formato-consentimiento.md) | Personas evaluadas, tutores y quien conduce | Modelo de autorización (adulto y tutor), aceptación del niño, código de cada sesión y retiro |
| [registro-de-tratamiento.md](registro-de-tratamiento.md) | Facultad y asesoría legal | Cada tabla con datos personales: campos, finalidad, base, acceso, cifrado y retención |
| [matriz-de-accesos.md](matriz-de-accesos.md) | Facultad y responsable técnico | Qué ve y qué puede hacer cada cuenta |
| [compromiso-de-confidencialidad.md](compromiso-de-confidencialidad.md) | Usuarios y docentes | Texto vigente y reparto de responsabilidades |
| [guia-de-uso.md](guia-de-uso.md) | Usuarios y docentes | Qué registrar y qué no, Emi y qué hacer ante una filtración |
| [procedimiento-derechos.md](procedimiento-derechos.md) | Docentes | Acceso, rectificación, cancelación y oposición |
| [procedimiento-incidentes.md](procedimiento-incidentes.md) | Responsable de incidentes | Detección, contención, evaluación, comunicación y registro |
| [checklist-despliegue-seguro.md](checklist-despliegue-seguro.md) | Responsable técnico | HTTPS, claves, cuentas, respaldos, registros, dependencias y retención |

El resto de esta página describe los controles técnicos tal como los aplica el
servidor (FastAPI); ocultar un botón en la interfaz nunca es la única protección.

## Controles técnicos

## Papeles

| Papel (interno) | En pantalla | Para qué | Nunca accede a |
| --- | --- | --- | --- |
| `superadmin` | Superadministrador | Soporte técnico: modelos, catálogos, políticas, la cuenta de administrador y la auditoría. Restablece solo la contraseña del administrador. | Sesiones, cuestionarios, respuestas y reportes |
| `admin` | Administrador | Persona con cargo superior en la Facultad: crea y desactiva docentes y usuarios, arma los grupos, restablece sus contraseñas y consulta la auditoría. | Sesiones, cuestionarios, respuestas y reportes |
| `psychologist` | Docente | Ve las sesiones de los usuarios de su grupo y las suyas, y las elimina con acta. Conduce sesiones propias. | Datos de otros grupos |
| `student` | Usuario | Conduce sesiones, propias o con otras personas, y ve solo lo suyo. | Datos de otros usuarios |

- Solo el superadministrador crea o desactiva la cuenta de administrador. Por
  defecto puede haber **una** activa (`MAX_ADMIN_ACCOUNTS`).
- Un docente tiene varios usuarios; **un usuario tiene un solo docente**
  (restricción única en `psychologist_assignments.student_id`). Solo el
  administrador mueve un usuario a otro grupo: el acceso del docente sigue la
  asignación vigente y el cambio queda en la auditoría.
- Las **personas evaluadas no se registran**: no hay participantes ni cuentas
  para ellas. Cada sesión lleva un código aleatorio (`S-XXXXXX`, único, que no
  se puede editar), sin nombre, DNI, edad, foto ni datos del tutor; la API
  rechaza campos de más. El código se muestra al empezar y al terminar, y quien
  conduce lo anota en el formato firmado que custodia el docente; el sistema no
  puede recuperar la relación código–persona. No hay seguimiento ni
  estadísticas por persona.
- **Estadísticas** (`GET /statistics`): cuentan sesiones, no personas. Se
  calculan en el servidor solo con las sesiones a las que la cuenta ya tiene
  acceso; el docente ve además los totales por usuario de su grupo (correo y
  cantidad de sesiones). Las respuestas de texto no se muestran, solo cuántas
  hubo. Cada consulta se audita sin contenido y no se generan archivos.
- La cuenta de superadministrador se crea con `scripts/security/create_admin.py`
  y su contraseña se recupera con `scripts/security/reset_admin_password.py`
  (solo en el servidor).

## Control de acceso central

`AuthorizationService.can_access_session(usuario, sesión)` es la única regla de
acceso a una sesión y a todo lo suyo (capturas, cuestionarios, marcadores, lo
que dijo ver, línea de tiempo, métricas, reporte y eliminación). Acceden:

1. la cuenta que condujo la sesión;
2. el docente asignado **en este momento** a esa cuenta.

El administrador y el superadministrador nunca acceden. Solo quien conduce una
sesión puede enviar su cámara o cancelarla.

## Inicio de una sesión y autorización

- Toda sesión empieza en el **Analizador**: con un protocolo (una receta
  guardada) o sin él. Con protocolo, el público lo decide el protocolo (adultos
  o niños). Sin protocolo se pregunta «¿Con quién es la sesión?»: Conmigo, Un
  adulto o Un niño o niña. Una sesión infantil sin protocolo no muestra imágenes
  ni cuestionarios.
- Cada sesión pide **una sola confirmación** antes de crearse, según su público:
  - propia o con una persona adulta: «Es una sesión mía o cuento con la
    autorización firmada de la persona adulta»;
  - con un niño o una niña: «Su tutor autorizó por escrito, está presente y el
    niño aceptó participar».

  La casilla empieza sin marcar. Sin ella, el servidor responde `422` y no hay
  sesión. Se guarda la fecha y hora de la confirmación
  (`sessions.authorization_confirmed_at`), no el formato ni datos de quien
  firma.
- La autorización se firma **en papel** con el formato aprobado (dos
  autorizaciones separadas: participación y cámara). EMOtv no la registra.
- **Retiro.** Quien conduce no inicia sesiones nuevas con esa persona (cada una
  pide de nuevo la confirmación) y, si se pide, solicita eliminar cada sesión
  anotada en el formato.
- El inicio de cada sesión queda en la auditoría.

## Banco de estímulos y protocolos

- Los estímulos los crean los docentes (para los usuarios de su grupo) y el
  administrador (para toda la institución), sin revisión; los usuarios los usan
  en sus protocolos junto con sus **imágenes propias** (ver abajo). Cada uno tiene tipo (emocional o abstracta),
  categoría, expresión que se espera provocar (solo en los emocionales),
  intensidad (leve o moderada), edad mínima, y origen y licencia obligatorios.
- **Nunca son fotos de personas evaluadas**: quien sube la imagen lo declara. Las
  abstractas son de creación propia o con una licencia que lo permita; no se
  incluyen láminas de pruebas proyectivas publicadas (también se declara).
- La imagen se decodifica y se vuelve a codificar antes de guardarse, lo que
  descarta los metadatos (EXIF, ubicación, autor). Solo PNG, JPEG o WebP de
  hasta 5 MB y 4096 px de lado.
- El sistema solo muestra y registra: no relaciona ninguna imagen con una
  condición ni interpreta lo que la persona dice ver.

### Imágenes propias de los usuarios

- Un usuario sube imágenes para sus protocolos desde **Mi material → Imágenes**,
  por lote. Cada una indica de dónde es, para quién es («Para niños» o «Para
  adultos») y lleva la casilla obligatoria «No es una foto de una persona que
  pueda identificarse, y tengo derecho a usarla». Hay un máximo por usuario
  (`IMAGE_UPLOAD_LIMIT_PER_USER`).
- **Detección automática de personas, en memoria.** Antes de guardar, el
  servidor decodifica la imagen, la reduce a 1280 px por lado y busca rostros
  (YuNet) y cuerpos (MediaPipe Pose), los mismos modelos que ya usa EMOtv. Solo
  obtiene una confianza: no reconoce a nadie, no compara rostros y no guarda
  plantillas, recortes ni la imagen analizada. Con confianza igual o mayor que
  `IMAGE_PERSON_REJECT_CONFIDENCE` la imagen se rechaza y no se guarda nada;
  desde `IMAGE_PERSON_REVIEW_CONFIDENCE` se guarda marcada «Revisar: posible
  persona». Si los modelos no están instalados, no se acepta ninguna imagen
  (`503`).
- **La detección no es infalible.** Puede no ver a una persona (de espaldas,
  pequeña, dibujada con realismo, parcialmente tapada) y puede marcar imágenes
  sin personas. Por eso **el docente revisa todas las imágenes** antes de que se
  usen, y la pantalla de revisión le recuerda: «Si ves a una persona, elimina la
  imagen». Las imágenes con personas las agrega el docente al banco.
- Una imagen aceptada se guarda reescrita, sin metadatos, **pendiente**: la ven
  solo quien la subió («En revisión») y su docente, y no se puede elegir en
  ningún protocolo ni sesión.
- El docente revisa en **Imágenes por revisar** (con contador en el menú) los
  lotes de su grupo, con el correo de quien subió y la fecha. Para cada imagen
  elige «Para niños», «Para adultos» o «Eliminar», también para varias a la vez;
  la respuesta del usuario viene preseleccionada. «Eliminar» borra el archivo y
  el registro, con un motivo opcional que el usuario ve como aviso. Si una sesión
  o un protocolo ya nombran la imagen, se borra el archivo y queda solo un
  registro sin imagen, para no alterar el historial.
- «Para niños» sirve en protocolos para niños y para adultos; «Para adultos»,
  solo en protocolos para adultos. Si el docente elimina una imagen usada o la
  cambia a «Para adultos», los protocolos afectados quedan «Necesita una imagen»
  y su dueño recibe un aviso.
- Una imagen que nadie revisa se elimina a los `IMAGE_REVIEW_DAYS` días (30 por
  defecto), con un aviso al usuario siete días antes.
- La auditoría registra, sin contenido, cada lote subido, cada rechazo
  automático, cada decisión del docente, cada eliminación y cada apertura de la
  vista ampliada.
- Un **protocolo** es una receta guardada: qué aplicar en una sesión
  (cuestionario previo opcional, imágenes en orden con sus segundos y
  cuestionario posterior opcional). Su primera pregunta, obligatoria, es «¿Para
  adultos o para niños?». Se guarda sin ejecutarlo y no necesita la aprobación
  del docente.
- Un protocolo **para niños** solo admite estímulos leves, aprobados y
  vigentes (el servidor lo comprueba al guardarlo y al usarlo). La edad de la
  persona no se registra, así que la edad mínima no filtra; los estímulos
  institucionales tampoco se filtran por edad.
- Una versión de un protocolo usada en una sesión no se edita: editarla crea una
  versión nueva. La sesión conserva la versión que aplicó.

## Cuestionarios

- Los crea quien conduce la sesión (usuario o docente); el docente puede
  compartir uno suyo con su grupo como plantilla, que los usuarios copian y
  modifican. EMOtv no los valida como instrumento, no calcula puntajes ni
  interpreta respuestas; una nota fija bajo cada cuestionario lo dice.
- Un cuestionario usado en una sesión no se edita: se crea una versión nueva.
  Cada respuesta queda asociada a la versión exacta que se respondió.
- Se aplican solo dentro de un protocolo. El previo se responde antes de la
  calibración (el servidor no la permite sin él); el posterior, si lo hay, al
  terminar. Responde la persona en su pantalla, o quien conduce registra las
  respuestas a mano; queda anotado cuál de las dos.
- Las respuestas se guardan **cifradas** con `SENSITIVE_DATA_KEY`. Las ven quien
  condujo la sesión y su docente, nunca los administradores; cada consulta, y
  cada acceso denegado, queda en la auditoría sin el contenido.
- Se muestran tal como se dieron, sin sumarlas ni interpretarlas. La eliminación
  y la retención de una sesión incluyen sus respuestas.

## Sesión con protocolo

- La confirmación se da una vez, al crear la sesión; durante la sesión no se
  pide otra.
- La pantalla de la persona se abre con un enlace propio (token aleatorio que el
  servidor guarda solo como hash), sin cuenta y sin la navegación de la
  aplicación; deja de valer cuando la sesión termina. Solo recibe lo que debe
  mostrar: nunca expresiones, probabilidades, calidad ni notas.
- Los cuadros de su cámara se analizan en memoria y se descartan. La tabla
  `expression_captures` guarda solo la expresión estimada, la confianza, la
  distribución, el indicador de calidad, el estímulo (si lo hay) y el tiempo desde su
  aparición; ninguna imagen ni dato de identidad. La base de la calibración
  neutral vive solo en memoria.
- Las notas de quien conduce la sesión y lo que la persona dice ver en una
  imagen abstracta se guardan cifrados. EMOtv no interpreta esa respuesta ni la
  relaciona con ninguna condición.
- La persona puede pedir parar con un botón visible; si lo pide ella o su
  tutor, la sesión termina de inmediato y queda registrado quién lo pidió.
- La eliminación y la retención de una sesión incluyen el avance del protocolo,
  las capturas, los marcadores y las respuestas.

## Línea de tiempo y métricas

- Las ven solo quien condujo la sesión y su docente (`can_access_session`);
  nunca los administradores. No hay tendencias ni seguimiento por persona. Cada
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
  evaluación, y qué modelo se usó. Muestra el código de la sesión, nunca un
  nombre.
- Solo el reporte aprobado se imprime, desde el navegador, sin generar archivos
  en el servidor; cada impresión queda en la auditoría. Si la persona adulta o
  el tutor de un niño pide una copia, el docente la imprime y se la entrega: no
  hay portal para personas evaluadas ni envío por correo.
- La eliminación y la retención de la sesión incluyen sus reportes,
  comentarios e historial.

## Imágenes

Ningún endpoint, pantalla ni exportación devuelve imágenes de personas evaluadas:
los cuadros de la cámara se procesan en memoria y se descartan. La prueba
`tests/integration/test_no_participant_images.py` revisa el esquema de la API y
recorre cada ruta GET con los cuatro papeles para comprobarlo. Las únicas
imágenes guardadas son estímulos subidos por docentes, por el administrador o por
usuarios (estos, tras la detección automática de personas y con la revisión del
docente), nunca fotos de personas evaluadas. `GET /stimuli/{id}/file` y
`GET /own-stimuli/{id}/file` son las únicas rutas que sirven una imagen y la
prueba las trata como excepciones explícitas.

## Compromiso de confidencialidad

- Texto versionado en `src/emotv/resources/confidentiality_commitment.md`,
  marcado como **provisional** hasta que la Facultad lo revise.
- Usuarios y docentes lo aceptan una vez, en una ventana al entrar que no se
  cierra sin aceptar, y cada vez que cambia la versión. Sin aceptarlo, el
  servidor rechaza iniciar sesiones (`428`).
- Antes de la primera sesión con un niño o una niña aparece un aviso reforzado
  (`src/emotv/resources/child_data_notice.md`): los datos de menores son más
  sensibles. Se acepta en la misma ventana de confirmación de la sesión; sin
  él, el servidor responde `428`.
- Cada aceptación queda en la auditoría con su versión.

## Cifrado de campos sensibles

- Se cifran en reposo con Fernet (`emotv.shared.security.field_encryption`):
  notas de los marcadores (`session_markers.note_encrypted`), respuestas de cuestionarios
  (`questionnaire_responses.answers_encrypted`), lo que la persona dice ver
  en una imagen abstracta (`verbal_responses.text_encrypted`), texto de los
  reportes (`session_reports.narrative_encrypted`) y comentarios del docente
  (`report_comments.text_encrypted`).
- **No se cifran en la aplicación**: el código y el público de la sesión, la
  fecha de la confirmación, las expresiones estimadas
  (`expression_captures`, `sessions`), los correos de las cuentas ni las
  conversaciones con Emi (`chat_messages`). El detalle está en el
  [registro de tratamiento](registro-de-tratamiento.md).
- La clave es `SENSITIVE_DATA_KEY` (vacía en los archivos de ejemplo; nunca en
  el repositorio). Generar una:
  `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
- **Rotación:** `SENSITIVE_DATA_KEY=nueva,anterior`. La primera clave cifra y
  todas descifran. Todavía no hay un script que vuelva a cifrar los datos
  existentes con la clave nueva, así que la anterior no se puede retirar sin
  perder lo cifrado con ella.
- Sin clave válida, las sesiones con protocolo, los cuestionarios, los reportes
  y la eliminación de sesiones **no se activan** (`503`) y la API registra el motivo en el log.

## Auditoría

Tabla `access_audit`: fecha, cuenta que actúa y su papel, acción, tipo e id del
recurso, y resultado (`success`, `denied`, `failure`). **Nunca** guarda notas,
respuestas, correos ni imágenes.

- Se registran consultas, creaciones, impresiones, aprobaciones, eliminaciones,
  solicitudes de eliminación, el inicio de cada sesión, restablecimientos de
  contraseña, cambios de grupo, creación y desactivación de cuentas, y
  aceptaciones del compromiso. Los accesos denegados a una sesión también.
- La API solo la consulta (`GET /audit`, con filtros), para el administrador y
  el superadministrador. No existe ninguna operación para editarla o borrarla.
- Se conserva `AUDIT_RETENTION_MONTHS` meses (24 por defecto).

## Retención y eliminación

Todo es **por sesión**.

- **Retención:** una tarea que corre al arrancar la API y luego una vez al día
  elimina las sesiones con más de `SESSION_RETENTION_MONTHS` meses (12 por
  defecto; el código cuenta meses de 30 días) **desde su inicio**, con todos sus
  registros. Se aplica a toda sesión, también a las propias. La auditoría anota
  solo la cantidad. Una sesión que falle la verificación se conserva.
- **Eliminación a pedido:** quien condujo la sesión la pide y el docente la
  ejecuta; el docente también puede eliminar directamente sus sesiones y las de
  su grupo. Una sesión en curso no se elimina. Es una sola transacción: borra la
  sesión y sus registros, verifica que no quede ninguno y, si la verificación
  falla, revierte todo. Genera un **acta imprimible** con el código de la
  sesión, la fecha, la cantidad de registros por tipo y el resultado de la
  verificación, sin datos personales. Imprimirla queda en la auditoría.
- Cada tabla nueva con datos de una sesión se agrega a `SESSION_LINKED_RECORDS`,
  así la retención y la eliminación la incluyen.

## Registros y respuestas HTTP

- Los logs no incluyen cuerpos de peticiones, notas, respuestas ni imágenes.
  Sí incluyen el registro de acceso de uvicorn y nginx: IP, método, ruta y código
  de cada petición. La ruta de la pantalla de la persona contiene su enlace
  temporal (`/participant-view/{token}`), válido mientras dura la sesión. Docker
  Compose no configura rotación de logs (ver el
  [checklist](checklist-despliegue-seguro.md#6-registros-logs-y-auditoría)).
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
respaldos con más antigüedad que `SESSION_RETENTION_MONTHS`**, y los de
cuentas de voluntarios a los 30 días.

## Configuración

| Variable | Por defecto | Uso |
| --- | --- | --- |
| `SENSITIVE_DATA_KEY` | vacía | Claves Fernet de los campos sensibles (separadas por comas) |
| `BACKUP_KEY` | vacía | Clave Fernet de los respaldos (solo en el anfitrión) |
| `MAX_ADMIN_ACCOUNTS` | 1 | Cuentas de administrador activas a la vez |
| `SESSION_RETENTION_MONTHS` | 12 | Retención de cada sesión y sus registros, desde su inicio |
| `AUDIT_RETENTION_MONTHS` | 24 | Retención de la auditoría |
| `CHAT_RETENTION_DAYS` | 90 | Retención de las conversaciones con Emi |
| `TEST_DATA_RETENTION_DAYS` | 30 | Plazo de las cuentas de voluntarios (máximo 30; se aplica con `scripts/testdata/delete_test_data.py --expired`) |
