# EMOtv con Docker

Esta guía permite levantar EMOtv en cualquier computadora con Docker Desktop,
sin instalar Python, Node.js ni PostgreSQL. Está escrita para quien nunca usó
Docker: sigue los pasos en orden.

EMOtv estima una expresión facial con fines formativos. No diagnostica, no
determina el estado psicológico y no sustituye a un profesional. La cámara se
abre en el navegador; los contenedores no usan ninguna cámara del equipo y no
guardan fotografías ni video.

## Qué se levanta

| Servicio | Qué hace | Acceso |
|----------|----------|--------|
| `db` | PostgreSQL 16 con los datos (volumen `emotv_pgdata`) | interno |
| `models` | Descarga y verifica los pesos (YuNet, FER+, pose) y mide el benchmark de FER+; luego termina | se ejecuta una vez |
| `api` | API FastAPI; aplica migraciones al arrancar | interno |
| `web` | Interfaz web (nginx) y proxy hacia la API y el WebSocket | http://localhost:8080 |
| `https` (opcional) | HTTPS para usar la cámara desde otras computadoras | https://IP:8443 |
| `flowise` (opcional) | Flowise local para el chatbot Emi | http://localhost:3000 |

## 1. Requisitos

- **Windows 10/11:** Docker Desktop con el motor WSL 2 (el instalador lo
  ofrece; acéptalo). Reinicia si te lo pide.
- **macOS o Linux:** Docker Desktop o Docker Engine con el plugin `compose`.
- Unos 4 GB libres en disco (la imagen de la API ocupa 1,4 GB).
- Memoria: ver [Consumo medido](#consumo-medido). Docker Desktop debe tener
  al menos 4 GB asignados.
- Git, para clonar el repositorio.

Comprueba la instalación en una terminal (PowerShell en Windows):

```powershell
docker --version
docker compose version
```

## 2. Clonar el repositorio

```powershell
git clone <url-del-repositorio> EMOtv
cd EMOtv
```

Todos los comandos siguientes se ejecutan desde la carpeta `EMOtv`.

### Red con inspección HTTPS (por ejemplo, la red de la UNHEVAL)

Si la construcción falla con `CERTIFICATE_VERIFY_FAILED` o
`self-signed certificate in certificate chain`, la red está inspeccionando
HTTPS. Coloca la CA de esa red en `docker/certs/` siguiendo
[docker/certs/README.md](../docker/certs/README.md) y vuelve a construir.
Fuera de esa red no hace falta.

## 3. Crear el archivo de configuración `.env.docker`

Este archivo guarda contraseñas generadas al azar y **no se sube al
repositorio**. Créalo una sola vez; el script nunca sobrescribe uno existente.

Con Python instalado:

```powershell
python scripts/docker/init_env.py
```

Sin Python (usa Docker):

```powershell
# PowerShell
docker run --rm -v "${PWD}:/work" -w /work python:3.12-alpine python scripts/docker/init_env.py
```

```bash
# Linux o macOS
docker run --rm -v "$PWD:/work" -w /work python:3.12-alpine python scripts/docker/init_env.py
```

Revisa el archivo con un editor. Los valores por defecto sirven para usar
EMOtv en esta misma computadora. Variables importantes:

- `ENVIRONMENT`: la API acepta `development`, `test` o `production`. Para
  demostraciones usa `development` con `CONSENT_MODE=demo`. `production` exige
  HTTPS en `CORS_ORIGINS` y `CONSENT_MODE=production` con una política
  institucional aprobada.
- `CONSENT_MODE`: `development` solo para pruebas del desarrollador sin otras
  personas; `demo` para voluntarios y la presentación; `production` exige una
  política institucional aprobada. El consentimiento no se desactiva para
  facilitar pruebas.
- `FLOWISE_API_URL` y `FLOWISE_API_KEY`: chatbot Emi (opcional).

> **Importante:** todos los comandos `docker compose` de esta guía llevan
> `--env-file .env.docker`. Sin él, Compose responde
> `required variable POSTGRES_PASSWORD is missing a value`. Para no repetirlo
> puedes definirlo una vez por terminal:
> `$env:COMPOSE_ENV_FILES = ".env.docker"` (PowerShell) o
> `export COMPOSE_ENV_FILES=.env.docker` (bash).

## 4. Levantar el sistema completo

```powershell
docker compose --env-file .env.docker up -d --build
```

La **primera vez** tarda varios minutos: construye las imágenes, descarga unos
41 MB de pesos y mide el benchmark de FER+ (unos 15 segundos). Las siguientes
veces arranca en segundos.

Comprueba el estado:

```powershell
docker compose --env-file .env.docker ps -a
```

Debe verse `db`, `api` y `web` como `healthy`, y `models` como `Exited (0)`.

## 5. Crear la primera cuenta de administración

```powershell
docker compose --env-file .env.docker exec api python scripts/security/create_admin.py --email admin@ejemplo.local
```

La terminal muestra una **contraseña temporal una sola vez**: cópiala ahora.
No se guarda en ningún archivo ni en los logs. Al iniciar sesión, EMOtv pedirá
cambiarla. Si ya existe un administrador activo, el script se niega a crear
otro (usa `--force` solo si de verdad necesitas una segunda cuenta).

Para crear cuentas de prueba de psicología y estudiante (solo pruebas
técnicas, nunca personas reales):

```powershell
docker compose --env-file .env.docker exec api python scripts/create_demo_role_accounts.py --create
```

## 6. Abrir la web y permitir la cámara

1. Abre http://localhost:8080 en Chrome, Edge o Firefox.
2. Inicia sesión con el administrador y cambia la contraseña.
3. Crea las cuentas desde **Usuarios**. Los voluntarios usan cuentas
   identificadas por código (`PRUEBA-NN`), nunca por su nombre.
4. Al entrar en **Análisis** con una cuenta de estudiante, el navegador pedirá
   permiso para la cámara: elige **Permitir**.

Los navegadores solo permiten la cámara en `localhost` o en HTTPS. Para usar
EMOtv desde **otra** computadora de la red, sigue el paso 7.

## 7. Usar la cámara desde otras computadoras de la red (HTTPS)

1. Averigua la IP de esta computadora (`ipconfig` en Windows; busca
   "Dirección IPv4", por ejemplo `192.168.1.50`).
2. Edita `.env.docker` con esa IP:

   ```
   EMOTV_LAN_HOST=192.168.1.50
   CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080,https://192.168.1.50:8443
   TRUSTED_HOSTS=localhost,127.0.0.1,api,192.168.1.50
   ```

3. Levanta con el perfil `https`:

   ```powershell
   docker compose --env-file .env.docker --profile https up -d
   ```

4. Desde la otra computadora abre `https://192.168.1.50:8443`.

El certificado lo emite una autoridad local de Caddy, por lo que **el
navegador mostrará una advertencia** ("La conexión no es privada"). Elige
"Configuración avanzada" → "Continuar". Hay que aceptarla una vez en cada
navegador. Si el Firewall de Windows pregunta, permite el acceso en redes
privadas. Si la IP cambia, repite los pasos 2 y 3.

## 8. Ver los logs

```powershell
docker compose --env-file .env.docker logs -f api
docker compose --env-file .env.docker logs -f web
```

`Ctrl+C` deja de seguir los logs (los servicios siguen funcionando).

## 9. Detener y volver a iniciar

```powershell
docker compose --env-file .env.docker down     # detiene; conserva datos
docker compose --env-file .env.docker up -d    # vuelve a iniciar
```

`down` conserva usuarios, sesiones y pesos descargados.

## 10. Respaldar y restaurar la base de datos

Requieren Python en el host (solo la biblioteca estándar) y los servicios en
ejecución. No hace falta PostgreSQL instalado.

```powershell
python scripts/docker/backup_db.py
# -> backups/emotv-AAAAMMDD-HHMMSS.dump

python scripts/docker/restore_db.py backups/emotv-20261005-164449.dump
```

La restauración **reemplaza toda la base actual**: pide escribir `RESTAURAR`,
detiene la API mientras restaura y la vuelve a iniciar. La carpeta `backups/`
no se sube al repositorio. Guarda los respaldos en un lugar seguro: contienen
datos personales.

## 11. Borrar todo, incluidos los datos

```powershell
docker compose --env-file .env.docker down -v
```

`-v` elimina los volúmenes: **se pierden usuarios, sesiones y pesos**. Úsalo
para empezar de cero o para eliminar los datos de voluntarios (como máximo 30
días después de cada prueba). La base nueva se crea con
`alembic upgrade head` al siguiente `up`.

## Modo solo base de datos (desarrollo local)

Para ejecutar la API y Vite en el host con PostgreSQL en Docker:

```powershell
docker compose -f docker-compose.yml -f docker-compose.db.yml up -d db
```

Este modo lee las variables del archivo `.env` local (no de `.env.docker`).
Agrega allí `POSTGRES_USER`, `POSTGRES_PASSWORD` y `POSTGRES_DB`, y apunta
`DATABASE_URL` al puerto publicado:

```
POSTGRES_USER=emotv
POSTGRES_PASSWORD=<contraseña-local>
POSTGRES_DB=emotv
DATABASE_URL=postgresql+psycopg://emotv:<contraseña-local>@localhost:5433/emotv
```

PostgreSQL se publica solo en `127.0.0.1`, en el puerto **5433** para no
chocar con un PostgreSQL instalado en Windows. Cámbialo con
`POSTGRES_HOST_PORT`. Luego `python -m alembic upgrade head` y sigue el
README.

## Chatbot con Flowise local (opcional)

Por defecto EMOtv usa el Flowise externo de `FLOWISE_API_URL`. Para uno local:

```powershell
docker compose --env-file .env.docker --profile chatbot up -d
```

Abre http://localhost:3000, crea el flujo y pon en `.env.docker`
`FLOWISE_API_URL=http://flowise:3000/api/v1/prediction/<id-del-flujo>`. Luego
reinicia la API: `docker compose --env-file .env.docker up -d api`.

## Consumo medido

Medido con `docker stats` en un equipo Windows 11 x86_64 con 5,6 GiB asignados
a Docker Desktop:

| Servicio | En reposo | Tras analizar 40 frames por WebSocket |
|----------|-----------|---------------------------------------|
| `api` | 195 MiB | 360 MiB |
| `db` | 44 MiB | 45 MiB |
| `web` | 13 MiB | 14 MiB |

Benchmark de FER+ en el contenedor: p95 de 18 a 25 ms por predicción. No se
midió con varias sesiones simultáneas.

## Problemas comunes

**`Bind for 127.0.0.1:8080 failed: port is already allocated`.** Otro programa
usa el puerto. Ciérralo o cambia la primera parte de `"8080:8080"` en
`docker-compose.yml` (por ejemplo `"8081:8080"`) y agrega ese origen a
`CORS_ORIGINS`. Para la base de datos usa `POSTGRES_HOST_PORT`.

**La cámara no se activa.** Fuera de `localhost` los navegadores exigen HTTPS:
usa el paso 7. Revisa también que el sitio tenga permiso de cámara (icono del
candado en la barra de direcciones) y que otra aplicación no la esté usando.

**El análisis no conecta desde otra computadora.** Revisa que la URL exacta
(`https://IP:8443`) esté en `CORS_ORIGINS` y la IP en `TRUSTED_HOSTS`; luego
`docker compose --env-file .env.docker --profile https up -d`.

**"Modelo bloqueado: Benchmark vencido".** El benchmark de FER+ tiene una
vigencia de 30 días. Vuelve a medirlo con
`docker compose --env-file .env.docker up -d models`, que se ejecuta y termina
solo.

**`models` termina con `Exited (1)`.** No pudo descargar algún peso (sin
internet o red con inspección HTTPS). Revisa
`docker compose --env-file .env.docker logs models`, corrige y vuelve a
ejecutar `up -d`. Los pesos ya descargados no se vuelven a descargar.

**La API se reinicia o el sistema va lento.** Falta memoria. En Docker
Desktop → Settings → Resources asigna al menos 4 GB y cierra otros programas.

**La primera construcción tarda mucho.** Es normal: descarga imágenes base,
dependencias de Python (OpenCV, MediaPipe, ONNX Runtime) y los pesos. Las
siguientes construcciones reutilizan la caché.

**Apple Silicon (M1/M2/M3).** Las imágenes se construyen para la arquitectura
del equipo. MediaPipe, ONNX Runtime y OpenCV publican ruedas para
`linux/arm64`, pero esa combinación no se probó. Si la construcción o el
arranque fallan, fuerza amd64 (más lento, con emulación):
`$env:DOCKER_DEFAULT_PLATFORM = "linux/amd64"` o
`export DOCKER_DEFAULT_PLATFORM=linux/amd64` antes de `up --build`.

**`/bin/sh^M: bad interpreter` en la API.** El entrypoint perdió el fin de
línea LF. `.gitattributes` lo evita al clonar; si editaste el archivo en
Windows, vuelve a obtenerlo con `git checkout -- docker/api-entrypoint.sh`.
