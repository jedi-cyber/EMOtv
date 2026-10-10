# Pruebas de extremo a extremo (Playwright)

Las pruebas e2e recorren EMOtv en un navegador real: inicio de sesión, primer
acceso, consentimiento, analizador, historial, Psicología y Emi. Están en
`web/e2e/` y usan Playwright con Chromium y una cámara simulada.

Lo que necesita una cámara y personas reales no se automatiza: está en
[manual-checklist.md](manual-checklist.md).

## Qué cubren

| Archivo | Pruebas |
| --- | --- |
| `auth.spec.ts` | inicio de sesión correcto e incorrecto; bloqueo tras el límite de intentos; primer acceso con cambio de contraseña |
| `consent.spec.ts` | aceptar la política vigente desde el modal y revocar el consentimiento |
| `analysis.spec.ts` | la cámara simulada abre en el analizador; resultado con expresión en español, confianza, información y limitación; finalizar sin actividad y verla en el historial; la actividad no avanza con un video sin persona |
| `psychologist.spec.ts` | Psicología no ve a un estudiante sin asignación (interfaz y API) y sí lo ve después de asignarlo |
| `emi.spec.ts` | Emi con un n8n falso: respuesta dentro del alcance, fuera del alcance y error 502 `llm_unavailable` |
| `screenshots.spec.ts` | capturas de cada vista para `docs/thesis-evidence/screenshots/`; solo con `E2E_SCREENSHOTS=1` |

Cada prueba crea sus propias cuentas (`e2e-…@emotv.local`, códigos `E2E-…`)
con la API de administración. Por eso **nunca se ejecutan contra una base con
datos de voluntarios**: usa el stack aislado.

## Forma recomendada: stack aislado

`docker-compose.e2e.yml` levanta un proyecto aparte (`emotv-e2e`) con su
propia base de datos (`emotv_e2e_pgdata`) en `http://localhost:8081`. Reutiliza
los pesos ya descargados y apunta Emi al n8n falso de las pruebas.

```bash
# Desde la raíz, en Git Bash o Linux. Usa los valores de .env.docker.
cd web && npm ci && npx playwright install chromium && cd ..
python scripts/e2e/make_fake_video.py            # ver «Cámara simulada»
bash scripts/e2e/run_isolated.sh                 # todas las pruebas
bash scripts/e2e/run_isolated.sh e2e/auth.spec.ts
```

`run_isolated.sh` levanta el stack, genera una contraseña nueva para la cuenta
`e2e-admin@emotv.local` (la crea si no existe) y lanza Playwright. La
contraseña solo vive en variables del proceso: no se guarda en archivos ni se
muestra. Variables útiles:

| Variable | Uso |
| --- | --- |
| `E2E_ENV_FILE` | archivo de entorno de Compose (por defecto `.env.docker`) |
| `E2E_WEB_PORT` | puerto del stack aislado (por defecto 8081) |
| `E2E_SKIP_UP=1` | no reconstruye el stack; usa el que ya está levantado |
| `E2E_BROWSER_CHANNEL` | `chrome` o `msedge` para usar el navegador instalado si el Chromium de Playwright no arranca en tu equipo |

Para borrar el stack de pruebas y su base:

```bash
docker compose -p emotv-e2e --env-file .env.docker -f docker-compose.yml -f docker-compose.e2e.yml down -v
```

`down -v` borra solo los volúmenes de ese proyecto (`emotv_e2e_pgdata`); los
pesos (`emotv_models`) los usa también el stack principal y se conservan.

## Otra forma: backend y frontend locales

```bash
cd web
E2E_BASE_URL=http://localhost:5173 \
E2E_ADMIN_EMAIL=<correo de administración> \
E2E_ADMIN_PASSWORD=<su contraseña> \
npx playwright test
```

Define las variables en la terminal; no las guardes en archivos del
repositorio. La cuenta debe haber cambiado ya su contraseña provisional y la
base debe ser de pruebas.

- Con el límite por defecto (`LOGIN_MAX_FAILURES_PER_IP=20` en 15 minutos),
  dos o tres ejecuciones seguidas pueden bloquear tu IP, porque cada ejecución
  falla a propósito unas siete veces. Sube ese valor en el `.env` de pruebas o
  espera la ventana. Si cambias `LOGIN_MAX_FAILURES_PER_ACCOUNT`, define el
  mismo valor en `E2E_LOGIN_MAX_FAILURES`.
- Emi solo se prueba con `E2E_FAKE_N8N=1` y el backend arrancado con
  `N8N_WEBHOOK_URL=http://localhost:5679/webhook/emi-chat` y cualquier
  `N8N_WEBHOOK_KEY` de prueba. Sin eso, la prueba se marca como omitida.

## Cámara simulada

Chromium arranca con `--use-fake-ui-for-media-stream`,
`--use-fake-device-for-media-stream` y `--use-file-for-fake-video-capture`
apuntando a `web/e2e/fixtures/generated/camera.y4m`.
`scripts/e2e/make_fake_video.py` genera ese video en dos tramos que se repiten
en bucle:

1. **Rostro:** cada imagen de `web/e2e/fixtures/faces/` durante 12 s.
2. **Sin persona:** un fondo neutro durante 45 s.

Qué imágenes usar (propias o con licencia, nunca de voluntarios ni del
personal de la UNHEVAL) está en
[web/e2e/fixtures/README.md](../../web/e2e/fixtures/README.md). Sin imágenes,
el script genera solo el tramo sin persona y las tres pruebas que necesitan un
rostro se marcan como omitidas. Ni las imágenes ni el video se suben al
repositorio.

La prueba de la actividad registra la expresión durante el tramo con rostro y
espera al tramo sin persona. Comprueba que el servidor avisa que no ve a nadie
y que el paso y el progreso no avanzan. **Completar una actividad no se
automatiza:** una imagen fija no puede adoptar posturas y un video grabado
para eso no sería fiable. Esa verificación está en la lista manual.

## Emi con n8n simulado

`web/e2e/support/fakeN8n.ts` levanta, dentro de la prueba, un servidor con el
contrato del workflow "Version 1.0 EMI":

- `POST /webhook/emi-chat` con `X-EMOtv-Key` y
  `{request_id, question, history, knowledge}`;
- `200 {answer, in_scope, category, request_id}`;
- `502 {error: "llm_unavailable", answer, request_id}`;
- `403` si falta la clave (o si no coincide con `E2E_FAKE_N8N_KEY`, cuando se
  define).

La palabra «receta» en la pregunta produce una respuesta fuera de alcance y
«falla-llm» produce el 502. La prueba también comprueba que ni el correo ni el
código del estudiante viajan al workflow. Escucha en `0.0.0.0:5679`
(`E2E_FAKE_N8N_PORT`); el contenedor de la API llega por
`host.docker.internal`.

## Integración continua

- `.github/workflows/tests.yml`: pytest (con PostgreSQL de servicio y las
  migraciones aplicadas), `tsc -b` y `vitest` en cada push.
- `.github/workflows/e2e.yml`: solo ejecución manual (`workflow_dispatch`).
  Genera una configuración efímera, levanta el stack aislado y publica el
  informe de Playwright como artefacto. En CI no hay imágenes de rostro, así
  que las pruebas de análisis con rostro se omiten.
