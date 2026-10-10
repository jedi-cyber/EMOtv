# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
El repositorio no tenía etiquetas de versión: las versiones anteriores a
1.0.0 agrupan el historial real de commits por hitos, con la fecha del último
commit de cada grupo. La cronología commit por commit está en
[docs/thesis-evidence/chronology.md](docs/thesis-evidence/chronology.md).

## [1.0.0-rc.1] - 2026-10-10

Candidata a 1.0.0. La etiqueta `v1.0.0` se creará cuando se cumplan todos los
[criterios de aceptación](docs/thesis-evidence/README.md#criterios-de-aceptación).

### Añadido
- Pruebas de extremo a extremo con Playwright, cámara simulada, n8n falso y un
  stack de Docker aislado (`5c11845`).
- Lista de pruebas manuales con cámara y voluntarios, workflow de CI para
  pytest y vitest en cada push, y e2e manual (`5c11845`).
- Estructura con barras fijas y componentes base según `DESIGN.md`
  (`1850803`); contenido de Inicio, Analizador, Actividades, Consentimiento y
  Sesiones (`54d1ad1`).
- Guía previa al análisis, mensajes específicos para cada error de cámara y
  estados de carga, vacío, error y sin permiso (`315db5f`).
- `requirements.lock` con las versiones exactas de la imagen de la API;
  documentación de arquitectura, modelo de datos y evidencia para la tesis.

### Cambiado
- Los textos visibles no muestran identificadores internos ni claves del
  modelo; las posturas y estados aparecen en español (`315db5f`).
- La imagen Docker de la API instala desde `requirements.lock`.
- El README describe EMOtv como herramienta formativa, sin presentarlo como
  apoyo al bienestar emocional.

### Corregido
- Tras el primer acceso el estudiante llega al consentimiento y no al inicio
  (`5c11845`).
- La cámara se apaga al cerrar la pestaña y la vista previa no queda marcada
  como lista cuando el servidor cancela la sesión (`315db5f`).

### Eliminado
- Módulos sin uso (`movement_tracker.py` vacío y un reexport de
  `pose_landmarks`) e imports sin uso.

## [0.4.0] - 2026-10-09

### Añadido
- Análisis en vivo: el estudiante decide qué expresión registrar y la sesión
  la guarda con independencia de la actividad (`6c2c940`).
- Catálogo informativo de expresiones y pantalla de resultado educativa
  (`9f3bb7b`).
- Recomendaciones configurables en la base de datos (`2f59aa0`).
- Chatbot Emi con n8n, conversaciones guardadas 90 días y límites de uso
  (`f458233`); conocimiento controlado de EMOtv y evaluación de Emi
  (`aa88fdc`).
- Cuentas de voluntarios `PRUEBA-NN` y eliminación verificable de sus datos
  (`8d0ead9`).
- Identidad visual con tokens de diseño (`06487c7`).

### Corregido
- Verificación estricta de pasos y repeticiones en actividades secuenciales
  (`91e29d1`).

## [0.3.0] - 2026-10-07

### Añadido
- Primera integración del chatbot (`56be0b4`).
- Despliegue con Docker Compose para la base de datos y el sistema completo
  (`8045f88`).
- Límite de intentos de inicio de sesión y política de contraseñas
  (`af89c9d`).
- Asignación de estudiantes a Psicología y autorización por asignación
  (`7ad4dc3`).
- Política de consentimiento demo v0.2 (`33bbc30`).

### Cambiado
- Se retiró la cámara del servidor: la cámara solo se abre en el navegador; se
  unificó la descarga de modelos (`2cc1fe8`).

### Corregido
- Detector de secretos, hook de pre-commit y reseteo seguro de administración
  (`9798c7a`).

## [0.2.0] - 2026-09-23

### Añadido
- Frontend, API administrativa y FER+ como modelo predeterminado
  (`8c00d0a`).
- Selector de modelos faciales con admisión por recursos, solo para
  administración (`e0ac82a`).
- Primer acceso y consentimiento estudiantil (`d469d6e`).
- Actividades secuenciales y repetición del análisis facial (`60c2570`),
  validadores de posturas (`ecbd932`) y recomendación de actividades
  secuenciales (`ff04ffd`).

## [0.1.0] - 2026-09-08

### Añadido
- Prototipo de detección facial con cámara y reconocimiento de expresiones
  (`c0491fe` a `ef927b8`).
- Detección de pose y ejercicios corporales (`4c4ba9e`).
- Integración de emociones con actividades y sesiones en memoria
  (`c418f38`, `b839b5e`).
- API de sesiones, identidad y actividades con PostgreSQL y Alembic
  (`4076f38`).
