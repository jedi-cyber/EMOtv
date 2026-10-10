# Protocolo de pruebas con voluntarios

Este protocolo explica cómo preparar, hacer y cerrar una prueba funcional de
EMOtv con personas. Solo participan voluntarios **mayores de edad** que **no
pertenecen a la Facultad de Psicología de la UNHEVAL** y que firman el
consentimiento en papel. EMOtv estima la expresión facial visible: no
diagnostica, no determina el estado psicológico de nadie y sus actividades son
actividad guiada, no terapia.

El consentimiento en papel promete tres cosas, y este protocolo sirve para
cumplirlas:

1. La cuenta se identifica solo con un código `PRUEBA-NN`, sin nombre ni
   correo real.
2. Todos los registros del voluntario se eliminan como máximo a los 30 días,
   o antes si lo pide.
3. La eliminación queda en un acta que incluye su verificación.

Los comandos se ejecutan desde la raíz del repositorio. Con Docker Compose,
antepón `docker compose --env-file .env.docker exec api` a cada
`python scripts/testdata/...`.

## 1. Preparación

1. Configura `CONSENT_MODE=demo` en `.env` o `.env.docker`. El modo
   `development` **nunca** se usa con voluntarios. Ver
   [consent-demo.md](../consent-demo.md).
2. Aplica las migraciones: `python -m alembic upgrade head`. En Docker se
   aplican solas al arrancar la API.
3. Crea una cuenta por voluntario:

   ```powershell
   python scripts/testdata/create_test_accounts.py --count 3
   ```

   El script crea cuentas de estudiante con códigos consecutivos (`PRUEBA-04`,
   `PRUEBA-05`, …, a partir del último que exista), correo ficticio
   `prueba-NN@emotv.local` y una contraseña aleatoria. La contraseña aparece
   **una sola vez** en la terminal. Anótala en la hoja de entrega de ese
   código y no la guardes en archivos del repositorio. El script no acepta
   nombres ni correos y no registra el consentimiento: cada voluntario lo
   acepta en la aplicación.
4. Prepara dos ejemplares impresos del consentimiento por voluntario.

## 2. Firma del consentimiento en papel

1. Lee el consentimiento con el voluntario y responde sus dudas. Confirma que
   es mayor de edad y que no pertenece a la Facultad de Psicología.
2. Firman **dos ejemplares**: uno queda con el voluntario y otro con el
   equipo.
3. Escribe en ambos ejemplares el código asignado (`PRUEBA-NN`) y la fecha.
   El papel es el **único lugar** que relaciona el nombre con el código. Ese
   vínculo no se escribe en EMOtv, en hojas de cálculo ni en el repositorio.

Si se elimina la cuenta con el código más alto, la siguiente cuenta que se
cree volverá a usar ese código. La fecha del papel y la fecha de creación que
figura en el acta permiten distinguir a los dos participantes.

## 3. Entrega del código

Entrega al voluntario el código, el correo ficticio y la contraseña de su
cuenta. Dile que puede pedir la eliminación de sus datos en cualquier momento
indicando su código, y que puede revocar el consentimiento desde la página
**Consentimiento** de la aplicación.

## 4. Desarrollo de la prueba

1. El voluntario inicia sesión y acepta el consentimiento de la aplicación
   (política de prueba v0.3). Si no lo acepta, la prueba termina ahí.
2. Usa EMOtv por sí mismo: analizador facial, actividad recomendada y, si
   corresponde, Emi. La persona que facilita la prueba no escribe ni responde
   por el voluntario.
3. Recuérdale que el resultado es una estimación de la expresión visible y no
   dice lo que siente.
4. No se toman fotografías ni videos de la prueba. EMOtv tampoco los guarda:
   procesa los frames y los descarta.

## 5. Registro de resultados

Anota lo observado en [manual-checklist.md](manual-checklist.md). Identifica a
la persona solo con su código `PRUEBA-NN`, nunca con su nombre, e incluye la
fecha de la prueba.

## 6. Plazo de 30 días

Los datos de cada cuenta se eliminan **como máximo a los 30 días** desde que se
creó la cuenta. El plazo se configura con `TEST_DATA_RETENTION_DAYS` (30 por
defecto). Solo admite valores de 1 a 30, porque el consentimiento no permite
más.

- Ejecuta `--expired` al menos una vez por semana mientras haya cuentas de
  prueba y apúntalo en el calendario del equipo.
- Si un voluntario lo pide, elimina su cuenta ese mismo día con `--code`.
- Al terminar todas las pruebas, elimina las cuentas que queden con
  `--all-test-accounts`.

## 7. Eliminación con el script

```powershell
# A pedido del voluntario
python scripts/testdata/delete_test_data.py --code PRUEBA-07 --save

# Cuentas con más de TEST_DATA_RETENTION_DAYS días
python scripts/testdata/delete_test_data.py --expired --save

# Cierre de pruebas: todas las cuentas de prueba (pide escribir ELIMINAR)
python scripts/testdata/delete_test_data.py --all-test-accounts --save
```

El motivo del acta se asigna según el modo: solicitud del participante,
expirado o cierre de pruebas. Puedes cambiarlo con
`--reason solicitud|expirado|cierre`.

Qué hace el script:

- Solo elimina cuentas con `is_test_account` activo. Si recibe el código de
  otra cuenta, se niega y no borra nada.
- Borra, en este orden: `chat_messages`, `chat_conversations`, `sessions`,
  `psychologist_assignments`, `consents`, `login_attempts` (identificados por
  el SHA-256 del correo ficticio), `students` y `users`. Además, deja en nulo
  las referencias de autoría que esa cuenta tenga en filas de otras personas
  (`psychologist_assignments.assigned_by_user_id` y
  `expression_info.reviewed_by_user_id`).
- Borra las sesiones de forma explícita. Su clave foránea es `SET NULL` y, si
  no se borraran, quedarían como sesiones anónimas huérfanas.
- Hace todo en **una transacción**. Antes de confirmarla, cuenta los registros
  que quedan asociados a cada código en cada tabla. Si alguno no es cero, o si
  ocurre cualquier error, se revierte todo y no se borra nada.
- Después de confirmar, repite el conteo con otra conexión y lo informa en el
  acta. Si esa verificación falla, el script termina con código 2: no firmes el
  acta hasta revisar la base.

## 8. Acta de eliminación

Al terminar, el script imprime un texto listo para copiar al acta con estos
datos:

- código;
- fecha de creación de la cuenta;
- fecha y hora de la eliminación;
- motivo;
- registros eliminados por tabla;
- resultado de la verificación.

Con `--save`, también lo guarda en `reports/deletions/`, una carpeta que no se
sube al repositorio. En Docker queda dentro del contenedor y se pierde al
recrearlo. Cópiala antes de recrearlo:

```powershell
docker compose --env-file .env.docker cp api:/app/reports/deletions/. reports/deletions/
```

Imprime el acta, complétala con el nombre y la firma de quien eliminó los
datos y archívala junto con el ejemplar del consentimiento del voluntario. Las
horas se muestran en la zona horaria del equipo que ejecuta el script; en
Docker esa zona es UTC.

## 9. Respaldos

Un respaldo hecho con `scripts/docker/backup_db.py` **antes** de la
eliminación contiene los datos del voluntario. El script de eliminación lo
advierte al terminar. Por eso:

- elimina los respaldos de `backups/` que tengan más de 30 días;
- si necesitas conservar un respaldo, haz uno nuevo después de la eliminación
  y borra los anteriores;
- no copies respaldos fuera del equipo de trabajo.

## 10. Logs

Ni la API ni nginx registran el contenido de los mensajes de Emi, los frames
ni los correos. Para Emi, la API solo registra el `request_id`, el código de
respuesta de n8n y si la pregunta estuvo dentro de alcance. Los intentos de
inicio de sesión guardan el SHA-256 del correo, no el correo. nginx registra
la ruta de cada petición y la IP. En las rutas no aparecen correos y nginx no
registra el cuerpo de las peticiones, que es donde viajan los frames y los
mensajes.

## 11. Archivo del papel

Guarda juntos y bajo llave el ejemplar firmado del consentimiento y el acta de
eliminación de cada voluntario. Los documentos en papel no se digitalizan ni
se suben al repositorio. Sigue las indicaciones del docente responsable sobre
el tiempo de conservación de esos documentos.
