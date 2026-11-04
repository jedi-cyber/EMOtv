# Evidencia para la tesis

Material verificable de EMOtv para la tesis. Todo se generó a partir del
repositorio, sin datos personales reales.

| Documento | Contenido |
| --- | --- |
| [chronology.md](chronology.md) | cronología real de desarrollo extraída de `git log` (fecha, commit, cambio) |
| [test-results.md](test-results.md) | resultados de las pruebas del 10 de octubre de 2026, con fecha y comandos |
| [benchmark-ferplus.md](benchmark-ferplus.md) | benchmark de FER+ como medición en el entorno evaluado, no como garantía |
| [screenshots/](screenshots/) | 29 capturas de cada vista, generadas con Playwright con cuentas ficticias |
| [diagrams/](diagrams/) | arquitectura, flujo del estudiante y modelo de datos en HTML imprimible sin conexión |

Los diagramas de texto equivalentes están en
[docs/architecture.md](../architecture.md) y
[docs/data-model.md](../data-model.md). Si un diagrama visual y su versión
Mermaid difieren, la fuente de verdad son las migraciones y el código.

## Criterios de aceptación

Revisión del 4 de noviembre de 2026 (commit `42d367d`). **Cumplido**:
implementado y verificado con la evidencia indicada. **Parcial**: implementado,
pero falta una verificación que la versión exige. **Pendiente**: no verificado.
Las cifras de pruebas están en [test-results.md](test-results.md).

| # | Criterio | Estado | Evidencia |
| --- | --- | --- | --- |
| 1 | Aplicación web | Cumplido | React + Vite (`web/`) y FastAPI (`src/emotv/`); `docker compose up` con `api`, `web` y `db` *healthy* |
| 2 | Login seguro | Cumplido | argon2 y JWT con `token_version` (`application/authentication_service.py`); límite de intentos (`application/login_throttle.py`); primer acceso obligatorio; `e2e/auth.spec.ts`; `tests/unit/test_login_hardening.py`, `tests/integration/test_authentication_api.py` |
| 3 | Visión facial | Parcial | YuNet + HSEmotion (principal) y FER+ (respaldo) cargan con los pesos reales (`tests/integration/test_real_model_weights.py`, `/health`). **Falta** verificar la estimación con un rostro: las pruebas e2e con rostro se omiten sin imágenes y la [lista manual](../testing/manual-checklist.md) está sin ejecutar |
| 4 | Resultado emocional | Parcial | Expresión estimada en español, confianza, información y limitación (`expressions/ExpressionResult.tsx`; `web/tests/adaptive_analysis.test.tsx`, `web/tests/session_outcome.test.tsx`). **Falta** `e2e/analysis.spec.ts` con un rostro propio o con licencia, o la sección 1 de la lista manual |
| 5 | Recomendación de 2 o más posturas | Cumplido | `application/recommendation_config_service.py` y `interfaces/web/activity_router.py` rechazan actividades de un paso; `tests/integration/test_recommendations_api.py`, `tests/unit/test_activity_recommendation_service.py` |
| 6 | Visión corporal | Cumplido | MediaPipe Pose y `PostureValidator` para las cinco posturas; `tests/unit/test_multiple_postures.py`, `test_posture_models.py`, `test_pose_detector.py` |
| 7 | Secuencia | Cumplido | pasos y repeticiones verificados uno a uno (`application/browser_activity_service.py`); `tests/unit/test_new_sequence_postures.py`, `tests/integration/test_browser_activity_api.py`, `tests/integration/test_activities_freeze.py` |
| 8 | Persistencia | Cumplido | PostgreSQL + 35 migraciones Alembic, la última `20261104_35_imitation_steps` ([data-model.md](../data-model.md)); cada migración nueva tiene su prueba de ida y vuelta |
| 9 | Chatbot | Parcial | Emi para usuarios y docentes: límites, filtros de riesgo e identificadores, historial, conocimiento con la guía de uso (`application/chat_service.py`, `application/emi_knowledge.py`; `tests/unit/test_emi_chat.py`, `tests/unit/test_emi_knowledge.py`). **Falta** una conversación contra el workflow publicado en Sim (sección 6 de la lista manual) |
| 10 | Seguridad y privacidad | Cumplido | detector de secretos sin hallazgos; permisos aplicados en FastAPI; consentimiento por modos; frames solo en memoria; eliminación verificable de voluntarios (`tests/unit/test_volunteer_test_data.py`); [privacy-data-governance.md](../privacy-data-governance.md) |
| 11 | Prueba completa | Pendiente | El recorrido con cámara y personas reales no se ha ejecutado: [manual-checklist.md](../testing/manual-checklist.md) (secciones 1 a 6) está vacía |
| 12 | Cuentas y permisos | Cumplido | cuatro papeles, un docente por usuario, administración sin acceso a contenidos y `can_access_session` (`tests/integration/test_privacy_accounts.py`, `tests/integration/test_docente_supervision.py`); [matriz-de-accesos.md](../privacy/matriz-de-accesos.md) |
| 13 | Sesiones con autorización confirmada | Cumplido | sin confirmación no hay sesión; aviso reforzado para niños; código aleatorio al empezar y al terminar (`tests/integration/test_privacy_accounts.py`: `test_no_session_starts_without_the_confirmation`, `test_the_first_session_with_a_child_requires_the_reinforced_notice`, `test_the_session_code_is_random_and_unique`) |
| 14 | Cuestionarios | Cumplido | constructor, plantilla inicial y respuestas registradas sin puntajes (`tests/integration/test_questionnaires.py`, `web/tests/questionnaires.test.tsx`) |
| 15 | Protocolos e imágenes con revisión del docente | Cumplido | protocolos versionados para adultos o niños, plantillas, banco inicial y «Haz la misma cara»; imágenes de usuarios con detección de personas y aprobación del docente (`tests/integration/test_protocols_and_stimuli.py`, `test_protocol_templates.py`, `test_initial_bank.py`, `test_imitation_steps.py`, `test_recognition_sessions.py`) |
| 16 | Sesión con línea de tiempo y reporte | Cumplido en código | sesión guiada, línea de tiempo, métricas descriptivas y reporte con revisión del docente («Por revisar») (`tests/integration/test_guided_sessions.py`, `test_session_insights.py`, `test_session_reports.py`, `test_docente_supervision.py`). La sesión con una persona real es parte del criterio 11 |
| 17 | Estadísticas agregadas | Cumplido | cuentan sesiones, nunca personas; las demostraciones del docente no cuentan (`tests/integration/test_session_statistics.py`, `test_practice_statistics.py`) |
| 18 | Documentación de privacidad | Cumplido | [docs/privacy/](../privacy/README.md): política, registro de tratamiento, matriz de accesos, compromiso de confidencialidad, formato de consentimiento, procedimientos de derechos e incidentes, y guía de uso responsable de datos |

Los criterios 5, 6 y 7 se cumplen en el código y sus pruebas, pero el módulo de
actividades corporales está congelado y oculto (`ACTIVITIES_ENABLED=false`)
porque no forma parte del objetivo. Para mostrarlo se arranca la API con
`ACTIVITIES_ENABLED=true` y se cambia `ACTIVITIES_ENABLED` en
`web/src/routes/features.ts` (anexo de la lista manual). El examen simulado y
las imágenes abstractas también están congelados y no son criterios.

### Qué falta para etiquetar `v1.0.0`

La etiqueta `v1.0.0` **no se creó**: los criterios 3, 4, 9 y 11 no están
cumplidos, y el 16 espera la sesión con una persona real. Ninguno se cierra
con más código, sino con pruebas. Para cerrarlos:

1. Completar [manual-checklist.md](../testing/manual-checklist.md) con
   voluntarios adultos según el [protocolo](../testing/volunteer-protocol.md):
   cámara, luz y distancia; «Validación con adultos» con los dos modelos;
   una sesión con protocolo; la supervisión del docente; navegadores y
   HTTPS (criterios 3, 4, 11 y 16).
2. Pegar la descripción vigente en el workflow de Sim, mantener una
   conversación con Emi y anotarla en la sección 6 (criterio 9).
3. Opcional, para el criterio 4: agregar imágenes de rostro propias o con
   licencia en `web/e2e/fixtures/faces/` y lograr que pase
   `e2e/analysis.spec.ts`.
4. Registrar en [test-results.md](test-results.md) solo los resultados
   agregados y anónimos, y crear la etiqueta.

## Capturas

`web/e2e/screenshots.spec.ts` regenera las capturas contra el stack aislado:

```bash
E2E_SCREENSHOTS=1 bash scripts/e2e/run_isolated.sh e2e/screenshots.spec.ts
```

Usan cuentas ficticias (`e2e-…@emotv.local`, códigos `E2E-…`) y la cámara
simulada sin persona. No incluyen el resultado de una expresión, porque eso
requiere un rostro; esa vista se capturará cuando existan imágenes con
licencia.

| Archivo | Vista |
| --- | --- |
| `01-login.png` | inicio de sesión |
| `02-primer-acceso.png` | cambio de la contraseña provisional |
| `03-inicio-sin-consentimiento.png` | inicio del usuario sin consentimiento |
| `04-consentimiento.png`, `05-consentimiento-modal.png` | consentimiento y lectura de la política |
| `06-analizador-requisitos.png`, `07-analizador-camara-simulada.png` | analizador con guía previa y requisitos |
| `08-inicio-primeros-pasos.png` | inicio con los tres pasos del recorrido |
| `09-actividades.png`, `10-actividad-pasos.png` | actividades y pasos de una actividad |
| `11-mis-sesiones-vacio.png` | historial vacío |
| `12-emi.png` | Emi (respuesta del n8n falso) |
| `13-analizador-360px.png` | analizador en pantalla de 360 px |
| `14-psicologia-estudiantes.png`, `15-psicologia-sesiones-del-estudiante.png` | grupo del docente y sesiones de su grupo |
| `16-admin-usuarios.png` | cuentas y grupos (administrador de la Facultad) |
| `17-admin-actividades.png`, `18-admin-expresiones.png` | actividades y expresiones (superadministrador) |
| `19-mis-sesiones-con-codigo.png`, `20-sesion-detalle.png` | sesiones identificadas solo por su código y detalle de una sesión |
| `21-estadisticas.png` | estadísticas agregadas con gráfico de barras (cuentan sesiones, no personas) |
| `22-cuestionarios.png`, `23-protocolos.png`, `24-imagenes-propias.png` | material del usuario: cuestionarios, protocolos e imágenes propias |
| `25-analizador-con-quien.png` | analizador con la pregunta «¿Con quién es la sesión?» |
| `26-docente-imagenes-por-revisar.png` | imágenes de los usuarios que esperan la revisión del docente |
| `28-docente-estadisticas-grupo.png` | estadísticas del grupo del docente |
| `29-compromiso-confidencialidad.png` | compromiso de confidencialidad antes de iniciar sesiones |

## Diagramas visuales

`diagrams/arquitectura.html`, `diagrams/flujo-estudiante.html` y
`diagrams/modelo-datos.html` usan los colores y la tipografía de `DESIGN.md`.
La fuente va incrustada en cada archivo: se abren sin conexión y se exportan a
PDF desde el diálogo de impresión del navegador (A4 horizontal) o a imagen con
una captura.
