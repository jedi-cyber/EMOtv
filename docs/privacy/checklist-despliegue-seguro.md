# Checklist de despliegue seguro

Para el responsable técnico (`[4: RESPONSABLE TÉCNICO DE LA PLATAFORMA]`) antes
de usar EMOtv con personas reales y después, de forma periódica. Cada punto
indica dónde lo aplica el sistema. Guía de instalación: [../docker.md](../docker.md).

Fecha de la revisión: ……………… · Revisó: ……………… · Versión de EMOtv (commit): ………………

## 1. HTTPS

- [ ] La aplicación se sirve **solo por HTTPS** fuera de `localhost`. El perfil
      `https` de Docker Compose (Caddy) usa una autoridad interna (`tls internal`)
      que provoca una advertencia en el navegador: sirve para la red local de
      pruebas. Para producción, usar un certificado de una autoridad reconocida
      (configurar `docker/Caddyfile` o el proxy de la institución).
- [ ] `ENVIRONMENT=production`: el servidor exige `CORS_ORIGINS` con `https`,
      envía `Strict-Transport-Security` y `Content-Security-Policy`, y rechaza los
      WebSocket sin origen.
- [ ] `CORS_ORIGINS` y `TRUSTED_HOSTS` contienen solo el dominio real.
- [ ] El puerto HTTP `8080` queda ligado a `127.0.0.1` (`WEB_BIND_ADDRESS`, valor
      por defecto) y solo se publica el HTTPS.

## 2. Claves y secretos

Todas van en `.env.docker` (o `.env`), que **no se versiona**. Nunca en el
repositorio, en mensajes ni en capturas.

- [ ] `SENSITIVE_DATA_KEY`: clave Fernet propia de este servidor
      (`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`).
      Sin ella, las sesiones con protocolo, los cuestionarios, los reportes y la
      eliminación de sesiones no se activan (`503`).
- [ ] `BACKUP_KEY`: otra clave Fernet, **distinta** de `SENSITIVE_DATA_KEY` (el
      script de respaldo se niega si son iguales). Se usa solo en el anfitrión; no
      se pasa a la API.
- [ ] Copia de ambas claves guardada fuera del servidor, en un lugar seguro y
      separado de los respaldos: **sin ellas, los datos cifrados y los respaldos
      no se pueden recuperar**.
- [ ] `JWT_SECRET_KEY`: aleatoria, de 32 caracteres o más (la API no arranca con
      menos).
- [ ] `POSTGRES_PASSWORD`: aleatoria; la base no se publica fuera de la red de
      Docker.
- [ ] `N8N_WEBHOOK_KEY`: la misma de la credencial Header Auth de n8n.
- [ ] Rotación: `SENSITIVE_DATA_KEY=nueva,anterior` cifra con la nueva y lee con
      ambas. No hay un script para volver a cifrar los datos existentes, así que
      la clave anterior no se puede retirar todavía.
- [ ] El detector de secretos está activo en el repositorio (`docs/security.md`).

## 3. Cuentas de administración

- [ ] Crear la cuenta de **superadministrador** en el servidor:
      `docker compose --env-file .env.docker exec api python scripts/security/create_admin.py --email <correo institucional>`.
      La contraseña temporal se muestra una sola vez y debe cambiarse en el
      primer ingreso.
- [ ] El superadministrador crea desde la aplicación la cuenta de
      **administrador** de la Facultad (`MAX_ADMIN_ACCOUNTS=1` por defecto).
- [ ] El administrador crea las cuentas de docentes y usuarios y arma los grupos.
- [ ] No quedan cuentas de demostración (`scripts/create_demo_role_accounts.py`)
      ni cuentas sin uso; las cuentas que ya no se usan se desactivan.
- [ ] `ALLOWED_ADMIN_RESET_HOSTS` solo incluye el host de la base (`db` en Docker).

## 4. Consentimiento y textos aprobados

- [ ] `CONSENT_MODE=production` con una política de consentimiento aprobada y
      activa (`development` y `demo` no son para personas reales).
- [ ] Compromiso de confidencialidad aprobado: versión actualizada y sin
      `provisional: true` en `src/emotv/resources/confidentiality_commitment.md`
      y `child_data_notice.md`.
- [ ] Formato de autorización aprobado y con versión (`[7]`).
- [ ] Datos de la Facultad completados en los documentos ([README](README.md#datos-que-debe-completar-la-facultad)).

## 5. Respaldos cifrados

- [ ] `python scripts/docker/backup_db.py` genera `backups/emotv-*.dump.enc`
      cifrado con `BACKUP_KEY`; el volcado en claro nunca se escribe en disco.
- [ ] Frecuencia de respaldo definida: ……………… y lugar de guarda: `[12]`.
- [ ] Probada una restauración (`scripts/docker/restore_db.py`) en un equipo de
      prueba.
- [ ] Se eliminan los respaldos con más antigüedad que
      `SESSION_RETENTION_MONTHS` y, si contienen voluntarios, a los 30 días.
      Esta eliminación **no es automática**.

## 6. Registros (logs) y auditoría

- [ ] **Configurar la rotación de los logs de Docker**: `docker-compose.yml` no
      define `logging`, así que los logs crecen sin límite. Los logs de `api` y
      `web` registran la IP, la ruta y el código de cada petición (incluido el
      enlace temporal de la pantalla de la persona). Definir un tamaño y un
      plazo de conservación: ……………… `[Verificar con asesoría legal el plazo.]`
- [ ] Revisar la **auditoría** de forma periódica (frecuencia: ………………):
      accesos denegados, impresiones, eliminaciones, restablecimientos de
      contraseña y cambios de grupo.
- [ ] Revisar los bloqueos por intentos de inicio de sesión fallidos.
- [ ] En n8n, el workflow EMI no guarda las ejecuciones exitosas de producción;
      las fallidas sí (con la pregunta): revisarlas solo para diagnosticar y
      borrarlas ([../chatbot/n8n-setup.md](../chatbot/n8n-setup.md)).

## 7. Actualización de dependencias

- [ ] Backend: versiones exactas en `requirements.lock`; frontend:
      `web/package-lock.json` con `npm ci` ([../docker.md](../docker.md#dependencias-fijadas)).
- [ ] Revisión periódica de vulnerabilidades (frecuencia: ………………) y
      actualización de las imágenes base (`python:3.12-slim`, `postgres:16-alpine`,
      `node:20-alpine` para compilar la web, `nginx:alpine` y `caddy:2-alpine`).
      `nginx:alpine` y `caddy:2-alpine` no fijan una versión exacta.
- [ ] Tras actualizar: `python -m pytest -q`, `npx tsc -b` y `npx vitest run`
      pasan antes de desplegar.

## 8. Retención

- [ ] `SESSION_RETENTION_MONTHS` igual al plazo aprobado (`[9]`; por defecto 12,
      contados como 360 días desde el inicio de cada sesión). La tarea corre
      al arrancar la API y una vez al día.
- [ ] `AUDIT_RETENTION_MONTHS` (24 por defecto) aprobado.
- [ ] `CHAT_RETENTION_DAYS` (90 por defecto) aprobado.
- [ ] Cuentas de voluntarios: ejecutar `python scripts/testdata/delete_test_data.py --expired`
      con regularidad (no es automático; `TEST_DATA_RETENTION_DAYS` máximo 30).
- [ ] Definido qué pasa con las cuentas de usuarios y docentes que dejan la
      Facultad y con sus sesiones propias: hoy **no tienen retención automática**.
- [ ] Definido el plazo de conservación de las actas de eliminación y de los
      formatos en papel. `[Verificar con asesoría legal.]`
