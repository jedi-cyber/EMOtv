# Adaptación a psicoeducación en reconocimiento de emociones

Registro breve del cambio de objetivo. Se actualiza al terminar cada bloque.

**Objetivo:** apoyar la psicoeducación en reconocimiento de emociones en niños y
personas con discapacidad que tienen dificultad para identificarlas, mediante
actividades visuales, dibujos y juegos con apoyos configurables. Se conservan la
visión con modelos preentrenados, Emi, la aplicación web y el aplicativo Android.

## Estado de los bloques

| Bloque | Estado |
|---|---|
| 0. Diagnóstico (este documento) | Completado el 2026-11-06, sin cambios de código |
| 1. Sesiones de reconocimiento sin cámara (backend e interfaz web) | Completado el 2026-11-06 (ver §10); falta la comprobación manual en el navegador |
| 2. Recorrido web sin cámara | Código y pruebas automáticas completos el 2026-11-06 (ver §12); recorridos sin cámara y mixto comprobados en el navegador; falta probar con una cámara real |
| 2b. Apoyos configurables | Partes 1 y 2 completas y recorridas en el navegador el 2026-11-06 (ver §14) |
| 3. Explicaciones educativas y apoyos | Completo el 2026-11-06, comprobado en el navegador (ver §13) |
| 3a. Repetir un paso, tiempo sin límite y pausa para leer | Completo en 2b (§14) |
| Dibujo táctil en la web (bloque 4 del pedido) | Actividad completa el 2026-11-06, sin sesión ni registro; comprobada en el navegador (ver §15) |
| 4a. El dibujo como paso de un protocolo, con registro mínimo | Hecho el 2026-11-06 (§15, «Subtarea 4a»); migración 20261106_40 |
| 4. Primer juego (emparejar; bloque 5 del pedido) | Hecho el 2026-11-06 (§16); migración 20261106_41; contrato móvil 4.6 |
| Segundo juego (busca la misma emoción; bloque 6 del pedido) | Hecho el 2026-11-07 (§17); migración 20261107_42; contrato móvil 4.7 |
| Resultados educativos en reportes y estadísticas (bloque 7 del pedido) | Hecho el 2026-11-07 (§18); sin migración; contrato móvil 4.8 |
| Android como pantalla de la persona (bloque 8 del pedido) | Hecho el 2026-11-07 (§19 y §20); migración 20261107_43; contrato móvil 4.9 |
| Dibujo táctil en Android (bloque 9 del pedido) | Hecho el 2026-11-07 en `EMOtv-android` (§20); contrato móvil 4.10, solo documentación |
| Juego de emparejar en Android (bloque 10A del pedido) | Hecho el 2026-11-07 en `EMOtv-android` (§21); contrato móvil 4.11, solo documentación |
| «Busca la misma emoción» en Android (bloque 10B del pedido) | Hecho el 2026-11-07 en `EMOtv-android` (§22); contrato móvil 4.12, solo documentación |
| 5. Reportes, estadísticas y contrato móvil 4.5 | Pendiente |
| 6. Android sigue el contrato 4.5 | Pendiente |
| 7. Emi, guía de uso y plantillas | Pendiente |

## 1. Lo que hay hoy (diagnóstico)

**Motor de sesiones.** Uno solo, `GuidedSessionService`
(`src/emotv/application/guided_session_service.py`) con `GuidedRun`
(`src/emotv/domain/guided_session.py`). Fases: cuestionario previo → (imágenes
abstractas previas) → **calibración** → pasos (`STIMULI`) → cuestionario posterior →
fin. Una sola confirmación de autorización al crear la sesión, según el público.
Enlace de la pantalla de la persona con un token cuyo hash se guarda. Los pasos con
tiempo (práctica y reconocimiento) avanzan con `_tick_timed` y el reloj del servidor.

**Tipos de paso** (`StepKind` en `src/emotv/domain/protocol.py`):
- `stimulus`: imagen y captura automática de la expresión estimada (cámara).
- `recognition`: «¿Qué emoción es?», con 2 a 4 opciones, sin cámara. `situation`
  opcional («¿Cómo se siente?»). La respuesta correcta la copia el servidor desde la
  imagen. Responde la persona o quien conduce. Resultado: `RecognitionResult`.
- `practice`: producción de una expresión pedida, con una señal de 0 a 1 respecto de
  la base neutral. `imitate=True` es «Haz la misma cara» con una imagen modelo.
  Resultado: `PracticeResult` (sin imágenes, solo contadores y nivel máximo).

Reconocimiento y producción ya tienen resultados, avisos y agregados separados
(`RECOGNITION_NOTICE` y `PRACTICE_NOTICE`).

**Hallazgo principal: la cámara no es complementaria.** Todo protocolo pasa por
`CALIBRATION`, y la fase solo avanza cuando la calibración neutral termina con
cuadros de la cámara (`_receive`, líneas 1123-1148). Un protocolo hecho solo de
reconocimientos tampoco arranca sin cámara, y no hay ninguna opción para omitir la
calibración.

**Accesibilidad.** Solo existe `Protocol.accessible` (booleano): letra y botones más
grandes, pictogramas, sin animaciones y una pausa doble (`ACCESSIBLE_PAUSE_FACTOR`).
No se configura por separado (lectura en voz alta, sin límite de tiempo, número de
opciones por defecto). Existe la síntesis de voz `web/src/analysis/exerciseSpeech.ts`.

**Banco de imágenes.** `Stimulus` con tipo `emotional` o `abstract`, alcance
(grupo, institución o usuario), público (niños = intensidad leve) y
`expected_expression`. Las imágenes que suben los usuarios pasan por la detección
de personas y la revisión del docente. Hay un banco inicial de dibujos generado
por código (`src/emotv/infrastructure/stimuli/initial_bank.py`) y plantillas de
protocolo compartibles (migración 34; «Emociones básicas 4 a 6 años»).

**Reportes y estadísticas.** Reporte por sesión con flujo borrador → enviado →
devuelto o aprobado (`report_service.py`). Las estadísticas agregan sesiones:
expresiones, práctica (por protocolo y expresión pedida), reconocimiento (por
expresión) y cuestionarios (`session_statistics_service.py`). Las sesiones de
demostración del docente no cuentan. Limitación: la imitación se suma a la práctica
(`PracticeResult` no guarda `imitate`); por paso sí se distingue (`session_metrics`).

**Emi.** React → `/chat` (sesión iniciada, límites, filtros de riesgo y de
identificadores, historial de 90 días) → workflow de Sim. Se le envía
`knowledge` desde `emi_knowledge.py` (tope de 12 000 caracteres), nunca datos de
sesiones. El conocimiento ya describe reconocimiento, situaciones, práctica e
imitación; no menciona dibujo, juegos ni apoyos. El aplicativo Android no usa Emi.

**Android** (`C:\Users\CHINO\AndroidStudioProjects\EMOtv`). Solo consulta: inicio,
sesiones, detalle con métricas de práctica y reconocimiento, reporte (editar,
enviar, comentar, devolver, aprobar), pendientes del docente y estadísticas; 17
endpoints en `EmotvApi.kt`. Sigue el contrato 4.4; su `docs/mobile-api.md` es
idéntico al de la web. No conduce sesiones ni envía imágenes. Tiene un cambio
local ajeno sin confirmar (`.idea/deploymentTargetSelector.xml`).

**Ya congelado y fuera del recorrido principal:** posturas (`ACTIVITIES_ENABLED`),
examen simulado (`EXAMS_ENABLED`) e imágenes abstractas
(`ABSTRACT_STIMULI_ENABLED`). Se conserva su código.

## 2. Matriz

| Elemento | Decisión | Motivo |
|---|---|---|
| Login, roles, MFA, compromiso, `can_access_session`, auditoría, cifrado y retención | Mantener | Sin cambios de dominio |
| Autorización única por público y código de sesión | Mantener | Sigue aplicando sin cámara |
| Motor `GuidedSessionService` y vista de la persona con token | Mantener; extender | Base única para los pasos nuevos |
| Pasos `recognition` y situaciones | Mantener | Núcleo del reconocimiento |
| Pasos `practice` e `imitate` | Mantener como **producción**, opcional | Usan la cámara; resultados separados del reconocimiento |
| Calibración obligatoria | **Modificar**: solo si el protocolo tiene pasos con cámara | La cámara pasa a ser complementaria |
| `Protocol.accessible` (booleano) | **Modificar**: apoyos configurables, con `accessible` como preajuste compatible | Apoyos configurables del objetivo |
| Estadísticas de práctica | **Modificar**: separar imitación de producción a pedido | Son actividades distintas |
| Reportes, estadísticas y contrato móvil | **Modificar** (campos opcionales, revisión 4.5) | Mostrar dibujo y juegos |
| Conocimiento de Emi y guía de uso | **Modificar** | Describir dibujo, juegos y apoyos |
| Paso `drawing` | **Agregar** | Dibujo sin interpretación |
| Paso `game` (primero: emparejar) | **Agregar** | Juegos sobre el mismo motor |
| `ActivityResult` (resultado de dibujo y juego) | **Agregar** | Registro mínimo, solo contadores |
| Posturas, examen simulado e imágenes abstractas | Ocultar (ya ocultos) | Fuera del objetivo; código histórico intacto |
| Análisis libre sin protocolo (fase `live`) | Mantener, en segundo plano | Útil para demostrar; no es el recorrido principal |

## 3. Dibujo y juegos sin duplicar el motor

Ambos se agregan como **tipos de paso** de `ProtocolStep` y usan el mismo camino
de los pasos con tiempo (`_tick_timed`, `steps_log`, saltar, detener, pausa del
modo accesible y vista de la persona con token). No se crea otro servicio de
sesiones, otra tabla de sesiones ni otro flujo de autorización.

**Paso `drawing`.** Consigna «Dibuja una cara de {emoción}» o «Dibuja cómo se siente»
con `situation`, una imagen de apoyo opcional (`stimulus_id`) y un tiempo máximo
opcional. Se dibuja en papel o en un lienzo del navegador. **El dibujo no se
guarda, no se sube, no lo ve ningún clasificador y no se envía a Emi**; el lienzo
se borra al terminar el paso. Termina cuando quien conduce marca «Terminó», o al
saltar, detener o vencer el tiempo. No analiza la cámara.

**Paso `game`.** `game_type` con un valor inicial, `matching` (emparejar cada
situación o cara con su emoción, de 2 a 4 pares tomados del banco aprobado).
Después pueden venir `memory` o `sorting` sin cambiar el contrato. Las respuestas
correctas las fija el servidor a partir de `expected_expression`, como en el
reconocimiento. No analiza la cámara.

**Registro mínimo propuesto: `ActivityResult`** (una tabla nueva, un registro por paso):

| Campo | Contenido |
|---|---|
| `id`, `session_id`, `step_index` | Igual que los otros resultados |
| `kind` | `drawing` o `game` |
| `game_type` | Nulo en el dibujo |
| `target_expression` | Emoción pedida (dibujo); nulo en un juego con varias emociones |
| `outcome` | `completed`, `timed_out`, `skipped` o `stopped` |
| `rounds_total`, `rounds_matched` | Solo juegos: contadores, sin la lista de jugadas |
| `supports_used` | Apoyos activos en el paso (por ejemplo, pictogramas o lectura en voz alta) |
| `completed_by` | `participant` o `conductor` |
| `started_at`, `ended_at` | Con zona horaria |

No guarda imágenes, trazos, texto libre ni ninguna calificación del dibujo. Los
reportes dicen qué ocurrió («terminó el dibujo», «emparejó 3 de 4»). Las
estadísticas tienen una sección propia, separada del reconocimiento y de la
producción.

## 4. Dependencias y plan incremental

```
1 Cámara complementaria ─┬─> 3 Dibujo ──┬─> 5 Reportes, estadísticas, contrato 4.5 ─> 6 Android
2 Apoyos configurables ──┴─> 4 Juego ───┘                                         └─> 7 Emi, guía, plantillas
```

1. **Cámara complementaria.** Si el protocolo no tiene pasos `stimulus` ni
   `practice`, se pasa de la confirmación o del cuestionario previo directamente a
   los pasos, y la vista de la persona no pide la cámara. Sin migración ni cambio de
   contrato. Revisar en `GuidedConductorPage` y `ParticipantViewPage` dónde se llama a
   `getUserMedia`.
2. **Apoyos configurables.** Ajustes por protocolo: pictogramas, lectura en voz
   alta, sin límite de tiempo (o tiempo amplio), pausa larga y número de opciones
   por defecto. Una migración nueva; `accessible=True` equivale al preajuste actual.
3. **Dibujo**: tipo de paso, `ActivityResult` (migración), editor de protocolos,
   pantalla de la persona y de quien conduce, línea de tiempo y reporte.
4. **Juego `matching`**: mismo `ActivityResult`, sin otra migración salvo
   `game_type`.
5. **Reportes y estadísticas** por tipo de actividad, imitación separada de la
   producción y contrato móvil 4.5 con campos opcionales (compatible con la 4).
6. **Android** muestra los campos nuevos y los ignora si faltan.
7. **Emi y guía**: conocimiento, `docs/chatbot/emotv-descripcion-sim.md`
   (el workflow de Sim no se edita desde aquí), guía de uso y plantillas de
   ejemplo con dibujo y juego.

## 5. Criterios de aceptación

- Un protocolo de reconocimiento, dibujo o juego se aplica de principio a fin sin
  cámara; uno con producción la pide y calibra como hoy.
- El reconocimiento, la producción (práctica e imitación por separado), el dibujo y
  los juegos tienen resultados, textos y agregados separados.
- Ningún dibujo, trazo ni imagen de una persona se guarda o sale del servidor; nada
  de eso llega a Emi ni a un clasificador.
- Los textos describen qué ocurrió y no valoran a la persona; no hay puntajes,
  diagnósticos ni interpretación de dibujos.
- Los apoyos se configuran por protocolo y los protocolos con `accessible`
  existentes se ven igual que antes.
- Sin cuentas ni perfiles de niños o de participantes; las estadísticas cuentan
  sesiones.
- El contrato móvil sigue siendo compatible con la revisión 4; Android compila y
  sus pruebas pasan.
- Al cerrar cada bloque: `python -m pytest -q`; en `web/`, `npx tsc -b` y
  `npx vitest run`; en Android, las pruebas unitarias con Gradle si se modificó.

## 6. Riesgos y decisiones pendientes

**Decisiones pendientes (del desarrollador o de la Facultad):**
1. ¿El lienzo de dibujo está en el navegador, o el dibujo se hace en papel y solo
   se registra que terminó? Propuesta: ambos, sin guardar nunca el dibujo.
2. ¿Se permite guardar algún dibujo (por ejemplo, para el docente)? Propuesta: no;
   es un dato personal del niño y choca con «ninguna imagen sale del servidor».
3. ¿Qué juegos después de `matching`, y cuántos? Propuesta: solo uno en la v1.
4. ¿«Personas con discapacidad» adultas usan el mismo público «adultos» con apoyos?
   Propuesta: sí, sin un público nuevo.
5. Los 18 criterios de v1.0.0 incluyen posturas (5 a 7) aunque estén congeladas;
   confirmar si siguen vigentes para la tesis. Este bloque no cambia la tesis.

**Riesgos:**
- Los modelos de expresión no están validados con niños ni con personas con
  discapacidad; la producción queda como opcional y conserva su aviso.
- El tiempo límite puede saturar a un niño dentro del espectro autista: el apoyo
  «sin límite de tiempo» va antes que los juegos.
- Cada paso nuevo agranda `GuidedSessionService` (1179 líneas); conviene aislar la
  lógica de cada tipo en funciones propias, sin otro motor.
- El contrato móvil debe crecer solo con campos opcionales para no romper Android.
- Los textos de autorización mencionan el análisis de la cámara; revisar su
  redacción cuando una sesión no la use, sin quitar la confirmación.

## 7. Verificaciones

Bloque 0 (solo inspección y comandos breves; no se ejecutó ninguna suite):

| Herramienta | Estado comprobado |
|---|---|
| Python 3.12.10 en `.venv`, pytest 9.1.1, FastAPI 0.141.1, Alembic 1.20.0 | Disponibles (versión) |
| Pruebas Python | 110 archivos `test_*.py` en `tests/` (no ejecutadas) |
| Node 26.12.1, `tsc` y `vitest` en `web/node_modules` | Disponibles (no ejecutados) |
| Pruebas web | 40 archivos en `web/tests`, 7 en `web/e2e`; Playwright con Chromium instalado |
| PostgreSQL | Servicio `postgresql-x64-18` en ejecución; `DATABASE_URL` en `.env` apunta a 127.0.0.1:5432 (sin conectar) |
| Pesos de modelos | `models/weights/` con `emotion`, `yunet`, `pose` y `experimental` |
| Android | `gradlew`, SDK y el JDK de Android Studio (`jbr`) presentes; en el PATH está Java 1.8, que no sirve para Gradle: usar `JAVA_HOME` con el `jbr` |

## 8. Archivos modificados

- Bloque 0: `docs/adaptacion-psicoeducacion.md` (nuevo). Sin cambios en Android.
- Bloque 1: ver §10 (backend) y §11 (interfaz).

## 9. Siguiente paso concreto

1. Probar «Mixto» con una cámara real (§12, paso 3) y escuchar «Escuchar» con
   altavoces (§13).
2. Que Psicología revise las explicaciones (§13) y la regla de contar solo el
   primer intento (§14, parte 2).

## 10. Bloque 1: sesiones de reconocimiento sin cámara (backend)

**Decisión.** `Protocol.uses_camera` es verdadero en un examen o si algún paso es
`stimulus` o `practice` (incluida la imitación). Un protocolo solo de
reconocimientos (con o sin situación) no usa la cámara.

**Transiciones sin cámara.** Inicio → (cuestionario previo) → `ready` → «Empezar»
→ primer paso (`stimuli`) → … → (cuestionario posterior) → `finished`. No pasa por
`calibration`. En `ready` el tiempo no corre, no hay paso que saltar y se puede
detener. Saltar, detener, el tiempo vencido y la pausa funcionan igual en los
pasos. Los protocolos con cámara y los mixtos no cambian: calibran antes del
primer paso.

**Por qué «Empezar».** Reemplaza al botón «Iniciar calibración», así que no agrega
pasos. Evita que el primer paso corra antes de que se abra la pantalla de la
persona, y sirve también cuando quien conduce registra lo que la persona señala,
sin pantalla propia.

**Cambios de contrato (web; Android no conduce sesiones):**
- `GET /guided-sessions/{id}` y `GET /sessions/{id}/guided-results`: campo nuevo
  `uses_camera` (booleano, siempre presente).
- `GET /participant-view/{token}`: campo `uses_camera: false` **solo** en las
  sesiones sin cámara; si falta, se asume `true`. Así las respuestas de las sesiones
  con cámara quedan idénticas. `capture_frames` es siempre `false` sin cámara. En
  `ready`, el mensaje es «En un momento empezamos.».
- La fase `ready`, que antes solo usaba la estación de examen, también es la
  espera de «Empezar» en una sesión sin cámara.
- `POST /guided-sessions/{id}/start` (nuevo): de `ready` al primer paso. Responde
  409 si la sesión usa la cámara, es un examen o no está en `ready`; solo quien
  conduce.
- `POST /guided-sessions/{id}/calibration` responde 409 («Esta sesión no usa la
  cámara: no se calibra») en una sesión sin cámara.
- `POST /guided-sessions/{id}` no exige el modelo facial si no hay cámara: la sesión
  queda con `emotion_model_id` y `emotion_model_version` nulos (los campos ya eran
  opcionales). Con cámara, si falta el modelo, sigue respondiendo 409.
- Los cuadros que lleguen a una sesión sin cámara se aceptan (`{"received": true}`)
  y se descartan sin analizarlos.
- Sin migración. Sin cambios en `/mobile` (el contrato móvil sigue en 4.4).

**Comportamiento que cambió en las pruebas.** Antes, un protocolo solo de
reconocimientos pasaba por la calibración. Los auxiliares `start` de
`test_recognition_sessions.py` y `test_accessible_protocols.py` ahora usan
`begin_steps` (nuevo, en `test_guided_sessions.py`): calibra o pulsa «Empezar»
según la fase.

**Archivos modificados:** `src/emotv/domain/protocol.py`,
`src/emotv/domain/guided_session.py` (solo el comentario de `READY`),
`src/emotv/application/guided_session_service.py`,
`src/emotv/interfaces/web/guided_router.py`,
`tests/integration/test_camera_optional_sessions.py` (nuevo),
`tests/integration/test_guided_sessions.py`,
`tests/integration/test_recognition_sessions.py`,
`tests/integration/test_accessible_protocols.py` y este documento.

## 11. Bloque 1: interfaz web

**Cambios.** `GuidedConductorPage`: en `ready` con `uses_camera === false`
muestra la tarjeta «Lista para empezar» («Esta sesión no usa la cámara: no hay
calibración…») y el botón «Empezar» (`POST /start`). Con cámara, la calibración
sigue igual. `ParticipantViewPage` no monta el `<video>` si `uses_camera` es falso;
la cámara se sigue abriendo solo si `capture_frames` es verdadero. Tipos:
`uses_camera?` en `GuidedState` y `ParticipantViewState`.

**Archivos:** `web/src/api/types.ts`, `web/src/pages/GuidedConductorPage.tsx`,
`web/src/pages/ParticipantViewPage.tsx` y `web/tests/guided_session.test.tsx`
(3 pruebas nuevas).

**Verificación (2026-11-06).**
- `npx tsc -b`: sin errores.
- `npx vitest run`: 40 archivos, 276 pruebas aprobadas.
- `python -m pytest -q --basetemp=<carpeta escribible>`: 1048 aprobadas, 3 saltadas, 0 fallos. Sin
  `--basetemp`, las pruebas que usan `tmp_path` dan error de entorno
  (`PermissionError: [WinError 5]` sobre `AppData\Local\Temp\pytest-of-CHINO`),
  ajeno al cambio.
- **No ejecutada:** la comprobación en el navegador. Habría creado protocolos y
  sesiones en la base PostgreSQL local del desarrollador.

**Comprobación manual reproducible** (API en 8000 y web en 5173, cuenta de
usuario de prueba):
1. Crear un protocolo para adultos con dos pasos «¿Qué emoción es?» y ninguno de
   imagen ni de práctica.
2. En el Analizador, iniciarlo con «cuento con su autorización firmada». La vista
   de quien conduce muestra «Lista para empezar», sin «Iniciar calibración».
3. Abrir la pantalla de la persona: dice «En un momento empezamos.» y el
   navegador **no** pide permiso de cámara.
4. Pulsar «Empezar»: aparece el paso 1 con su tiempo. Responder en la pantalla de
   la persona; el paso 2 vence sin respuesta. La sesión termina, y el detalle
   muestra 2 reconocimientos y ninguna captura.
5. Repetir con un protocolo que tenga un ejercicio de práctica: debe pedir la
   cámara y calibrar como antes.

**Limitaciones.** Si la pantalla de la persona se abre después de «Empezar», el
primer paso ya está corriendo (el texto de la tarjeta lo advierte). Sin cambios en
Android.

## 12. Bloque 2: recorrido web sin cámara

**Diagnóstico.** El Analizador exigía probar la cámara antes de cualquier
protocolo, y su texto siempre decía «calibración». En la pantalla de la persona,
si se negaba el permiso solo se leía «Avisa a quien conduce», y una sesión mixta
quedaba detenida en la calibración sin forma de seguir.

**Decisiones.**
- **La cámara la pide solo la pantalla de la persona**, cuando la sesión envía
  cuadros (`capture_frames`): en la calibración y en los pasos de imagen o de
  práctica. El Analizador ya no la pide para un protocolo; sigue pidiéndola para
  el análisis sin protocolo.
- **Seguir sin cámara.** Si la pantalla de la persona no puede usarla, solo
  informa el motivo. Quien conduce decide con «Continuar sin cámara», que
  también ofrece en la calibración o en un paso con cámara aunque no haya aviso.
  Desde entonces:
  - no se calibra;
  - un paso con cámara en curso se salta (si era una práctica, queda su
    resultado como saltado);
  - los pasos con cámara siguientes se saltan sin empezar: quedan en
    `steps_log` con `reason: "no_camera"` y no dejan resultado de práctica;
  - los reconocimientos siguen igual.
  Se puede elegir también en el cuestionario previo: la sesión espera «Empezar».
  No hay vuelta atrás dentro de la misma sesión.
- **Liberar la cámara.** La pantalla de la persona apaga las pistas y suelta el
  video cuando deja de enviar cuadros, al fallar, al desmontarse y en `pagehide`.

**Contrato (web; sin cambios en `/mobile`):**
- `ProtocolResponse.uses_camera` (nuevo, booleano).
- `POST /participant-view/{token}/camera-problem` con
  `{"reason": "denied" | "busy" | "not_found" | "insecure" | "unknown"}`. Responde
  `{"received": true}`, 422 si el motivo no es válido y 404 si el enlace no vale.
  El motivo vive solo en memoria.
- `POST /guided-sessions/{id}/continue-without-camera`: solo quien conduce.
  Responde 409 sin protocolo, en un examen, en un protocolo sin cámara o en una
  sesión terminada. Repetirlo no cambia nada.
- `GET /guided-sessions/{id}`: campos nuevos `camera_off` y `camera_problem`.
  `steps_log[].reason` es opcional.
- `GET /participant-view/{token}`: `uses_camera: false` también aparece tras
  seguir sin cámara, y `capture_frames` queda en falso.
- Migración `20261106_36_guided_camera_off`: columna `guided_runs.camera_off_at`,
  nula en las sesiones existentes.

**Avisos.**
- La persona lee: «No se pudo usar la cámara. Avisa a quien conduce la sesión:
  puedes seguir con las actividades de elegir emociones, que no la necesitan.»
- Quien conduce lee el motivo y que siguen los pasos «¿Qué emoción es?» y se
  saltan los que necesitan la cámara.
- En el Analizador, para un protocolo con cámara: «La cámara se pide en la
  pantalla de la persona solo en los pasos que la necesitan; si no está
  disponible, siguen los pasos sin cámara.» Para uno sin cámara: «No usa la
  cámara.»

**Archivos.**
- Backend: `src/emotv/domain/protocol.py` (`ProtocolStep.uses_camera`),
  `src/emotv/domain/guided_session.py`,
  `src/emotv/application/guided_session_service.py`,
  `src/emotv/interfaces/web/guided_router.py`,
  `src/emotv/interfaces/web/stimulus_router.py`,
  `src/emotv/infrastructure/persistence/models.py`,
  `src/emotv/infrastructure/persistence/postgres_guided_repositories.py` y
  `migrations/versions/20261106_36_guided_camera_off.py` (nuevo).
- Web: `web/src/api/types.ts`, `web/src/pages/AdaptiveAnalysisPage.tsx`,
  `web/src/pages/GuidedConductorPage.tsx` y `web/src/pages/ParticipantViewPage.tsx`.
- Pruebas: `tests/integration/test_continue_without_camera.py` (nuevo, 8),
  `web/tests/guided_session.test.tsx` (4 nuevas) y
  `web/tests/adaptive_analysis.test.tsx` (1 nueva).

**Verificación (2026-11-06).**
- `npx tsc -b`: sin errores.
- `npx vitest run`: 40 archivos, 281 pruebas aprobadas.
- `python -m pytest -q --basetemp=<carpeta escribible>`: 1056 aprobadas, 3 saltadas, 0 fallos.
- Migraciones en PostgreSQL real: `alembic upgrade head` aplicó 35 y 36 sin errores
  en una base desechable (`emotv_bloque2_check`), no en la de trabajo.
- **Navegador, «Solo reconocer» (completo).** Se usaron la API y la web locales
  sobre esa base, y el desarrollador marcó la confirmación de la autorización.
  - El Analizador no lista la cámara como requisito y dice «2 reconocimientos.
    No usa la cámara.».
  - Quien conduce ve «Lista para empezar», y la persona, «En un momento
    empezamos.».
  - Tras «Empezar», la persona respondió «Tristeza» en el paso 1 y dejó vencer
    el paso 2. Quien conduce leyó «La sesión terminó y quedó registrada.», con
    «Respondió: Tristeza a los 7 s» y «Terminó el tiempo sin respuesta».
  - En la pantalla de la persona, `getUserMedia` se llamó 0 veces y no hubo
    ningún elemento `<video>`.
- **Navegador, «Mixto» con la cámara bloqueada (completo).** El navegador
  integrado no permite la cámara, así que equivale a negar el permiso.
  - El Analizador dice «calibración, 2 ejercicios de práctica, 1
    reconocimiento. La cámara se pide en la pantalla de la persona solo en los
    pasos que la necesitan…» y habilita «Empezar la sesión» sin probar la cámara.
  - Al iniciar la calibración, la persona leyó el aviso «No se pudo usar la
    cámara… puedes seguir con las actividades de elegir emociones…».
  - Quien conduce leyó «La pantalla de la persona no pudo usar la cámara: se
    negó el permiso.» y la opción «Continuar sin cámara».
  - Al pulsarla, quien conduce pasó a «La sesión sigue sin cámara…» y al «Paso 2
    de 3 · reconocimiento»: la práctica 1 se saltó. La persona vio las opciones,
    sin aviso y sin ningún elemento `<video>`.
  - Respondió «Tristeza». La práctica 3 se saltó y la sesión terminó: «Paso 2 ·
    imagen de Tristeza · Respondió: Tristeza a los 10 s». No hay resultados de
    práctica.
- No se probó una cámara real, porque el navegador integrado la bloquea.
- **Observación fuera del bloque.** En la vista de quien conduce (`/guided/…`),
  la miga de pan dice «Página no encontrada»: `labels` de
  `web/src/layouts/AppLayout.tsx` no tiene la clave `guided`. Es anterior a este
  bloque y no se corrigió.

**Comprobación manual pendiente** (base `emotv_bloque2_check`, que tiene las
dos cuentas de prueba, un Usuario y un Docente, y los
protocolos «Solo reconocer» y «Mixto»):
1. «Solo reconocer»: hecho (ver arriba).
2. «Mixto» con la cámara bloqueada: hecho (ver arriba). Para repetirlo con un
   permiso denegado a mano, en un navegador con cámara: «Mixto», con el permiso de cámara **denegado** en la pantalla de la persona:
   pulsar «Iniciar calibración». La persona lee el aviso; quien conduce ve «se
   negó el permiso» y «Continuar sin cámara». Al pulsarlo, se salta la práctica
   1, se muestra el reconocimiento, se salta la práctica 3 y la sesión termina.
3. «Mixto», con el permiso **permitido**: calibra y la práctica pide la cámara.
   En el reconocimiento el indicador de cámara del sistema se apaga, y vuelve a
   encenderse en la práctica siguiente.
4. Al terminar, eliminar la base: `DROP DATABASE emotv_bloque2_check`.

**Limitaciones.**
- Tras seguir sin cámara, la sesión no puede volver a usarla.
- Si un reconocimiento queda entre dos prácticas, el navegador puede volver a
  pedir el permiso de cámara; depende de cómo recuerde el permiso.
- Sin cambios en Android.

## 13. Bloque 3: explicaciones educativas y apoyos

**Diagnóstico.**
- Al responder, la persona leía solo «Es tristeza» durante la pausa (2 s, o 4 s
  en modo accesible). No había ninguna explicación ni forma de volver a oír la
  consigna.
- La opción elegida se distinguía solo por el color.
- Con una situación se preguntaba «¿Cómo se siente?» y se respondía «Es
  tristeza»: eso enseñaba una única respuesta emocional para la situación.
- El catálogo `expression_info` ya tenía textos revisables, pero escritos para
  personas adultas y demasiado largos para la actividad infantil.

**Decisiones.**
- **Explicación sencilla.** Campo nuevo `expression_info.child_explanation`:
  una oración, de 10 a 200 caracteres, que describe la cara («En la tristeza, las
  cejas suben en el centro y las puntas de la boca bajan.»).
  - Es parte del catálogo revisable: se edita en «Catálogo de expresiones» con
    la misma revisión de siempre.
  - Los textos iniciales son borradores del equipo. Ningún LLM la genera, ni
    antes ni durante la actividad.
  - La pantalla de la persona la recibe solo al terminar el paso (respuesta o
    tiempo vencido), igual con cualquier opción elegida.
- **Situaciones.**
  - La pregunta pasa a «¿Qué emoción muestra la cara?».
  - Al terminar se lee «La cara de la imagen muestra tristeza.» y «En una
    situación así, cada persona puede sentir algo distinto.».
  - El resultado registrado no cambia.
- **Repetir.** «Escuchar» lee con la voz del navegador la situación y la
  consigna; al terminar, la respuesta, la aclaración y la explicación. Se puede
  pulsar las veces que haga falta y nunca responde por la persona. Si el
  navegador no tiene voz, no aparece.
- **Retroalimentación respetuosa.** Nunca dice si la persona acertó ni la
  valora. La elegida muestra «✓ Tu elección» además del color; el lector de
  pantalla la anuncia con `aria-pressed`.
- **Controles táctiles.** Los botones existentes ya miden al menos 3,5 rem (7
  rem en modo accesible). Se agregó `touch-action: manipulation` para evitar el
  zoom por doble toque. «Escuchar» mide 3 rem.
- No se rediseñó la aplicación: solo cambió el bloque del reconocimiento.

**Revisión de tiempo flexible y pausas → subtarea 3a (no hecha).**
- La pausa tras responder (2 s; 4 s accesible) es corta para leer la
  explicación. Para eso «Escuchar» está disponible hasta el paso siguiente.
- Repetir un paso exige más de un resultado por paso: hoy
  `uq_recognition_results_session_step` admite uno solo, así que hacen falta
  intentos en el dominio, en la base, en las métricas y en el contrato móvil.
- «Sin límite de tiempo», una pausa para leer y «esperar a quien conduce para
  seguir» son apoyos por protocolo: van con el bloque 2b (apoyos
  configurables), que cambia `Protocol` y necesita su propia migración.
- Son cambios de dominio amplios, así que el bloque se detuvo antes de
  ampliarlos.

**Contrato (web; `/mobile` sin cambios).**
- `GET /participant-view/{token}`: `recognition` gana `explanation` y `note`
  (nulos hasta que termina el paso). Con situación, `question` es «¿Qué emoción
  muestra la cara?» y `message` es «La cara de la imagen muestra …».
- `GET /expressions` y `/expressions/{key}` ganan `child_explanation`.
  `PUT /expressions/{key}` la acepta como opcional (sin el campo se conserva).
- Migración `20261106_37_child_explanation`: agrega la columna, la llena con
  borradores y devuelve a borrador las filas que estaban revisadas, porque el
  texto nuevo no está revisado.

**Archivos.**
- Backend: `src/emotv/domain/expression_info.py`,
  `src/emotv/domain/guided_session.py`, `src/emotv/domain/protocol.py`
  (comentario), `src/emotv/application/guided_session_service.py`,
  `src/emotv/infrastructure/persistence/models.py`,
  `src/emotv/infrastructure/persistence/postgres_expression_info_repository.py`,
  `src/emotv/interfaces/web/expression_router.py`,
  `src/emotv/interfaces/web/guided_router.py`,
  `src/emotv/interfaces/web/stimulus_router.py` (comentario),
  `src/emotv/interfaces/web/app.py` y
  `migrations/versions/20261106_37_child_explanation.py` (nuevo).
- Web: `web/src/analysis/exerciseSpeech.ts`, `web/src/api/types.ts`,
  `web/src/expressions/ExpressionCatalog.tsx`,
  `web/src/pages/ParticipantViewPage.tsx`,
  `web/src/pages/AdminExpressionsPage.tsx`,
  `web/src/pages/GuidedConductorPage.tsx`, `web/src/pages/ProtocolsPage.tsx` y
  `web/src/styles/global.css`.
- Docs: `docs/emotion-recognition.md` y `docs/expression-catalog.md`.
- Pruebas: `tests/integration/test_recognition_explanations.py` (nuevo, 8),
  `tests/integration/test_recognition_situations.py`,
  `tests/integration/test_privacy_accounts.py` (catálogo en el entorno),
  `web/tests/recognition_supports.test.tsx` (nuevo, 5),
  `web/tests/expression_catalog.test.tsx` (1 nueva) y
  `web/tests/situations.test.tsx`.

**Verificación (2026-11-06).**
- `npx tsc -b`: sin errores.
- `npx vitest run`: 287 pruebas aprobadas.
- `python -m pytest -q --basetemp=<carpeta escribible>`: 1063 aprobadas, 3
  saltadas, 0 fallidas.
- Migración 37 en PostgreSQL real (base desechable `emotv_bloque2_check`):
  upgrade, downgrade a 36 y upgrade otra vez, sin errores.
- **Navegador (protocolo «Situación», agregado a la base desechable).** El
  desarrollador marcó la confirmación de la autorización.
  - Paso 1, con situación: la persona leyó la situación y «¿Qué emoción muestra
    la cara?». «Escuchar» leyó «A Lucía se le cayó su helado al piso. ¿Qué
    emoción muestra la cara?» (se capturó el texto enviado a la voz).
  - Eligió «Sorpresa»: el botón mostró «✓ Tu elección» y se leyó «La cara de la
    imagen muestra tristeza.», «En una situación así, cada persona puede sentir
    algo distinto.» y la explicación de la tristeza. Nada dijo si coincidió.
  - Paso 2, sin situación: eligió «Tristeza» y se leyó «Es tristeza» con la
    explicación; «Escuchar» leyó ambas.
  - La sesión terminó con los dos resultados. No se pidió la cámara. Las
    opciones miden 56 px de alto y usan `touch-action: manipulation`.
  - Hallazgo corregido: «✓ Tu elección» quedaba al lado del nombre y apretado,
    así que el botón ahora apila el nombre y la marca
    (`flex-direction: column`). En modo accesible el pictograma también queda
    encima del nombre.
  - Confirmado: la pausa de 2 s alcanza apenas para leer la explicación (ver
    subtarea 3a).
- No se escuchó la voz con altavoces: se comprobó el texto enviado.

**Limitaciones.**
- La explicación se muestra aunque la fila del catálogo esté en borrador: todas
  lo están hasta que Psicología las revise.
- «Escuchar» depende de la voz del navegador; si falta, el botón no aparece.
- Sin cambios en Android.

## 14. Bloque 2b: apoyos configurables y repetir un paso

**Diagnóstico.** El modo accesible era un único booleano (`Protocol.accessible`)
que activaba a la vez pictogramas, botones grandes y una pausa del doble. No
había lectura en voz alta, ni tiempo sin límite, ni forma de esperar a quien
conduce.

**Decisiones.**
- `ProtocolSupports` (dominio), por protocolo:
  - `pictograms`;
  - `large_controls` (botones y letra grandes, sin animaciones);
  - `read_aloud`;
  - `no_time_limit`;
  - `pause`: `normal`, `long` (el doble) o `wait`.
- **Compatibilidad.** `accessible=True` sin apoyos equivale a `ACCESSIBLE_PRESET`
  (pictogramas, botones grandes y pausa larga). La migración da ese mismo
  preajuste a los protocolos que ya eran accesibles. Después, `accessible` indica
  si el protocolo tiene algún apoyo. Un examen no admite apoyos.
- **Sin límite de tiempo.** El reconocimiento y la práctica terminan al
  responder, al lograrlo o cuando quien conduce los salta. Tienen un tope de
  seguridad de 30 min (`NO_TIME_LIMIT_SECONDS`). Quien conduce lee «Sin límite de
  tiempo» en lugar de la cuenta regresiva.
- **Esperar a quien conduce.** Tras responder, lograrlo o vencer el tiempo, la
  persona sigue viendo la respuesta y la explicación hasta que quien conduce
  pulsa «Seguir». Hay un tope de 10 min (`WAIT_PAUSE_SECONDS`). Con esto la
  subtarea 3a cuenta con una pausa para leer.
- **Leer en voz alta.** La pantalla de la persona lee la consigna al empezar
  cada paso y, en «¿Qué emoción es?», la respuesta y la explicación al
  terminar. «Escuchar» sigue disponible.
- **Editor.**
  - «Modo accesible» marca o quita el preajuste.
  - «Apoyos uno por uno» permite ajustar cada apoyo.
  - En la lista, el protocolo aparece como «Modo accesible» o «Con apoyos».
- **Quien conduce.** El encabezado del paso nombra los apoyos activos.
- Lo que se registra no cambia: los apoyos cambian solo el ritmo y la pantalla.

**Contrato (web; `/mobile` sin cambios).**
- `POST/PUT /protocols`: `supports` es opcional y manda sobre `accessible`.
  `ProtocolResponse` gana `supports`.
- `GET /guided-sessions/{id}`: gana `supports` y `waiting_for_conductor`.
  `remaining_seconds` es nulo en un paso sin límite de tiempo.
- `POST /guided-sessions/{id}/continue` («Seguir»): solo quien conduce. Responde
  409 si no hay un paso esperando.
- `GET /participant-view/{token}`:
  - gana `supports` (`pictograms`, `large_controls`, `read_aloud`), que solo
    aparece si alguno está activo;
  - `accessible` indica pictogramas o botones grandes;
  - `remaining_seconds` es nulo en un paso sin límite de tiempo.
- Migración `20261106_38_protocol_supports`: columnas `support_*`. Usa
  `add_column` y `drop_column` directos, como la 33 (en SQLite, `protocols` no
  puede recrearse por sus claves foráneas). Por eso no hay restricción CHECK
  para `support_pause`: el dominio valida el valor.

**Archivos.**
- Backend: `src/emotv/domain/protocol.py`,
  `src/emotv/application/protocol_service.py`,
  `src/emotv/application/guided_session_service.py`,
  `src/emotv/infrastructure/persistence/models.py`,
  `src/emotv/infrastructure/persistence/postgres_practice_repositories.py`,
  `src/emotv/interfaces/web/stimulus_router.py`,
  `src/emotv/interfaces/web/guided_router.py` y
  `migrations/versions/20261106_38_protocol_supports.py` (nuevo).
- Web: `web/src/api/types.ts`, `web/src/pages/ProtocolsPage.tsx`,
  `web/src/pages/ParticipantViewPage.tsx` y
  `web/src/pages/GuidedConductorPage.tsx`.
- Pruebas: `tests/integration/test_protocol_supports.py` (nuevo, 10) y
  `web/tests/protocol_supports.test.tsx` (nuevo, 9).

**Verificación (2026-11-06).**
- `npx tsc -b`: sin errores.
- `npx vitest run`: 296 pruebas aprobadas.
- `python -m pytest -q --basetemp=<carpeta escribible>`: 1073 aprobadas, 3
  saltadas, 0 fallidas.
- Migración 38 en PostgreSQL real (base desechable): upgrade, downgrade a 37 y
  upgrade otra vez, sin errores.
- **Navegador.** En el editor, «Solo reconocer» quedó con lectura en voz alta,
  sin límite de tiempo y pausa «esperar». Se guardó como versión 2, porque la 1
  ya se había usado, y la lista la muestra «Con apoyos». La API devuelve esos
  apoyos. Recorrido de la sesión, con dos pestañas y sin cámara:
  - quien conduce ve «Sin límite de tiempo», sin cuenta regresiva, y los apoyos
    activos;
  - la pantalla de la persona lee «¿Qué emoción es?» al empezar el paso y la
    explicación al responder;
  - pasados 25 s el paso seguía abierto, y se respondió a los 40,6 s;
  - tras responder aparece «Pulsa «Seguir»…». «Seguir» pasa al paso 2 y, en el
    último paso, termina la sesión con los dos resultados registrados.

**Parte 2: repetir un paso (2026-11-06).**
- **Qué se repite.** Un reconocimiento o un ejercicio de práctica, cuando ya
  terminó (respondido, logrado o con el tiempo vencido) y mientras dura la
  pausa. Hay hasta 3 intentos (`MAX_STEP_ATTEMPTS`). Quien conduce pulsa
  «Repetir este paso» y el mismo paso empieza otra vez, con las mismas
  opciones. La pantalla de la persona vuelve a la pregunta, sin la respuesta
  anterior. El permiso se comprueba en FastAPI
  (`POST /guided-sessions/{id}/repeat`).
- **Qué se guarda.** Cada intento es un resultado propio (`attempt` 1, 2 o 3),
  y la sesión en curso guarda su intento (`guided_runs.step_attempt`). Lo hace
  la migración `20261106_39`. Al volver a la 38 se borran las repeticiones y
  queda el primer intento.
- **Decisión (revisable con Psicología).** Las métricas, las estadísticas, el
  reporte y la API móvil cuentan solo el primer intento: repetir no infla
  «logró». Las repeticiones se describen aparte, sin valorar:
  - al terminar, debajo de su primer intento («2.º intento · Respondió:
    Tristeza a los 11.2 s»);
  - en la línea de tiempo, después del resultado.

  La línea de tiempo empieza el paso en su primer intento. El contrato móvil
  no cambia: mostrar las repeticiones allí sería un campo opcional (4.5).
- **Verificación.**
  - Pruebas nuevas: `tests/integration/test_step_attempts.py` (12) y
    `web/tests/step_attempts.test.tsx` (5).
  - Las pruebas de las migraciones 28 y 31 aplican también la 39 a la tabla
    que recrean.
  - `tsc` sin errores; vitest, 301 pasaron; pytest, 1085 pasaron, 3 saltadas
    y 0 fallidas.
  - Migración 39 en PostgreSQL real (base desechable): upgrade, downgrade y
    upgrade otra vez, sin errores.
- **Navegador.** «Solo reconocer» v2, sin cámara:
  - se respondió mal el paso 1 y apareció «Repetir este paso»;
  - al repetir, el paso dijo «intento 2 de 3»; la persona volvió a ver las
    mismas opciones sin su elección y la consigna se leyó otra vez;
  - el paso 2 empezó en el intento 1;
  - el resumen final, la tabla de métricas (solo el primer intento) y la línea
    de tiempo del detalle mostraron lo esperado.
- **Limitación.** Con la pausa normal (unos segundos) «Repetir» se ve poco
  tiempo. Es cómoda con la pausa «esperar a quien conduce».

**Limitaciones.**
- La lectura automática depende de la voz del navegador. Algunos navegadores
  solo hablan después de que la persona tocó la pantalla al menos una vez.
- Dos ejercicios de práctica seguidos con la misma instrucción no se vuelven a
  leer solos; «Escuchar» solo existe en «¿Qué emoción es?».
- Sin cambios en Android.

## 15. Bloque 4: dibujo táctil en la web

**Integración separada (subtarea 4a).** Para que el dibujo sea un paso del
recorrido del participante, de un protocolo, hacen falta cambios estructurales:
- un tipo de paso nuevo, con su migración (restricciones de `protocol_steps`);
- el motor de la sesión guiada;
- el editor de protocolos y la vista de quien conduce;
- una tabla de resultados (emoción elegida y tiempos, nunca la imagen);
- las métricas, el reporte y el contrato móvil.

Por eso se hizo primero la actividad sola y la integración queda como subtarea.

**Qué hay ahora.**
- `/drawing` («Actividad de dibujo», enlazada desde el Analizador para Usuario
  y Docente): pantalla completa con el aspecto de la pantalla de la persona,
  sin menú y sin Emi. No crea una sesión, no usa la cámara y no registra nada.
- Consigna: «Dibuja una cara que muestre una emoción.», con «Escuchar».
- Al pulsar «Terminé»: «¿Qué emoción quisiste dibujar?», con pictograma y
  nombre. Después, «Dibujaste alegría.» en color neutro y «Dibujar otra vez».
  El dibujo no se clasifica ni se compara con la emoción elegida.
- Herramientas:
  - siete colores con nombre y tres grosores; lo elegido se marca con borde y
    negrita, no solo con color;
  - borrador, deshacer y limpiar con confirmación;
  - «Lienzo más grande».
- Tacto:
  - eventos de puntero (dedo, lápiz y ratón) y `touch-action: none`;
  - `touchmove` bloqueado en el lienzo para Safari antiguo, sin menú de
    pulsación larga;
  - solo dibuja el primer dedo, así que la palma o un segundo dedo no dibujan.
- Pantalla: los trazos se guardan relativos al lienzo, así que el dibujo se
  adapta al girar la pantalla o cambiar de tamaño. En un teléfono el lienzo va
  primero y las herramientas debajo.
- Salida accidental: con un dibujo en pantalla, salir dentro de la aplicación
  pide confirmación («el dibujo se borra»), y cerrar o recargar la pestaña
  muestra el aviso del navegador.

**Cuándo se borra el dibujo.** Vive solo en la memoria de la pantalla (trazos en
el estado de React y el lienzo). Se borra:
- al limpiar;
- al pulsar «Dibujar otra vez»;
- al salir de la pantalla, recargarla o cerrarla (al salir también se vacía el
  lienzo).

No se envía al servidor, no se guarda en el navegador (ni localStorage ni
sessionStorage) y no se exporta como imagen. Hay un tope de 40 000 puntos por
dibujo para que la memoria no crezca sin límite.

**Verificación.**
- Pruebas:
  - `web/tests/drawing.test.tsx` (12): trazos y escala, deshacer, limpiar con
    confirmación, colores, grosor y borrador, segundo dedo ignorado, bloqueo
    del desplazamiento, terminar, elegir y dibujar otra vez sin `fetch` ni
    almacenamiento, tope de puntos y confirmación al salir;
  - `assistant.test.tsx`: Emi no aparece en `/drawing`.
- `tsc` sin errores; vitest, 314 pasaron; pytest (sin cambios de backend),
  1085 pasaron, 3 saltadas y 0 fallidas.
- Navegador, con tamaño de teléfono (375 × 812) y de tableta (768 × 1024):
  - `touch-action: none` y sin desplazamiento horizontal;
  - trazos táctiles simulados (`pointerType: touch`) quedan bajo el dedo y un
    segundo dedo no dibuja;
  - se dibujó una cara arrastrando;
  - el color rojo, el borrador (quitó solo el tramo), deshacer dos veces,
    limpiar con confirmación, el cambio a tableta (el dibujo se reescaló),
    terminar, elegir, dibujar otra vez (lienzo vacío) y salir con
    confirmación;
  - solo hubo peticiones GET de la aplicación.

**Limitaciones.**
- No se probó en un teléfono o tableta físicos, solo con la emulación del
  navegador y eventos táctiles simulados.
- «Volver» dentro de la aplicación pasa por la misma confirmación. El texto del
  aviso al cerrar o recargar la pestaña lo decide el navegador.

### Subtarea 4a: el dibujo como paso de un protocolo

**Qué cambió.**
- Tipo de paso `drawing`: sin imagen, sin expresión pedida y sin opciones que
  configurar; solo el tiempo para dibujar (90 s por defecto, 120 s con modo
  accesible). No usa la cámara: un protocolo solo de dibujos y reconocimientos
  se aplica sin calibración.
- Editor de protocolos: «Agregar dibujo».
- Pantalla de la persona: la misma actividad de `/drawing`. Al elegir la emoción
  solo se envía su clave (por el mismo `POST .../answer` del reconocimiento).
  Sin «Dibujar otra vez»: repetir lo decide quien conduce. Con un dibujo en
  pantalla, cerrar o recargar pide confirmación.
- Quien conduce: «Paso n · dibujo». Puede registrar la emoción que la persona
  señaló o dijo, seguir, repetir (hasta 3 intentos) o saltar. No ve el dibujo.
- Registro mínimo (`drawing_results`, migración 20261106_40):
  - la emoción elegida, cómo terminó el paso, quién respondió, los tiempos y
    el intento;
  - nunca el dibujo, ni trazos ni imagen;
  - entra en la eliminación y la retención por sesión.
- Métricas, reporte y línea de tiempo: «Señaló una emoción en 1 de 2 dibujos.»,
  con el aviso de que EMOtv no ve ni interpreta los dibujos. No hay respuesta
  correcta: no se compara con nada. Las estadísticas agregadas no cambian.
- Contrato móvil 4.5: solo campos opcionales (`metrics.drawing` y `kind`
  `drawing` en la línea de tiempo, que es una enumeración abierta).

**Cuándo se borra el dibujo en una sesión.** Al terminar el paso (cuando la
pantalla pasa al siguiente), al empezar otro intento, al terminar la sesión o
al cerrar o recargar la pantalla. Durante la pausa tras responder sigue visible,
bloqueado.

**Verificación.**
- `tests/integration/test_drawing_steps.py` (12): dominio, armado del protocolo,
  respuesta de la persona y de quien conduce, tiempo vencido, repetir, saltar,
  detener, métricas, línea de tiempo, eliminación y migración (bajar y subir).
- `web/tests/drawing_steps.test.tsx` (8): editor, pantalla de la persona (solo
  se envía la emoción, sin cuadros ni almacenamiento), tiempo vencido,
  confirmación al cerrar, quien conduce, métricas y línea de tiempo.
- Migración 40 en PostgreSQL (base desechable): subir, bajar y subir sin errores.
- Navegador, con la pantalla de la persona a tamaño de teléfono:
  - se creó el protocolo «Dibujo 4a» en el editor y el Analizador lo mostró
    como «1 dibujo. No usa la cámara.»;
  - se dibujó una cara con toques simulados, se eligió «Alegría» y la pantalla
    dijo «Dibujaste alegría.»;
  - la pantalla de la persona solo envió `POST .../answer`, sin cuadros ni el
    dibujo;
  - quien conduce vio «Paso 1 · Respondió: Alegría»;
  - el detalle de la sesión mostró el bloque «Dibujos» y, en la línea de
    tiempo, «Dibujo: señaló alegría».

**Pendiente.** Probarlo en un teléfono o una tableta físicos. Si el protocolo no
tiene imágenes, el detalle de la sesión igual muestra el título «Métricas por
imagen» sobre el bloque de dibujos; ese título ya existía y no se cambió.

## 16. Bloque 5: juego de emparejar

**Qué cambió.** Un paso nuevo de protocolo, «Juego: empareja la emoción»
(`kind` `game`, `game_type` `matching`). En cada ronda la persona ve una imagen
del banco y elige con botones el nombre de su emoción (con pictograma si el
apoyo está activo); no hay que arrastrar.

- Dificultad en el editor: rondas (2 a 6, por defecto 3), opciones por ronda
  (2 a 4, por defecto 2) y tiempo por ronda.
- Si elige otra emoción: «Mira otra vez la cara. Puedes pedir ayuda.». Tras
  dos, se le muestra la emoción con su explicación educativa.
- «Ayuda» quita una opción y lee la pregunta; «Escuchar» repite el texto.
- Quien conduce puede responder, dar la ayuda, pasar de ronda, saltar el juego
  o repetirlo (cuenta el primer intento). La sesión se puede detener siempre.
- Sin puntaje, ranking ni penalización: el registro dice, por ejemplo, «Jugó
  3 de 3 rondas. Emparejó 2 imágenes, 1 a la primera; usó la ayuda 1 vez.».
- No usa la cámara: durante el juego no se envían cuadros.

**Desvíos del diagnóstico.**

- El resultado va en la tabla `game_results`, con contadores, en vez de un
  `ActivityResult` genérico. Así no se guardan listas que crezcan.
- Las imágenes las elige EMOtv al guardar el protocolo: imágenes emocionales
  aprobadas (y «Para niños» si corresponde), de emociones distintas. Si no
  alcanzan, el protocolo no se guarda y se dice cuántas faltan.

**Comprobado.**

- Pruebas: `tests/integration/test_matching_game.py` (14) y
  `web/tests/matching_game.test.tsx` (7).
- La migración 41 se aplicó, se revirtió y se volvió a aplicar en la base
  desechable.
- Recorrido en el navegador (sesión S-82ZWDR, para niños, 3 rondas y 3
  opciones), con error, ayuda, emoción mostrada, ronda pasada por quien
  conduce y fin. La pantalla de la persona solo envió `POST .../game`.
- La suite completa falló al principio. Las columnas JSON nuevas guardaban
  `None` como `null` de JSON, y las restricciones rechazaban los pasos que no
  son juego. Se corrigió con `none_as_null` y una prueba de un protocolo mixto.
  El recorrido usó un protocolo con solo el juego.

**Pendiente.**

- Probar en un teléfono o una tableta físicos.
- Si se borra del todo una imagen que solo usa un juego, el protocolo no la
  protege: queda marcado como «necesita imagen».
- `list_current_using` aún no ve las imágenes de los juegos.
- Que Psicología revise los textos del juego.

## 17. Bloque 6: busca la misma emoción

**Qué cambió.** Un segundo juego en el mismo paso y el mismo motor que el de
emparejar (`kind` `game`, `game_type` `similar`). No hay un motor aparte: la
ayuda, la repetición, el tiempo, la parada y los contadores son los mismos.
Arriba se ve una cara modelo; abajo, botones con caras («Cara 1», «Cara 2»…).
La persona toca la que muestra la misma emoción.

- Las opciones no dicen su emoción ni llevan pictograma: eso daría la
  respuesta. La emoción se nombra al terminar la ronda, con su explicación.
- Dificultad en el editor: rondas (2 a 6) y caras para elegir (2 a 4).
- Quien conduce ve la emoción de cada cara («Cara 2 (Alegría)») y puede
  registrar la que la persona señaló.
- Si la persona ya pidió ayuda, el reintento ya no se la ofrece (también en el
  juego de emparejar).

**Imágenes: cómo se evita resolver por identidad visual.** EMOtv las elige al
guardar el protocolo, del banco aprobado (y «Para niños» si corresponde).

- La pareja nunca es la misma imagen: ni el mismo identificador, ni el mismo
  archivo, ni una copia recodificada o con otro tamaño. Se compara una
  miniatura en color de 16 × 16 (`stimulus_appearance`, en infraestructura).
  Con el banco inicial, una copia difiere en menos de 1 (de 0 a 255); la misma
  emoción en otra variante, en 28 o más. El corte es 8.
- La pareja es la imagen de esa emoción que menos se parece a la modelo. Las
  otras caras son de emociones distintas y se eligen entre las que más se le
  parecen. Si la pareja quedara como la opción más parecida, la ronda no se
  usa. Así el parecido apunta a una opción equivocada y solo la emoción lleva a
  la respuesta.
- La miniatura compara colores y composición; no estima la expresión ni
  reconoce a nadie. No detecta una copia recortada o reflejada.

**Lo que no se comprueba.** La emoción de cada imagen es la que indicó quien la
subió y aprobó el docente. EMOtv no comprueba que la imagen la muestre, y el
material no fue validado por especialistas.

**Material disponible.** Cada ronda necesita dos imágenes distintas de una
emoción y una de otra emoción por cada cara restante.

- El banco inicial tiene 6 emociones con 3 variantes cada una. Eso alcanza para
  6 rondas de emociones distintas, con hasta 4 caras.
- No tiene «cara tranquila»: con solo el banco inicial, esa emoción no aparece.
- Si el banco no alcanza, el protocolo no se guarda y el mensaje dice para
  cuántas rondas alcanza.

**Comprobado.**

- Pruebas: `tests/integration/test_similar_game.py` (13) y
  `web/tests/similar_game.test.tsx` (4).
- La migración 42 se aplicó, se revirtió y se volvió a aplicar en PostgreSQL.
- Recorrido en el navegador (sesión S-53ZMK2, para niños, 3 rondas y 3 caras,
  con los 18 dibujos del banco inicial subidos como prueba):
  - en cada ronda, la pareja se veía distinta de la modelo y las otras caras se
    le parecían más;
  - en la ronda 1 se pidió ayuda, se eligió una cara de otra emoción y después
    la correcta;
  - en la ronda 2 se mostró la pareja tras dos errores;
  - en la ronda 3 terminó el tiempo y se registró «Jugó 2 de 3 rondas».
  - La pantalla de la persona solo envió `POST .../game` y pidió las imágenes.

**Pendiente.**

- Probarlo en un teléfono o una tableta físicos, y con niños, bajo la revisión
  de Psicología.
- Que Psicología revise si las imágenes del banco muestran con claridad su
  emoción.
- Mismos pendientes del §16 sobre imágenes de juegos borradas del todo.

## 18. Bloque 7: resultados educativos

**Qué muestra.** El detalle de la sesión, el reporte, su impresión y el
aplicativo móvil abren con «Resultados educativos». Es un resumen por tipo de
actividad:

- reconocimiento;
- dibujo: cuántos se completaron y qué emoción se señaló;
- juegos: rondas, emparejadas, ayudas e intentos, contando las repeticiones;
- práctica facial;
- actividades omitidas, interrumpidas o que no llegaron a aplicarse, con su
  paso.

Lleva un aviso fijo: no es un puntaje, no compara con otras sesiones y no
permite concluir nada sobre la persona.

Las estadísticas agregan dos secciones, «Dibujos» y «Juegos». Las dos cuentan
sesiones; no hay filas por persona.

**Cómo se calcula.**

- Al leer, de las tablas que ya existían: no hay migración ni copia guardada.
  Por eso el reporte, el detalle y el móvil dicen lo mismo.
- Las sesiones antiguas, o sin actividades, se leen igual que antes: sin el
  resumen.
- Del dibujo solo se guarda la emoción señalada y los tiempos. El servidor
  rechaza cualquier otro campo.
- Los permisos son los de siempre: quien condujo y su docente. Ni otro docente,
  ni `admin`, ni `superadmin`.

**Comprobado.** Pruebas: `tests/integration/test_educational_results.py` (9) y
`web/tests/educational_results.test.tsx` (5). Cubren:

- una sesión con todos los tipos, una omisión, una interrupción y un paso sin
  aplicar;
- que el reporte coincida con las métricas y con el móvil;
- permisos, sesiones antiguas, persistencia y estadísticas.

**Pendiente.** Que Psicología revise la redacción de las frases del resumen.

## 19. Bloque 8: Android como pantalla de la persona

**Cómo se vincula.**

- Quien conduce pulsa «Vincular Android» en la web. Recibe un código de 8
  caracteres que sirve una vez y vence a los 5 minutos.
- El aplicativo lo canjea sin iniciar sesión por el enlace de la pantalla de la
  persona: es el mismo mecanismo que el enlace web.
- Desde ese momento, la web informa que la pantalla está en Android.

**Reglas.**

- El enlace solo abre la pantalla de esa sesión. No sirve para sesiones,
  reportes ni estadísticas.
- Un código o un enlace nuevo invalida el anterior.
- Al terminar o detener la sesión, el enlace se cierra.
- Para reconectarse se usa el mismo enlace.
- Una respuesta repetida responde `409` y no se cuenta dos veces.
- Los códigos equivocados se limitan por red.
- Solo se vinculan sesiones sin cámara, o en las que se siguió sin cámara.
  Android nunca envía imágenes.
- No se registra a la persona. La consulta y la revisión docente no cambian.

**Datos.** La migración 43 agrega tres columnas a `guided_runs`: el SHA-256
del código, su vencimiento y el dispositivo (`web` o `android`). El código en
claro no se guarda.

**Comprobado.** Pruebas: `tests/integration/test_android_participation.py`
(14) y `web/tests/android_screen.test.tsx` (3).

**Pendiente.**

- Los dos juegos llegaron a Android en los bloques 10A y 10B (§21 y §22).
- La migración 43 en PostgreSQL y una prueba con un dispositivo real.

## 20. Bloque 9: dibujo táctil en Android

Está en el repositorio `EMOtv-android` (Kotlin y Compose), dentro de la
pantalla de la persona. Esa pantalla también se completó ahí: se abre desde el
inicio de sesión sin iniciar sesión, se escribe el código y se ve la actividad.

**Igual que la web.**

- Herramientas: siete colores con nombre, tres grosores, borrador, deshacer,
  limpiar con confirmación, «Terminé» y después elegir la emoción.
- Dibuja un solo dedo y hay un tope de 40.000 puntos.
- Repetir lo decide quien conduce: un `round` nuevo empieza un lienzo vacío.

**Ciclo de vida.**

- El dibujo vive en el `ViewModel`: sobrevive al giro de la pantalla y al
  segundo plano.
- Nunca se guarda en disco ni en el estado guardado del sistema.
- En segundo plano no se consulta al servidor; al volver se reconecta con el
  mismo enlace.
- Salir con un dibujo en pantalla pide confirmación.

**Política de datos temporales** (la misma que la web). El dibujo se borra en
estos casos:

- al terminar el paso, por respuesta o por tiempo;
- al empezar otro intento;
- al pasar a otra actividad;
- al terminar o detener la sesión;
- al salir;
- cuando el sistema destruye la pantalla.

**Privacidad.**

- Solo se envía `{"expression"}`. Un `409` se toma como ya recibida, así un
  reintento tras un corte no duplica la respuesta.
- No se usa la cámara y los juegos no cambian.
- `FLAG_SECURE` en la versión final.
- El cliente HTTP de la persona no lleva el token de la cuenta.

**Comprobado.** 21 pruebas unitarias nuevas (`DrawingBoardTest` y
`ParticipationViewModelTest`), `lintDebug` y `assembleDebug`.

**Pendiente.** Probarlo con niños, bajo la revisión de Psicología.

## 21. Bloque 10A: juego de emparejar en Android

Está en `EMOtv-android`, dentro de la pantalla de la persona. El servidor y la
web no cambian: Android usa las mismas rutas que la pantalla web.

**Igual que la web.**

- La imagen de la ronda, «Ronda N de M» y un botón por emoción, sin arrastrar.
- Si elige otra, se invita a mirar otra vez; tras dos, se muestra cuál es con su
  explicación.
- «Ayuda» quita una opción una vez por ronda.
- «Siguiente» y «Terminar el juego».
- Pictogramas si el protocolo los pide.
- Sin puntaje.

Las reglas las aplica el servidor; Android solo muestra su estado.

**TalkBack.**

- Cada botón se lee con el nombre de la emoción y su estado («No disponible»,
  «Es esta»). El pictograma y la marca «✓ Es esta» no se leen dos veces.
- La imagen se anuncia como «Cara de la ronda».
- Lo que pasó en la ronda está en una región viva.

**Reconexión y duplicados.**

- No se envía una acción mientras otra va en camino.
- Si se pierde la respuesta y la persona toca otra vez, el servidor responde
  `409` o `422` sin registrar nada; Android vuelve a leer el estado.
- Sin conexión, se reintenta con el mismo enlace y la ronda sigue igual.

**Privacidad.** La imagen de la ronda es un estímulo, solo en memoria: se borra
al cambiar de ronda, al terminar y al salir. Sin cámara.

**Comprobado.** Pruebas unitarias (`MatchingGameViewModelTest`, con un servidor
falso que aplica las reglas del juego web), pruebas en el teléfono
(`MatchingGameScreenTest`), `lintDebug` y `assembleDebug`.

**Pendiente.** Probarlo con niños, bajo la revisión de Psicología. La lectura en voz alta (apoyo `read_aloud`) aún no está
en Android.

## 22. Bloque 10B: «Busca la misma emoción» en Android

Reutiliza la estructura del juego de emparejar (§21): el mismo paso, la misma
pantalla y las mismas acciones. El servidor y la web no cambian.

**Igual que la web.**

- La cara modelo arriba y un botón con cada cara («Cara 1», «Cara 2»…), sin
  decir su emoción ni mostrar pictogramas.
- Si elige otra, se invita a mirar otra vez; tras dos, se muestra la pareja con
  su explicación.
- «Ayuda» quita una cara una vez por ronda.
- «Siguiente» y «Terminar el juego».

**TalkBack.** La modelo se anuncia como «Cara de arriba, la que hay que
comparar». Cada botón se lee «Cara 1» con su estado; la imagen de la cara no se
anuncia.

**Imágenes.** La modelo y cada cara se piden al cambiar la ronda, no en cada
consulta. Viven solo en memoria y se borran al cambiar de ronda, al terminar y al
salir. Son estímulos, nunca imágenes de personas.

**Finalización y resultados.** Al terminar la última ronda el paso se cierra y
sigue el siguiente. El resultado queda registrado como el del juego web:
rondas, emparejadas, a la primera, ayudas y respuestas de quien conduce (cero si
todo lo tocó la persona). Un toque repetido tras un corte no se registra dos
veces.

**Comprobado.**

- Servidor: una prueba juega las dos rondas con el enlace de Android y revisa el
  registro y la frase de las métricas
  (`test_busca_la_misma_emocion_desde_android_termina_y_registra_el_resultado`).
- Android: pruebas unitarias (`MatchingGameViewModelTest`) y en el teléfono
  (`SimilarGameScreenTest`).

**Pendiente.** Probarlo con niños, bajo la revisión de Psicología.
