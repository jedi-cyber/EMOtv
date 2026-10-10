# Evidencia para la tesis

Material verificable de EMOtv para la tesis. Todo se generó a partir del
repositorio, sin datos personales reales.

| Documento | Contenido |
| --- | --- |
| [chronology.md](chronology.md) | cronología real de desarrollo extraída de `git log` (fecha, commit, cambio) |
| [test-results.md](test-results.md) | resultados de las pruebas del 10 de octubre de 2026, con fecha y comandos |
| [benchmark-ferplus.md](benchmark-ferplus.md) | benchmark de FER+ como medición en el entorno evaluado, no como garantía |
| [screenshots/](screenshots/) | 18 capturas de cada vista, generadas con Playwright con cuentas ficticias |
| [diagrams/](diagrams/) | arquitectura, flujo del estudiante y modelo de datos en HTML imprimible sin conexión |

Los diagramas de texto equivalentes están en
[docs/architecture.md](../architecture.md) y
[docs/data-model.md](../data-model.md). Si un diagrama visual y su versión
Mermaid difieren, la fuente de verdad son las migraciones y el código.

## Criterios de aceptación

Revisión del 10 de octubre de 2026. **Cumplido**: implementado y verificado con
la evidencia indicada. **Parcial**: implementado, pero falta una verificación
que la versión exige. **Pendiente**: no verificado.

| # | Criterio | Estado | Evidencia |
| --- | --- | --- | --- |
| 1 | Aplicación web | Cumplido | React + Vite (`web/`) y FastAPI (`src/emotv/`); `npm run build` correcto; `docker compose up` con `api`, `web` y `db` *healthy*; 8 pruebas e2e pasan contra el stack |
| 2 | Login seguro | Cumplido | argon2 y JWT con `token_version` (`application/authentication_service.py`); límite de intentos (`application/login_throttle.py`); primer acceso obligatorio; `e2e/auth.spec.ts` (4 pruebas); `tests/unit/test_login_hardening.py`, `tests/integration/test_authentication_api.py` |
| 3 | Visión facial | Parcial | YuNet + FER+ ONNX cargan con los pesos reales (`tests/integration/test_real_model_weights.py`, `/health` → `face_detector` y `emotion_model` en `ok`). **Falta** verificar la estimación con un rostro: las pruebas e2e con rostro se omiten sin imágenes y la lista manual está sin ejecutar |
| 4 | Resultado emocional | Parcial | Expresión en español, confianza, información y limitación (`expressions/ExpressionResult.tsx`; `tests/adaptive_analysis.test.tsx`, `tests/session_outcome.test.tsx`). **Falta** la prueba e2e `analysis.spec.ts` con un rostro real o con licencia |
| 5 | Recomendación de 2 o más posturas | Cumplido | `application/recommendation_config_service.py` y `interfaces/web/activity_router.py` rechazan actividades de un paso; `tests/integration/test_recommendations_api.py`, `tests/unit/test_activity_recommendation_service.py`, `web/tests/admin_recommendations.test.tsx` |
| 6 | Visión corporal | Cumplido | MediaPipe Pose y `PostureValidator` para las cinco posturas; `tests/unit/test_multiple_postures.py`, `test_posture_models.py`, `test_pose_detector.py`. La verificación con personas está en el criterio 11 |
| 7 | Secuencia | Cumplido | pasos y repeticiones verificados uno a uno (`application/browser_activity_service.py`); `tests/unit/test_new_sequence_postures.py`, `tests/integration/test_browser_activity_api.py` |
| 8 | Persistencia | Cumplido | PostgreSQL + 16 migraciones Alembic ([data-model.md](../data-model.md)); pruebas de integración contra PostgreSQL 16 dentro de los 503 casos que pasan |
| 9 | Chatbot | Parcial | Emi: límites, filtro de riesgo e historial (`application/chat_service.py`; `tests/unit/test_emi_chat.py`); contrato del webhook probado con el n8n falso (`e2e/emi.spec.ts`: dentro y fuera de alcance, 502). **Falta** una conversación contra el workflow publicado en esta revisión (lista manual) |
| 10 | Seguridad y privacidad | Cumplido | detector de secretos sin hallazgos; permisos aplicados en FastAPI (`e2e/psychologist.spec.ts` comprueba el 403); consentimiento por modos; frames solo en memoria; eliminación verificable de voluntarios (`tests/unit/test_volunteer_test_data.py`); [privacy-data-governance.md](../privacy-data-governance.md) |
| 11 | Prueba completa | Pendiente | El recorrido completo con cámara y una persona real (análisis, actividad completa, historial y Emi) no se ha ejecutado: [manual-checklist.md](../testing/manual-checklist.md) está vacío |

### Qué falta para etiquetar `v1.0.0`

La etiqueta `v1.0.0` **no se creó**: los criterios 3, 4, 9 y 11 no están
cumplidos. Para cerrarlos:

1. Agregar imágenes de rostro propias o con licencia en
   `web/e2e/fixtures/faces/`, generar el video y lograr que pasen las tres
   pruebas de `e2e/analysis.spec.ts` (criterios 3 y 4).
2. Completar [manual-checklist.md](../testing/manual-checklist.md) con
   voluntarios según el [protocolo](../testing/volunteer-protocol.md):
   iluminación, distancias, las cinco posturas, una secuencia completa y
   conexión por HTTPS (criterios 3, 4 y 11).
3. Mantener una conversación con Emi contra el workflow publicado y anotarla
   en la lista manual (criterio 9).
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
| `03-inicio-sin-consentimiento.png` | inicio del estudiante sin consentimiento |
| `04-consentimiento.png`, `05-consentimiento-modal.png` | consentimiento y lectura de la política |
| `06-analizador-requisitos.png`, `07-analizador-camara-simulada.png` | analizador con guía previa y requisitos |
| `08-inicio-primeros-pasos.png` | inicio con los tres pasos del recorrido |
| `09-actividades.png`, `10-actividad-pasos.png` | actividades y pasos de una actividad |
| `11-mis-sesiones-vacio.png` | historial vacío |
| `12-emi.png` | Emi (respuesta del n8n falso) |
| `13-analizador-360px.png` | analizador en pantalla de 360 px |
| `14-psicologia-estudiantes.png`, `15-psicologia-sesiones-del-estudiante.png` | vistas de Psicología |
| `16-admin-usuarios.png`, `17-admin-actividades.png`, `18-admin-expresiones.png` | vistas de administración |

## Diagramas visuales

`diagrams/arquitectura.html`, `diagrams/flujo-estudiante.html` y
`diagrams/modelo-datos.html` usan los colores y la tipografía de `DESIGN.md`.
La fuente va incrustada en cada archivo: se abren sin conexión y se exportan a
PDF desde el diálogo de impresión del navegador (A4 horizontal) o a imagen con
una captura.
