# Procedimiento ante incidentes de seguridad de datos personales

> Sujeto a revisión de la Facultad. La normativa vigente (Ley N.° 29733 y su
> reglamento, D.S. 016-2024-JUS) exige **comunicar los incidentes a la autoridad
> de protección de datos personales dentro de las 48 horas posteriores a tomar
> conocimiento**. `[Verificar con asesoría legal: el plazo, qué incidentes deben
> comunicarse, el contenido de la comunicación, el canal y cuándo comunicar a
> las personas afectadas.]`

Responsable de incidentes: `[11: RESPONSABLE DE INCIDENTES]` ·
Canal ante la autoridad: `[16: CANAL DE COMUNICACIÓN CON LA AUTORIDAD]` ·
Registro: `[15: UBICACIÓN DEL REGISTRO DE INCIDENTES]`.

Un incidente es cualquier hecho que expone, altera, pierde o destruye datos
personales sin autorización. Ejemplos con EMOtv: una foto o captura de la
pantalla con datos de una sesión difundida por mensajería; un formato
código–persona perdida; una cuenta usada por otra persona; un respaldo, un
archivo `.env.docker` o una clave (`SENSITIVE_DATA_KEY`, `BACKUP_KEY`,
`JWT_SECRET_KEY`, `N8N_WEBHOOK_KEY`) expuestos; acceso no autorizado al
servidor o a la base de datos.

## 1. Detección

Cualquier persona que sospeche un incidente avisa de inmediato al responsable de
incidentes y al docente ([guia-de-uso.md](guia-de-uso.md#si-sospechas-una-filtración)).
Anota la **fecha y hora en que se tomó conocimiento**: desde ahí corre el plazo
de comunicación.

Fuentes en el sistema:

| Fuente | Qué permite ver | Quién |
| --- | --- | --- |
| Auditoría (`GET /audit`, pantalla **Auditoría**) | Accesos **denegados** a sesiones, impresiones, solicitudes de eliminación, eliminaciones, creación, desactivación y restablecimiento de cuentas, cambios de grupo, con fecha, cuenta y resultado. Sin contenido | Administrador y superadministrador |
| Logs de los contenedores (`docker compose logs api` y `web`) | IP, ruta y código de respuesta de cada petición; errores de la aplicación | Responsable técnico, en el servidor |
| Límite de intentos de inicio de sesión | Bloqueos por muchos fallos desde un correo o una IP (tabla `login_attempts`, 24 horas) | Responsable técnico, en la base |

## 2. Contención

Según el caso, el mismo día:

| Situación | Acción |
| --- | --- |
| Cuenta usada por otra persona | El administrador **desactiva** la cuenta (docentes y usuarios; la del administrador, el superadministrador). Una cuenta desactivada no accede a nada. Luego **restablece la contraseña**: al cambiarla se invalidan las sesiones abiertas de esa cuenta |
| Sospecha de robo de sesiones en general | Cambiar `JWT_SECRET_KEY` y reiniciar la API: todas las sesiones abiertas dejan de valer |
| Clave `SENSITIVE_DATA_KEY` expuesta | Generar una nueva y configurar `SENSITIVE_DATA_KEY=nueva,anterior`: lo nuevo se cifra con la nueva y lo anterior sigue legible. **El sistema no tiene hoy un script que vuelva a cifrar los datos existentes**, así que la clave anterior no se puede retirar sin perder esos datos; registrar esta limitación en el incidente |
| Respaldo o `BACKUP_KEY` expuestos | Cambiar `BACKUP_KEY`, generar un respaldo nuevo y eliminar los anteriores cifrados con la clave expuesta |
| Clave del webhook de Emi expuesta | Cambiarla en n8n y en `.env.docker` ([chatbot/n8n-setup.md](../chatbot/n8n-setup.md)) |
| Captura o foto difundida | Pedir a quien la difundió y a quienes la recibieron que la eliminen; no reenviarla como evidencia, solo describirla |
| Formato firmado perdido | Buscarlo y, si no aparece, evaluar con el docente si se deben eliminar las sesiones con los códigos que tenía |
| Servidor comprometido | Aislarlo de la red, conservar los logs y avisar al área técnica de la institución |

## 3. Evaluación del alcance

Responder y anotar en el registro:

- ¿Qué datos? (códigos, respuestas, expresiones estimadas, reportes, notas,
  cuentas, claves). Recordar: el sistema no guarda nombres, DNI ni imágenes de
  personas evaluadas; la relación código–persona solo está en papel.
- ¿Estaban cifrados? Notas, respuestas, comentarios, lo que dijo ver y reportes
  se cifran con `SENSITIVE_DATA_KEY`; un volcado de la base sin esa clave no los
  revela. El resto no está cifrado en la aplicación ([registro-de-tratamiento.md](registro-de-tratamiento.md)).
- ¿Cuántas sesiones y cuentas? ¿Hay sesiones con **niños**?
- ¿Se puede identificar a las personas? (por ejemplo, si una captura muestra el
  código junto a la cara, o si se perdió el formato firmado).
- ¿Desde cuándo y hasta cuándo? Usar la auditoría y los logs.
- ¿Qué riesgo tiene para las personas? `[Verificar con asesoría legal: criterios
  para decidir si se comunica a la autoridad y a los afectados.]`

## 4. Comunicación

- **A la autoridad de protección de datos personales**, dentro de las 48 horas
  posteriores a tomar conocimiento, por `[16]`, con lo que se sepa en ese momento;
  se completa después si hace falta. `[Verificar con asesoría legal.]`
- **A las personas afectadas**: EMOtv no tiene sus datos de contacto. El docente
  usa el formato firmado para ubicar a la persona adulta o al padre, madre o
  tutor, y comunica en lenguaje sencillo qué pasó, qué datos se vieron afectados,
  qué se hizo y a quién pueden dirigirse (`[3: CONTACTO PARA EJERCER DERECHOS]`).
  `[Verificar con asesoría legal: cuándo y cómo.]`
- **Internamente**: a `[1: RESPONSABLE DEL TRATAMIENTO]` y al docente responsable.

## 5. Registro posterior

Todo incidente se registra, aunque se concluya que no había que comunicarlo. El
registro va fuera del sistema (`[15]`), **sin nombres de las personas evaluadas** (solo
códigos) y sin copiar los datos expuestos.

Después de cerrarlo: revisar qué falló, actualizar este procedimiento, la
[guía de uso](guia-de-uso.md) o el [checklist](checklist-despliegue-seguro.md), y
recordar el compromiso de confidencialidad a las cuentas involucradas.

## Plantilla de registro del incidente

| Campo | Contenido |
| --- | --- |
| N.° de incidente | 2026-INC-001 |
| Fecha y hora en que se tomó conocimiento | |
| Quién lo detectó y cómo | Cargo; aviso, auditoría, logs… |
| Descripción | Qué pasó, sin copiar los datos |
| Fecha y hora estimadas de inicio y fin | |
| Datos afectados | Tipos de datos; ¿cifrados? |
| Personas afectadas | Cantidad de sesiones (¿con niños?) y de cuentas; solo códigos |
| ¿Se puede identificar a las personas? | Sí / No / No se sabe — por qué |
| Medidas de contención | Acción, fecha y quién la hizo |
| Evaluación del riesgo | |
| Comunicación a la autoridad | Fecha y hora, canal, n.° de constancia — o motivo para no comunicar |
| Comunicación a las personas afectadas | Fecha, medio, quién comunicó — o motivo |
| Medidas para que no se repita | |
| Fecha de cierre y responsable | |
