# Cronología de desarrollo

Extraída de `git log` de la rama `main` y de las ramas de trabajo hasta el
commit `5c11845` (10 de octubre de 2026), con:

```bash
git log --reverse --date=short --no-merges --format="%ad|%h|%s"
```

Se omiten los commits de fusión (*merge*); el texto de cada cambio es el
mensaje del commit, sin editar. Los primeros commits usan mensajes libres; desde
septiembre siguen prefijos convencionales (`feat:`, `fix:`, `chore:`, …).

| Fecha | Commit | Cambio |
| --- | --- | --- |
| 2026-08-19 | `c0491fe` | first commit |
| 2026-08-24 | `23c2eb4` | prueba facial + camara |
| 2026-08-24 | `cd03033` | mejoras en la prueba |
| 2026-08-26 | `308b75c` | reconocimiento |
| 2026-09-01 | `ef927b8` | web + camara IA optimizado |
| 2026-09-04 | `4c4ba9e` | feat: implementar deteccion de pose y ejercicios corporales |
| 2026-09-07 | `c418f38` | feat: integrar emociones con actividades y ejercicios |
| 2026-09-07 | `b839b5e` | feat: agregar sesiones y persistencia en memoria |
| 2026-09-08 | `4076f38` | feat: agrega API de sesiones, identidad y actividades |
| 2026-09-15 | `8c00d0a` | feat: integrar frontend, API administrativa y modelo FER+ predeterminado |
| 2026-09-16 | `e0ac82a` | feat: agregar selector de modelos faciales con admisión por recursos |
| 2026-09-16 | `de5a525` | limpieza de referencias residuales |
| 2026-09-18 | `d469d6e` | feat: incorpora primer acceso y consentimiento estudiantil |
| 2026-09-21 | `60c2570` | feat: actividades secuenciales y opción para repetir el análisis facial |
| 2026-09-21 | `3d9a498` | chore: ignorar archivos tsbuildinfo |
| 2026-09-21 | `ecbd932` | validadores de posturas |
| 2026-09-23 | `ff04ffd` | feat: recomendar actividades secuenciales y mostrar sus pasos |
| 2026-09-29 | `56be0b4` | integracion del chatbot |
| 2026-09-30 | `ad204b6` | Delete .tmp_check_login.py |
| 2026-10-05 | `e33abc6` | exclusion del contexto claude |
| 2026-10-05 | `8045f88` | feat: despliegue con Docker Compose para base de datos y sistema completo |
| 2026-10-06 | `33bbc30` | docs: política de consentimiento demo v0.2 alineada con las pruebas funcionales |
| 2026-10-06 | `9798c7a` | fix: detector de secretos, hook de pre-commit y reseteo seguro de admin |
| 2026-10-06 | `af89c9d` | feat: limitar intentos de login y reforzar política de contraseñas |
| 2026-10-06 | `7ad4dc3` | feat: asignación de estudiantes a psicólogos y autorización por asignación |
| 2026-10-07 | `aa89e59` | chore: ignorar CLAUDE.md con el nombre exacto |
| 2026-10-07 | `2cc1fe8` | refactor: retirar cámara de servidor y unificar descarga de modelos |
| 2026-10-07 | `4f64106` | chore: ignorar el directorio temporal de pytest |
| 2026-10-08 | `6c2c940` | feat: análisis en vivo con registro elegido por el estudiante y persistencia independiente |
| 2026-10-08 | `9f3bb7b` | feat: catálogo informativo de expresiones y pantalla de resultado educativa |
| 2026-10-09 | `2f59aa0` | feat: recomendaciones configurables en base de datos y recomendador tolerante |
| 2026-10-09 | `91e29d1` | fix: verificación estricta de pasos y repeticiones en actividades secuenciales |
| 2026-10-09 | `5d5bb44` | chore: ignorar configuración local de Claude Code |
| 2026-10-09 | `f458233` | feat: chatbot Emi con n8n, conversaciones y límites de uso |
| 2026-10-09 | `aa88fdc` | feat: conocimiento controlado de EMOtv y evaluación de Emi |
| 2026-10-09 | `8d0ead9` | feat: cuentas de voluntarios y eliminación verificable de datos de prueba |
| 2026-10-09 | `06487c7` | refactor: identidad visual con tokens de diseño en toda la interfaz |
| 2026-10-09 | `2a4306e` | chore: ignorar DESIGN.md |
| 2026-10-10 | `1850803` | feat: estructura con barras fijas y componentes base según DESIGN.md |
| 2026-10-10 | `54d1ad1` | feat: contenido de Inicio, Analizador, Actividades, Consentimiento y Sesiones según DESIGN.md |
| 2026-10-10 | `315db5f` | feat: mejoras de experiencia de uso en el recorrido completo |
| 2026-10-10 | `5c11845` | test: pruebas de extremo a extremo del recorrido principal |

## Resumen por periodo

| Periodo | Commits | Hitos |
| --- | --- | --- |
| Agosto 2026 | 4 | prototipo de detección facial con cámara y reconocimiento de expresiones |
| Septiembre 2026 | 15 | pose y ejercicios corporales, sesiones, API con PostgreSQL, frontend React, FER+ predeterminado, admisión de modelos, primer acceso, consentimiento, actividades secuenciales, primer chatbot |
| Octubre 2026 (1-10) | 23 | Docker Compose, seguridad (secretos, límite de intentos), asignaciones de Psicología, análisis en vivo, catálogo de expresiones, recomendaciones configurables, Emi con n8n, cuentas de voluntarios, identidad visual, interfaz según DESIGN.md, pruebas e2e y auditoría |

El commit de esta auditoría (`chore: auditoría final y preparación de la
versión 1.0.0`) es posterior a la tabla.
