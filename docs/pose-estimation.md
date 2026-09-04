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
| `ARMS_UP_HOLD_SECONDS` | `5.0` | Tiempo necesario para completar |

Estos valores son un punto de partida y deben calibrarse con usuarios, cámaras,
distancias e iluminación representativas.

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
- solo existe una postura objetivo;
- no hay persistencia de sesiones;
- no se ha integrado el flujo corporal con FastAPI;
- la prueba funcional con webcam requiere ejecución manual;
- los umbrales aún no han sido calibrados con una muestra de usuarios.

El sistema no debe utilizarse como herramienta diagnóstica.
