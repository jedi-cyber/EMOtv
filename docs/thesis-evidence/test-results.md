# Resultados de pruebas

Ejecución del **10 de octubre de 2026** sobre la rama `chore/version-1.0.0`
(a partir de `5c11845`), en el equipo de desarrollo: Windows 11, Docker
Desktop, Python 3.12, Node 24 y Chrome instalado. Son resultados reales de esa
ejecución. Las cifras cambian con el código: vuelve a ejecutar los comandos
antes de citarlas.

## Resumen

| Verificación | Comando | Resultado |
| --- | --- | --- |
| Detector de secretos | `python scripts/security/check_secrets.py --all` | sin hallazgos en 400 archivos versionados |
| Pruebas del backend | `python -m pytest -q` (PostgreSQL 16 desechable con `alembic upgrade head`) | 503 pasan, 1 falla por el entorno, 3 omitidas |
| Tipos del frontend | `npx tsc -b` | sin errores |
| Pruebas del frontend | `npx vitest run` | 139 pasan en 18 archivos |
| Build de producción | `npm run build` | correcto (JS 438 kB, 135 kB gzip) |
| Imágenes Docker | `docker compose --env-file .env.docker build` | correcto; `pip check` sin conflictos y la imagen coincide con `requirements.lock` |
| Stack con healthchecks | `docker compose --env-file .env.docker up -d` | `api`, `web` y `db` *healthy*; `/health` responde `database`, `face_detector` y `emotion_model` en `ok` |
| Pruebas e2e | `bash scripts/e2e/run_isolated.sh` (Chrome, stack aislado) | 8 pasan, 3 omitidas por falta de imágenes de rostro (más las 2 de capturas, que se activan aparte) |

## Detalle

**pytest.** La falla es
`tests/unit/test_check_secrets.py::test_project_repository_is_clean`: la
prueba lanza `python` como subproceso y en este entorno de ejecución eso
termina con `OSError: [WinError 87]`. El mismo detector, ejecutado
directamente, no encuentra hallazgos. Omitidas: dos pruebas del hook de
pre-commit que requieren `sh` y `python3` de POSIX (no disponibles en Windows)
y la del modelo experimental HardlyHumans, porque `torch` no está instalado
(extra opcional `emotion-vit`). Las pruebas con los pesos reales
(`tests/integration/test_real_model_weights.py`) pasan: verifican los hashes,
la carga de YuNet, FER+ y MediaPipe y que un frame sin persona no produce
resultado.

**e2e.** Pasan: inicio de sesión correcto e incorrecto, bloqueo por intentos,
primer acceso, aceptación y revocación del consentimiento, cámara simulada en
el analizador, Psicología sin y con asignación, y Emi con el n8n falso (dentro
y fuera del alcance, y 502). Omitidas: resultado del análisis, finalizar sin
actividad con historial, y actividad que no avanza sin persona. Las tres
necesitan imágenes de rostro propias o con licencia, que el repositorio no
incluye. El Chromium que descarga Playwright no arranca en este equipo, así
que se usó el Chrome instalado (`E2E_BROWSER_CHANNEL=chrome`).

## Pruebas con voluntarios

**No hay resultados registrados.** A la fecha no se ha completado ninguna
fila de [manual-checklist.md](../testing/manual-checklist.md) ni existen actas
de pruebas con voluntarios en el repositorio. Cuando se hagan, este documento
solo incluirá **resultados agregados y anónimos** (por ejemplo, «4 de 5
participantes completaron la secuencia»), sin códigos `PRUEBA-NN`, nombres,
fechas individuales ni ningún dato que permita identificar a alguien.

## Benchmark del modelo facial

Ver [benchmark-ferplus.md](benchmark-ferplus.md): medición de rendimiento en
el equipo evaluado, no una garantía.
