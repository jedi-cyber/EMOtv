# Etapa de reconocimiento corporal

## Alcance completado

Esta etapa implementa el flujo mínimo:

```text
cámara -> detección corporal -> landmarks -> esqueleto
       -> validación de postura -> tiempo -> ejercicio completado
```

Se utiliza MediaPipe Pose Landmarker Lite para detectar una persona. El
resultado externo se convierte a modelos propios para evitar que la lógica de
postura dependa de MediaPipe.

## Landmarks utilizados

- nariz;
- hombros;
- codos;
- muñecas;
- caderas;
- rodillas;
- tobillos.

Las coordenadas `x` e `y` están normalizadas respecto al frame. La profundidad
normalizada `z` disminuye hacia la cámara; `visibility` indica la calidad
estimada de cada punto. `arms_forward` requiere profundidad fiable.

## Postura: ambos brazos levantados

La postura es correcta cuando:

1. hombros, codos y muñecas superan la visibilidad mínima;
2. ambas muñecas están por encima de sus hombros, incluido el margen definido;
3. ambos codos están suficientemente extendidos.

Valores iniciales en `src/emotv/config.py`:

| Parámetro | Valor | Significado |
| --- | ---: | --- |
| `POSE_MIN_LANDMARK_VISIBILITY` | `0.5` | Visibilidad mínima aceptada |
| `ARMS_UP_WRIST_MARGIN` | `0.02` | Distancia vertical normalizada |
| `ARMS_UP_ELBOW_TOLERANCE_DEGREES` | `25.0` | Desviación permitida desde 180° |
| `ARMS_OPEN_WRIST_HEIGHT_TOLERANCE` | `0.08` | Diferencia vertical permitida |
| `ARMS_OPEN_LATERAL_MARGIN` | `0.08` | Apertura mínima desde el hombro |
| `HANDS_ON_HIPS_DISTANCE_TOLERANCE` | `0.12` | Distancia máxima muñeca–cadera |
| `HANDS_ON_HIPS_MIN_ELBOW_ANGLE` | `35.0°` | Flexión mínima del codo |
| `HANDS_ON_HIPS_MAX_ELBOW_ANGLE` | `135.0°` | Flexión máxima del codo |
| `ARMS_FORWARD_MIN_WRIST_DEPTH` | `0.12` | Avance mínimo de la muñeca respecto al hombro |
| `ARMS_FORWARD_ELBOW_TOLERANCE_DEGREES` | `35.0°` | Desviación máxima del codo extendido en 3D |
| `SQUAT_MIN_KNEE_ANGLE` / `SQUAT_MAX_KNEE_ANGLE` | `65°` / `155°` | Flexión aceptada de ambas rodillas |
| `ARMS_UP_HOLD_SECONDS` | `5.0` | Tiempo necesario para completar |

Estos valores son un punto de partida y deben calibrarse con usuarios, cámaras,
distancias e iluminación representativas.

## Contrato genérico de posturas

`PostureId` define identificadores estables para `arms_up`, `arms_open`,
`arms_forward`, `hands_on_hips` y `squat`. Los cinco cuentan con validadores
predeterminados; una prueba comprueba que cada paso del catálogo tenga uno.

Cada evaluación podrá devolver un `PostureResult` con:

- identificador de la postura;
- indicador `detected` / `is_valid`;
- confianza normalizada;
- mensaje para la interfaz;
- mediciones geométricas;
- identificadores de reglas incumplidas.

`PostureValidator.validate(pose, posture_id)` selecciona el evaluador desde un
registro. Incluye las cinco posturas anteriores; otros validadores pueden
añadirse mediante `register()` sin ampliar una cadena de
condicionales.
El método histórico `both_arms_up()` delega en esta interfaz y sigue devolviendo
un booleano.

### Brazos abiertos

Requiere muñecas aproximadamente a la altura de los hombros, brazos extendidos
y desplazamiento lateral hacia afuera del torso. La dirección se obtiene con
respecto al centro de los hombros para funcionar aunque la imagen esté reflejada.

### Manos en las caderas

Requiere ambas muñecas cerca de la cadera correspondiente, codos flexionados
dentro del rango configurado y desplazados hacia afuera del torso.

### Brazos al frente

Requiere hombros, codos y muñecas visibles, ambas muñecas y codos avanzados
hacia la cámara, muñecas a una altura cercana a los hombros y codos extendidos
según un ángulo 3D. No equivale a brazos abiertos: comprueba profundidad `z`.

### Sentadilla estática

Requiere hombros, caderas, rodillas y tobillos visibles, ambas rodillas
flexionadas dentro del rango configurable y el orden vertical esperado. Es
una aproximación geométrica de una postura mantenida, no un análisis de la
técnica, profundidad o seguridad de una sentadilla en movimiento.

## Máquina de estados

```text
incorrect -- postura correcta --> holding -- tiempo cumplido --> completed
    ^                                |
    +------ postura incorrecta ------+
```

- `incorrect`: progreso `0.0`;
- `holding`: progreso proporcional al tiempo sostenido;
- `completed`: progreso `1.0`, conservado hasta un reinicio explícito.

## Criterios de aceptación cubiertos

- el modelo se carga desde una ruta configurable;
- los frames BGR se convierten a RGB antes de MediaPipe;
- los timestamps de video son crecientes;
- la ausencia de persona produce `detected=False`;
- el dibujo no modifica el frame original;
- landmarks de baja visibilidad no se dibujan ni validan;
- el progreso está limitado al intervalo `[0, 1]`;
- bajar los brazos durante `holding` reinicia el ejercicio;
- los recursos de cámara, ventanas y modelo se liberan al finalizar.

## Limitaciones actuales

- se analiza una sola persona;
- las cinco posturas se validan geométricamente, pero requieren calibración
  con personas, cámaras y orientaciones reales;
- la prueba funcional con webcam requiere ejecución manual;
- los umbrales aún no han sido calibrados con una muestra de usuarios.

El sistema no debe utilizarse como herramienta diagnóstica.
