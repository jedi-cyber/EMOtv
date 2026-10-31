# Práctica de producción de expresiones (diseño)

Estado: aprobado por el desarrollador el 2026-10-30. Sin mediana de segundos
en las estadísticas.

## 1. Propósito

Hoy un paso de la sesión guiada muestra una imagen y, a los
`capture_after_seconds`, guarda una captura de la expresión estimada; las
métricas la comparan con la `expected_expression` del estímulo. Esa comparación
es débil: ver una imagen triste no obliga a poner cara triste, y la coincidencia
no dice nada útil sobre la sesión. Se agrega un paso de otro tipo, la
**práctica de expresión**: la persona recibe una instrucción ("Muestra
alegría") y ve en tiempo real una señal simple que crece cuando su expresión
facial estimada se acerca a la pedida. En este paso, "coincidió con la pedida"
es exactamente lo que se quiere registrar.

El uso previsto es con niños y niñas a quienes les cuesta producir expresiones a
pedido o de forma legible (por ejemplo, dentro del espectro autista). Un Usuario
conduce la sesión desde la web bajo la supervisión de su Docente y con la
autorización escrita del tutor. Es una actividad guiada, no terapia ni
evaluación diagnóstica: el sistema describe qué ocurrió en cada ejercicio
("se logró la expresión pedida en 3 de 5 ejercicios") y nunca valora a la
persona ni promete efectos.

## 2. Modelo de datos

### Paso del protocolo

Se sigue la opción preferida: un `ProtocolStep` con tipo de paso. No hace falta
una entidad nueva de protocolo porque el editor, el versionado, el orden
(`position`), la validación por público y el avance por el reloj del servidor ya
funcionan sobre `ProtocolStep`.

```python
class StepKind(str, Enum):
    STIMULUS = "stimulus"   # el paso de hoy
    PRACTICE = "practice"   # práctica de expresión

@dataclass(frozen=True, slots=True)
class ProtocolStep:
    stimulus_id: str | None          # obligatorio en stimulus; opcional en practice (ilustración)
    exposure_seconds: int            # en practice: tiempo máximo del ejercicio
    capture_after_seconds: int       # en practice: siempre 0 (no hay captura automática)
    record_verbal_response: bool = False   # siempre False en practice
    shown_before_analyzer: bool = False    # siempre False en practice
    kind: StepKind = StepKind.STIMULUS
    target_expression: str | None = None   # solo practice; una de PRACTICE_TARGETS
    hold_seconds: int | None = None        # solo practice; 1..10 y menor que exposure_seconds
```

Reglas del dominio (en `ProtocolStep.__post_init__`):

- `stimulus` exige `stimulus_id` y no admite `target_expression` ni
  `hold_seconds` (las filas existentes siguen igual).
- `practice` exige `target_expression` y `hold_seconds`;
  `exposure_seconds` entre `hold_seconds + 1` y 120 (predeterminado 20);
  `capture_after_seconds = 0`; no lleva respuesta verbal ni va antes del
  analizador (necesita la cámara y la calibración).
- La ilustración (`stimulus_id`) es opcional; si existe debe ser un estímulo
  `usable` (creación propia o con licencia; las imágenes propias ya pasan por la
  detección de personas y la revisión del docente) y, en un protocolo para
  niños, `suitable_for_children`. Su `expected_expression` no se usa.
- `PRACTICE_TARGETS`: `happiness`, `surprise`, `sadness`,
  `anger`, `fear`, `disgust` y `neutral`. Se excluye `contempt`: es
  difícil de pedir a un niño y los dos modelos la estiman con poca
  frecuencia, así que casi nunca se lograría.
- `Protocol`: el mínimo de pasos sigue siendo 1 y el máximo 30, sumando ambos
  tipos. Un protocolo puede tener solo pasos de práctica. Los exámenes siguen
  sin pasos.

Migración nueva (`20261030_28_practice_steps.py`, sin editar las existentes):

- `protocol_steps.kind` `String(16)` `NOT NULL DEFAULT 'stimulus'`, con check.
- `protocol_steps.stimulus_id` pasa a admitir nulo; check
  `kind = 'practice' OR stimulus_id IS NOT NULL`.
- `protocol_steps.target_expression` `String(32)` nulo y
  `hold_seconds` `Integer` nulo; check de que existan juntos solo en `practice`.
- La restricción `ck_protocol_steps_capture` sigue valiendo (0 ≤ 0 ≤ exposición).

### Resultado de un ejercicio

Se usa una tabla nueva `practice_results` (una fila por paso de
práctica y sesión) en lugar de escribir el resultado dentro de
`guided_runs.steps_log` (JSON). Motivos: las métricas, el reporte y las
estadísticas lo consultan por columna; la eliminación con acta cuenta filas
por tabla (`postgres_privacy_repositories.py`) y la retención funciona por
`ON DELETE CASCADE` desde `sessions`, igual que `expression_captures`.

```python
@dataclass(frozen=True, slots=True)
class PracticeResult:
    id: str
    session_id: str
    step_index: int
    target_expression: str
    outcome: PracticeOutcome      # achieved | timed_out | skipped | stopped
    seconds_to_achieve: float | None   # solo si achieved
    peak_level: float             # 0..1, nivel máximo del ejercicio
    relative_to_calibration: bool # el nivel se calculó respecto de la base neutral
    feedback_visible: bool        # la señal estuvo visible todo el ejercicio
    analyzed_frames: int          # cuadros con rostro que actualizaron el nivel
    flagged_frames: int           # cuadros sin rostro o con problemas de calidad
    emotion_model_id: str
    emotion_model_version: str
    started_at: datetime
    ended_at: datetime
```

Restricción única `(session_id, step_index)`. Los pasos de práctica **no** crean
filas en `expression_captures` (ver §4).

## 3. Algoritmo en vivo

Todo vive en memoria, en el `_Live` de la sesión, como la calibración. Un
`PracticeTracker` por ejercicio en curso, con estado de tamaño fijo:
`level`, `last_at`, `peak`, `above_since`, `achieved_at`, `analyzed`,
`flagged`. Nunca una lista de cuadros.

Por cada cuadro del ejercicio (ver §6 para la carga):

1. Se analiza con `GuidedFrameAnalyzer.assess` (detección YuNet, calidad,
   modelo local) y la imagen se descarta.
2. Si el cuadro no tiene rostro o tiene un problema de calidad: `flagged += 1`,
   el nivel **no se actualiza** y se reinicia el tiempo de sostén
   (`above_since = None`). Así una cara fuera de cuadro no cuenta como logro ni
   baja el nivel de golpe.
3. Probabilidad de la expresión pedida: `p = distribution[target]`.
4. Valor relativo a la base neutral, cuando existe calibración en memoria y la
   expresión pedida no es `neutral`:
   `x = clamp((p - base[target]) / (1 - base[target]), 0, 1)`.
   Si la base se perdió (reinicio del servidor) o se pide `neutral`, `x = p`, y
   el resultado guarda `relative_to_calibration = False`. En el caso
   `neutral`, respecto de una base neutral el aumento sería casi cero, por eso se
   usa la probabilidad directa.
5. Promedio móvil exponencial ajustado al tiempo real entre cuadros, para que un
   cuadro perdido no cambie el ritmo de la señal:
   `alpha = 1 - exp(-dt / TAU)`, `level += alpha * (x - level)`, con
   `TAU = 0.8 s` y `dt` acotado a 2 s. `peak = max(peak, level)`.
6. Umbral con histéresis: `PRACTICE_THRESHOLD = 0.6`. Si
   `level ≥ 0.6` y `above_since` es nulo, `above_since = ahora`; si
   `level < 0.55`, `above_since = None`. Las constantes van en
   `domain/guided_session.py`, junto a las del examen; no se piden en el editor.
7. Logro: `ahora - above_since ≥ hold_seconds`.

Al **lograrlo**: se guarda el `PracticeResult` con `outcome = achieved`,
`seconds_to_achieve` (desde el inicio del ejercicio hasta el momento del logro,
no hasta que empezó el sostén), `peak_level` y los contadores. La pantalla
muestra "¡Lo lograste!" durante `PRACTICE_SUCCESS_SECONDS = 2` y el paso avanza
solo (se registra en `steps_log` como hoy). En esos 2 s no se analizan más
cuadros.

Al **vencer el tiempo** (`exposure_seconds` sin logro, detectado por `_tick`
aunque no lleguen cuadros): `outcome = timed_out`, `seconds_to_achieve = None`,
`peak_level` y contadores. La pantalla pasa al siguiente paso sin un mensaje de
fracaso. **Saltar** guarda `skipped`; **parar** la sesión guarda `stopped` para el
ejercicio en curso.

Lo que se muestra se calcula con el mismo `level`, redondeado a dos decimales.

## 4. Qué se guarda y qué nunca se guarda

Por cada ejercicio, en `practice_results`: expresión pedida, resultado (logrado,
venció el tiempo, saltado, detenido), segundos hasta lograrlo, nivel máximo, si
fue relativo a la calibración, si la señal estuvo visible todo el ejercicio,
cuadros analizados y marcados, modelo y versión, inicio y fin. En `steps_log`, el
inicio y el fin del paso, como hoy.

Nunca se guarda: ninguna imagen ni cuadro, ninguna lista de niveles o de
probabilidades por cuadro, la distribución de cada cuadro, la base neutral, ni
la serie del nivel para dibujarla después. La línea de tiempo muestra el
ejercicio como un tramo con su resultado, no como una curva. El nivel en vivo
no sale del servidor salvo hacia las dos pantallas de esa sesión.

## 5. Cambios por pantalla y por contrato

**Vista de la persona (`ParticipantViewPage`).** En un paso de práctica muestra
solo: la instrucción ("Muestra alegría", con el nombre en español del catálogo
de expresiones), la ilustración si existe, una barra de nivel de 0 a 1 sin
números ni colores que valoren, y "¡Lo lograste!" al lograrlo. Si el conductor
apagó la señal, no hay barra: solo la instrucción. Nunca la expresión
detectada, probabilidades ni calidad. `ParticipantView` agrega
`practice: {instruction, level | null, achieved} | null`; `level` es nulo con la
señal apagada. La imagen de la ilustración usa la ruta de estímulo existente.

**Vista del conductor (`GuidedConductorPage`).** En un ejercicio: "Ejercicio N
de M · Expresión pedida: alegría", tiempo restante, el mismo nivel que ve la
persona, un aviso de calidad cuando no se ve el rostro (con los textos de
`issueNames`), el interruptor "Mostrar la señal a la persona" y "Saltar este
ejercicio". Al terminar, el resultado en lenguaje descriptivo. Con público
infantil, el aviso de limitación de §9. Nueva ruta
`POST /guided-sessions/{id}/practice-feedback` `{visible: bool}` (solo quien
conduce; se aplica en FastAPI). El estado se guarda en una columna nueva
`guided_runs.practice_feedback` (por defecto `true`) para que sobreviva a un
reinicio. El interruptor vale para toda la sesión (no por
ejercicio) y, si cambia a mitad de un ejercicio, ese ejercicio queda con
`feedback_visible = False`.

**Editor de protocolos (`ProtocolsPage`).** "Agregar imagen" y "Agregar
ejercicio de práctica". Un ejercicio pide: expresión pedida (lista de
`PRACTICE_TARGETS`), segundos para sostenerla (predeterminado 2), tiempo máximo
(predeterminado 20) e ilustración opcional del banco. La API
(`stimulus_router.py`, `ProtocolStepRequest`) agrega `kind`,
`target_expression` y `hold_seconds`. Un protocolo para niños solo acepta
ilustraciones "Para niños".

**Métricas (`session_metrics.py`).** `stimulus_metrics` salta los pasos de
práctica en `emotional[]` y `abstract[]` (la coincidencia con la esperada no
cambia) y agrega `practice[]` (por ejercicio: `step_index`, `target_expression`,
`outcome`, `seconds_to_achieve`, `peak_level`, `feedback_visible`) y
`totals.practice_exercises`, `totals.practice_achieved`,
`totals.practice_sentence`: "Se logró la expresión pedida en 3 de 5
ejercicios." (los saltados no cuentan en el total; se informan aparte).

**Línea de tiempo (`session_insights_service.py`).** El carril `stimuli` muestra
el ejercicio con `kind = "practice"` y título "Práctica: alegría"; un carril
nuevo `practice` con `start`, `end`, `target_expression` y `outcome`.

**Detalle y reporte (`SessionDetailPage`, `SessionReportPage`,
`web/src/insights`).** Componente nuevo `PracticeMetrics.tsx`: tabla por
ejercicio y la frase de totales. El reporte ya incrusta `metrics` y `timeline`,
así que recibe la práctica sin cambiar `report_service.py`, salvo el aviso de
limitación con niños.

**Estadísticas (`session_statistics_service.py`, `StatisticsPage`).** Bloque
nuevo `practice`: por expresión pedida, ejercicios, logrados y sesiones en las
que se aplicó, más el total. Cuenta ejercicios y sesiones, nunca personas;
no calcula puntajes ni promedios por persona. No incluye la mediana de
segundos hasta lograrlo.

**Contrato móvil (`docs/mobile-api.md`).** Revisión 5, **compatible**: solo campos
nuevos de lectura (`Metrics.practice[]`, `Metrics.totals.practice_*`,
`Timeline.lanes.practice[]`, `Statistics.practice`) y el valor `practice` en la
enumeración abierta `kind`. Enumeración nueva `practice_outcome` (abierta). No
sube `MOBILE_MIN_APP_VERSION`. El aplicativo sigue sin conducir sesiones ni
enviar imágenes.

## 6. Carga

Hoy la pantalla de la persona envía un cuadro cada `FRAME_INTERVAL_MS = 500` ms
mientras `capture_frames` es verdadero, pero en `STIMULI` el servidor solo
analiza los cuadros a partir de `next_capture_due` y hasta lograr una captura
buena: uno o pocos por imagen. Los demás se decodifican y se descartan sin
pasar por el modelo. La práctica, en cambio, analiza cada cuadro del ejercicio
(2 por segundo), igual que la calibración y la fase `EXAM`.

Hallazgo: `POST /participant-view/{token}/frames` usa `run_in_threadpool` y
**no pasa por `AnalysisCapacity`**. Por eso hoy `MAX_CONCURRENT_ANALYSES` no limita
los cuadros de las sesiones guiadas ni de las estaciones de examen (solo el
WebSocket del Analizador). Además, el navegador envía con `setInterval` sin
esperar la respuesta anterior, y un servidor lento acumula peticiones.

Propuesta:

1. `create_guided_router` recibe `analysis_capacity` y el análisis del cuadro
   corre en `capacity.run(...)`, en el mismo pool que el Analizador. Así un solo
   límite cubre prácticas, estaciones y lectura en vivo.
2. Si no hay cupo, el cuadro **se descarta** (sin esperar los 5 s de
   `busy_wait_seconds`) y la respuesta sigue siendo `{"received": true}`: la
   persona no recibe ningún resultado ni error. Un intento sin bloqueo en
   `AnalysisCapacity` (`try_run`). El descarte vale también
   para el examen: hoy los medios segundos sin cuadro ya se guardan marcados
   (`EXAM_GAP_SECONDS`), así que el registro muestra el hueco en vez de
   retrasarse.
3. `ParticipantViewPage` envía un cuadro solo cuando terminó el anterior (un
   cuadro en vuelo por pantalla). La demanda máxima es entonces una petición por
   pantalla que captura, y el EMA ajustado por `dt` tolera los cuadros perdidos.
4. El servidor solo analiza cuando la fase lo necesita: en `STIMULI` de imagen
   sigue analizando solo al capturar; en práctica, todos los cuadros; en los 2 s
   de "¡Lo lograste!", ninguno.
5. Hardware mínimo (i7-3770, 4 núcleos y 8 hilos, 4 GB, sin GPU útil): fijar
   `MAX_CONCURRENT_ANALYSES=3` y `ONNX_THREADS_PER_SESSION=1` en ese equipo (el
   valor por defecto, núcleos lógicos − 1 = 7, satura los 4 núcleos físicos).
   El modelo se carga una sola vez por proceso (`_assessors` por modelo), así que
   la memoria no crece con las sesiones. La capacidad real (cuántas pantallas a
   2 cuadros por segundo caben sin descartes) se medirá con una prueba de carga
   en ese equipo, con estaciones de examen y prácticas simultáneas, y se anotará
   en `docs/testing/`. No se dan cifras antes de medir.
6. Opcional, si la medición lo pide: la práctica puede enviar 320×240 en lugar
   de 640×480 (el control de calidad usa proporciones, no píxeles).

## 7. Convivencia con las fases actuales

No se agrega ninguna fase. Un ejercicio de práctica es un paso dentro de
`STIMULI`: `_tick` y `_receive` ramifican por `step.kind`.

- `PRE_QUESTIONNAIRE`, `POST_QUESTIONNAIRE`, `CALIBRATION`: sin cambios. La
  calibración ya ocurre antes de `STIMULI`, así que la práctica siempre la tiene,
  salvo tras un reinicio del servidor (§3, paso 4).
- `BEFORE_ANALYZER`: no admite pasos de práctica (lo valida el dominio).
- `STIMULI` con pasos de imagen: mismo código y mismas capturas; los pasos de
  imagen y de práctica pueden alternarse en un protocolo.
- `LIVE` (sin protocolo): sin pasos, sin práctica. Sin cambios.
- `WAITING`, `READY`, `EXAM`: un examen no tiene pasos (`Protocol` lo impide),
  así que nunca llega a la rama de práctica. El único cambio común es el cupo de
  análisis de §6, que no cambia lo que se guarda en el examen.
- `FINISHED`, `STOPPED`: al parar con un ejercicio en curso se guarda
  `outcome = stopped`.
- El Analizador por WebSocket y la actividad de posturas no cambian.
- Cuerpo: la práctica usa solo la cara; no se infiere nada desde la postura.

## 8. Archivos por prompt (propuesta)

La división en prompts es mía, a partir de los puntos de este documento; se
ajusta a S2–S9 cuando los vea.

| Prompt | Contenido | Archivos |
| --- | --- | --- |
| S2 | Dominio y esquema de pasos | `domain/protocol.py`, `domain/guided_session.py` (constantes, `PracticeResult`, `PracticeOutcome`), `infrastructure/persistence/models.py`, `postgres_*protocol*`, migración `..._28_practice_steps.py`, `interfaces/web/stimulus_router.py`, pruebas de dominio y repositorio |
| S3 | Algoritmo puro | `application/practice_tracker.py` (nuevo) y sus pruebas con reloj falso |
| S4 | Integración en la sesión guiada | `application/guided_session_service.py`, repositorio guiado, tabla `practice_results` y columna `guided_runs.practice_feedback` (migración `..._29_practice_results.py`), `postgres_privacy_repositories.py` (acta), `interfaces/web/guided_router.py` (`ParticipantView.practice`, `practice-feedback`) |
| S5 | Carga | `interfaces/web/analysis_capacity.py` (`try_run`), `guided_router.py`, `app.py`, `ParticipantViewPage.tsx` (un cuadro en vuelo), pruebas |
| S6 | Editor de protocolos | `web/src/pages/ProtocolsPage.tsx`, `web/src/api/types.ts`, pruebas vitest |
| S7 | Pantallas de la sesión | `ParticipantViewPage.tsx`, `GuidedConductorPage.tsx`, CSS, pruebas vitest |
| S8 | Métricas, línea de tiempo, reporte y estadísticas | `session_metrics.py`, `session_insights_service.py`, `session_statistics_service.py`, `report_service.py` (aviso), `web/src/insights/PracticeMetrics.tsx`, `SessionDetailPage.tsx`, `SessionReportPage.tsx`, `StatisticsPage.tsx` |
| S9 | Documentación y contrato | `docs/mobile-api.md` (revisión 5), `docs/privacy/` (registro de tratamiento, guía de uso), `docs/testing/manual-checklist.md`, `docs/thesis-evidence/README.md`, este documento |
| A1 | Android (`EMOtv-android`) | Mostrar `practice[]`, la frase de totales, el carril de práctica y `Statistics.practice`; tolerar `kind = practice` |

## 9. Riesgos

**Precisión con rostros de niños.** FER+ se entrenó con FER2013 y HSEmotion con
AffectNet: en su mayoría rostros de adultos. Con niños, y más con expresiones
atípicas o poco marcadas, la estimación puede ser menos precisa y el umbral
puede no alcanzarse aunque la persona sí haya mostrado la expresión. No se
entrenan ni se agregan modelos (fuera de alcance). Mitigaciones:

- el nivel se mide respecto de la base neutral de esa misma sesión;
- el umbral y el sostén son cortos y el conductor puede saltar el ejercicio;
- el conductor puede apagar la señal si genera frustración;
- vencer el tiempo no muestra un mensaje de fracaso a la persona;
- los textos dicen "se logró / no se logró en el sistema", nunca valoran.

Aviso fijo (`PRACTICE_CHILD_NOTICE`) en la vista del conductor, el detalle, el
reporte y las estadísticas cuando el público es infantil:

> "Los modelos de EMOtv se entrenaron sobre todo con rostros de personas
> adultas. Con niños y niñas la estimación puede ser menos precisa: que el
> sistema no registre el logro no significa que la expresión no se haya
> mostrado. Es un registro descriptivo, no una evaluación."

**Otros riesgos.**

- Carga: analizar 2 cuadros por segundo por pantalla puede saturar el equipo
  mínimo; se mitiga con §6 y se mide antes del piloto.
- Interpretación: una tasa de logro baja podría leerse como un juicio sobre el
  niño. Las frases son descriptivas y las estadísticas cuentan ejercicios y
  sesiones, nunca personas.
- Reinicio del servidor a mitad de un ejercicio: el tracker se pierde y el
  ejercicio vuelve a empezar desde su nivel cero; la base neutral también se
  pierde (queda `relative_to_calibration = False`).
- Ilustraciones: una imagen con una cara podría parecer una foto de una persona.
  Solo se aceptan estímulos del banco con origen y licencia; las imágenes propias
  ya pasan por la detección de personas y la revisión del docente.

## 10. Validación con adultos voluntarios

Antes de usar la práctica con niños se mide si cada modelo (HSEmotion y FER+)
reconoce expresiones producidas a propósito. Solo participan adultos voluntarios
con cuenta de prueba `PRUEBA-NN` y consentimiento firmado en papel
(`docs/testing/volunteer-protocol.md`). No se guardan imágenes: los cuadros se
analizan en memoria y se descartan, como en cualquier sesión.

**Protocolo «Validación con adultos».** Para adultos, con un ejercicio de
práctica por cada expresión de `EXPRESSION_KEYS` menos `contempt`, en el orden del
catálogo (neutral, alegría, sorpresa, tristeza, enojo, asco, miedo). Cada uno se
sostiene 2 s, con un máximo de 15 s. Solo aparece con `CONSENT_MODE=demo` y para
una cuenta con `users.is_test_account` verdadero; en cualquier otro caso el
servidor no lo ofrece, no lo agrega (`403`) y no deja aplicarlo. El nombre está
reservado: ninguna otra cuenta puede crear un protocolo con ese nombre.

**Cómo se ejecuta.**

1. Configura `CONSENT_MODE=demo` en `.env` (o `.env.docker`) y reinicia la API.
2. Crea las cuentas de voluntarios:
   `python scripts/testdata/create_test_accounts.py --count 3`. Entrega a cada
   voluntario solo su código y su contraseña.
3. Con la cuenta del voluntario, en **Protocolos**, pulsa «Agregar «Validación
   con adultos»». Se agrega una sola vez.
4. En el **Analizador**, elige ese protocolo y confirma la autorización firmada.
   Haz la calibración neutral y deja que la persona siga cada instrucción.
5. Para comparar modelos, repite la sesión con el otro modelo elegido como
   predeterminado en **Modelos** (cuenta de administración).
6. Con la cuenta de administración (`superadmin`), en **Modelos**, pulsa
   «Descargar resumen (CSV)» (`GET /practice-validation/export.csv`).
7. Al terminar, o como máximo a los 30 días, borra los datos de los voluntarios con
   `python scripts/testdata/delete_test_data.py` (incluye `practice_results`).

**Qué trae el CSV.** Una fila por modelo, versión del modelo y expresión pedida:
`modelo`, `version_modelo`, `expresion_pedida`, `ejercicios` (los que llegaron a
su final: logrados o con el tiempo vencido), `logrados` y
`tiempo_promedio_hasta_lograrlo_s` (solo de los logrados; vacío si no hubo
ninguno). Solo cuenta las sesiones del protocolo de validación conducidas por
cuentas de voluntarios. No lleva códigos de sesión, fechas, correos ni nada que
identifique a alguien, y los ejercicios saltados o detenidos no cuentan.

El servidor arma el CSV en memoria al pedirlo y no lo guarda. El archivo
descargado es un resultado de prueba: no se agrega al repositorio (`*.csv` está
en `.gitignore`) ni se comparte fuera del equipo del proyecto. Con pocos
voluntarios, una fila puede corresponder a una sola persona: se trata como dato
de prueba y se borra junto con las cuentas.

**Cómo leerlo.** Describe cuántas veces el modelo registró la expresión pedida
en adultos que la produjeron a propósito. No prueba que el modelo funcione con
niños ni dice nada sobre el estado emocional de nadie.
