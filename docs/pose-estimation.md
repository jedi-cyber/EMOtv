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

Las coordenadas `x` e `y` están normalizadas respecto al frame. `visibility`
indica la calidad estimada de cada punto.

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
| `ARMS_UP_HOLD_SECONDS` | `5.0` | Tiempo necesario para completar |

Estos valores son un punto de partida y deben calibrarse con usuarios, cámaras,
distancias e iluminación representativas.

## Contrato genérico de posturas

`PostureId` define identificadores estables para `arms_up`, `arms_open`,
`arms_forward`, `hands_on_hips` y `squat`. La existencia de un identificador no
implica que su validador ya esté implementado.

Cada evaluación podrá devolver un `PostureResult` con:

- identificador de la postura;
- indicador `detected` / `is_valid`;
- confianza normalizada;
- mensaje para la interfaz;
- mediciones geométricas;
- identificadores de reglas incumplidas.

`PostureValidator.validate(pose, posture_id)` selecciona el evaluador desde un
registro. Actualmente incluye `arms_up`, `arms_open` y `hands_on_hips`; otros
validadores pueden añadirse mediante `register()` sin ampliar una cadena de
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
- existen tres validadores; el ejercicio interactivo todavía usa `arms_up`;
- no hay persistencia de sesiones;
- no se ha integrado el flujo corporal con FastAPI;
- la prueba funcional con webcam requiere ejecución manual;
- los umbrales aún no han sido calibrados con una muestra de usuarios.

El sistema no debe utilizarse como herramienta diagnóstica.
