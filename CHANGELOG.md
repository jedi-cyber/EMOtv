# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
El repositorio no tenía etiquetas de versión: las versiones anteriores a
1.0.0 agrupan el historial real de commits por hitos, con la fecha del último
commit de cada grupo. La cronología commit por commit está en
[docs/thesis-evidence/chronology.md](docs/thesis-evidence/chronology.md).

## [Unreleased]

### Añadido
- Paso de reconocimiento «¿Qué emoción es?» en los protocolos. Se muestra una
  imagen emocional del banco y la persona elige entre 2 y 4 opciones que se
  eligen solas. Después lee el nombre de la emoción de la imagen. La cámara no
  se analiza en ese paso. Se registra lo elegido, el tiempo y quién respondió.
  Incluye métricas, línea de tiempo, reporte, estadísticas y el contrato móvil
  4.2 ([docs/emotion-recognition.md](docs/emotion-recognition.md)).
- Migración `20261102_31_recognition_steps`.
- Situaciones en el paso «¿Qué emoción es?»: una historia corta opcional junto
  a la ilustración, con la pregunta «¿Cómo se siente?». El servidor rechaza
  situaciones con DNI, correos o teléfonos. Migración
  `20261102_32_recognition_situations`.
- Modo accesible en los protocolos: pictogramas junto a cada emoción, botones
  y letra más grandes, sin animaciones y pausas del doble. El editor propone
  menos opciones y más tiempo. Migración `20261102_33_accessible_protocols`.
- Plantillas de protocolos: el docente comparte un protocolo suyo con su
  grupo y sus usuarios lo copian como protocolo propio («Copiar y
  modificar»); también se puede duplicar uno propio. Migración
  `20261102_34_protocol_templates`.
- Ejercicios de práctica de expresiones en los protocolos: la persona recibe
  una instrucción y ve una señal de 0 a 1; se registra si logró la expresión
  pedida, en cuánto tiempo y si la señal estuvo visible, sin guardar imágenes
  (`645841e`, `01b9f8d`, `7e50f98`, `15da302`).
- Métricas, línea de tiempo, reporte y estadísticas de los ejercicios con un
  aviso fijo sobre la precisión con niños (`6eceb2c`).
- Contrato móvil 4.1: resultados de práctica en el detalle de la sesión y en
  las estadísticas, solo con campos opcionales (`1829773`).
- Protocolo «Validación con adultos» para voluntarios `PRUEBA-NN` en modo demo
  y exportación CSV agregada para administración (`a4db041`).
- Variables `PRACTICE_THRESHOLD`, `PRACTICE_RELEASE_THRESHOLD`,
  `PRACTICE_SMOOTHING_SECONDS`, `PRACTICE_FRAME_INTERVAL_MS`,
  `PRACTICE_STEP_PAUSE_SECONDS` (antes `PRACTICE_SUCCESS_PAUSE_SECONDS`, que se
  sigue aceptando), `PRACTICE_HOLD_SECONDS` y `PRACTICE_MAX_SECONDS`.
- `GET /protocols/practice-defaults`: lo que el editor propone para un
  ejercicio nuevo.
- Banco inicial de 18 dibujos de creación propia (seis emociones básicas, tres
  variantes de piel y cabello), generados por el sistema y sin fotos de
  personas. El administrador lo agrega con un botón en «Estímulos
  institucionales» (`POST /stimuli/initial-bank`).
- Plantilla de protocolo «Emociones básicas 4 a 6 años»: para niños, en modo
  accesible, con un «¿Qué emoción es?» por emoción y dos opciones. Se copia
  con «Usar la plantilla inicial» en Protocolos (`POST /protocols/starter`).
- «Haz la misma cara»: un ejercicio de práctica que muestra una imagen como
  modelo. La persona lee «Haz la misma cara» y ve la misma señal de 0 a 1. La
  expresión pedida se toma de la imagen y no hay que elegirla. Quien conduce
  ve «Imitar el modelo», y las métricas y la línea de tiempo lo indican.
  Migración `20261104_35_imitation_steps` y contrato móvil 4.3 (`imitate`).
- Migraciones `20261030_28_practice_steps` y `20261030_29_practice_feedback`.
- Prueba e2e de una sesión con un ejercicio de práctica.

### Cambiado
- El docente supervisa y no conduce las sesiones de su grupo. «Por revisar»
  (`GET /reviews`, con contador en el menú) reúne, del más antiguo al más
  nuevo, los reportes enviados y los pedidos de eliminación, para revisarlos
  cuando tenga tiempo. Sus sesiones propias son de demostración: se marcan así
  y no cuentan en las estadísticas.
- La medición de rendimiento de los modelos faciales ya no vence a los 30 días
  y deja de ser requisito: sin ella, HSEmotion y FER+ funcionan con un
  rendimiento de referencia. Se quita `EMOTION_BENCHMARK_MAX_AGE_DAYS`.
- Práctica (§14.5): se puede pedir cualquier expresión del catálogo, incluido
  desprecio; el editor propone 20 s; hay una pausa de 2 s tras cada ejercicio,
  logrado o no; cuadros cada 250 ms y suavizado de 0,49 s.
- Los cuadros de un ejercicio de práctica pasan por el cupo de análisis y se
  descartan si no hay cupo; la pantalla de la persona envía un cuadro a la vez.
- El Analizador cuenta imágenes y ejercicios por separado al elegir un
  protocolo.
- Las imágenes abstractas con respuesta verbal («¿qué ves?») quedan congeladas
  y ocultas porque no forman parte del objetivo. Con
  `ABSTRACT_STIMULI_ENABLED=false` (predeterminado) no se suben, no se ofrecen
  en el banco ni en el editor, y un protocolo que las usa pide reemplazarlas
  antes de iniciar una sesión. Las sesiones, reportes y actas que ya las tienen
  se siguen mostrando.
- Las actividades corporales (posturas verificadas con MediaPipe) quedan
  congeladas y ocultas porque no forman parte del objetivo. Con
  `ACTIVITIES_ENABLED=false` (predeterminado) el Analizador termina en el
  resultado de la expresión, no se inician ni se recomiendan actividades, el
  catálogo solo se lee, Emi no las describe y el menú ya no muestra
  Actividades ni Administrar actividades. Las sesiones anteriores con
  actividad se siguen mostrando. El código, las pruebas y las tablas se
  conservan para los criterios 5, 6 y 7.

### Corregido
- El borrado de los datos de voluntarios incluye los resultados de práctica.
- El proxy de Vite y nginx reenvían `/practice-validation` a la API.

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
