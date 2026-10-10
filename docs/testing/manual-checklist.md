# Lista de pruebas manuales con cámara y personas

Estas pruebas no se automatizan porque necesitan una cámara real, una persona
frente a ella o el workflow de Emi publicado. Las pruebas automáticas están en
[e2e.md](e2e.md).

## Antes de empezar

- Sigue el [protocolo de pruebas con voluntarios](volunteer-protocol.md).
  Solo participan voluntarios **mayores de edad** que **no pertenecen a la
  Facultad de Psicología de la UNHEVAL**, con el consentimiento **en papel
  firmado** antes de empezar.
- Cada persona usa **su propia cuenta `PRUEBA-NN`**, creada con
  `scripts/testdata/create_test_accounts.py`. En esta hoja se anota solo el
  código, nunca el nombre.
- `CONSENT_MODE=demo`. Cada voluntario acepta el consentimiento en la
  aplicación antes de usar la cámara.
- No se toman fotografías ni videos de la prueba. EMOtv tampoco los guarda.
- Recuerda a cada participante que el resultado estima la expresión visible:
  no dice lo que siente, no es un diagnóstico y la actividad no es terapia.
- Los datos de las cuentas se eliminan como máximo a los 30 días, con acta
  (protocolo, secciones 6 a 8).

Haz una copia de esta hoja por jornada. En «Observaciones» anota el código
`PRUEBA-NN`, el equipo, el navegador y la cámara. Completa la tabla de cada
prueba aunque falle: «no funcionó» también es un resultado.

## Iluminación y distancia

| Prueba | Resultado esperado | Resultado obtenido | Fecha | Observaciones |
|---|---|---|---|---|
| Iluminación normal (luz de frente), a 1 m | Se detecta el rostro, la lectura en vivo se estabiliza y se puede registrar la expresión. El resultado muestra la expresión en español, la confianza, la información y la limitación. | | | |
| Iluminación baja (solo luz de fondo o una lámpara tenue) | Si no se detecta el rostro, aparece «Ubica tu rostro en el centro…» y no se registra nada. Si se registra, la confianza mostrada es coherente con la lectura en vivo. | | | |
| Distancia de 1 m | Se detecta el rostro. Al pasar a la actividad, el aviso pide alejarse si no se ve el cuerpo completo. | | | |
| Distancia de 2 m | Se detecta el cuerpo completo y las posturas se verifican. Anotar si el rostro todavía se detecta. | | | |
| Distancia de 3 m | Anotar si se detecta el rostro y si las posturas se verifican. La aplicación no debe registrar una expresión sin rostro detectado. | | | |

## Posturas

Cada postura se prueba a la distancia que funcionó mejor en la tabla anterior.

| Prueba | Resultado esperado | Resultado obtenido | Fecha | Observaciones |
|---|---|---|---|---|
| Brazos arriba | Mientras se mantiene, el tiempo restante del paso avanza. Al bajar los brazos, se detiene. | | | |
| Brazos abiertos | Mientras se mantiene, el tiempo restante del paso avanza. Al bajar los brazos, se detiene. | | | |
| Brazos al frente | Mientras se mantiene, el tiempo restante del paso avanza. Al bajar los brazos, se detiene. | | | |
| Manos en las caderas | Mientras se mantiene, el tiempo restante del paso avanza. Al retirar las manos, se detiene. | | | |
| Sentadilla | Mientras se mantiene, el tiempo restante del paso avanza. Al ponerse de pie, se detiene. | | | |
| Postura incorrecta a propósito | El paso no avanza y el mensaje indica la postura esperada. | | | |
| Secuencia completa (actividad de dos o más posturas, con sus repeticiones) | Se completan todos los pasos en orden, la voz anuncia cada paso (si está activada), la cámara se apaga al terminar y el historial muestra la actividad como «Completada». | | | |

## Condiciones de la persona y del equipo

| Prueba | Resultado esperado | Resultado obtenido | Fecha | Observaciones |
|---|---|---|---|---|
| Con gafas graduadas | Se detecta el rostro y se registra una expresión. Anotar si la confianza baja o si cambia la expresión estimada respecto de la prueba sin gafas. | | | |
| Google Chrome (última versión) | Permiso de cámara, análisis, actividad y Emi funcionan. | | | |
| Microsoft Edge (última versión) | Permiso de cámara, análisis, actividad y Emi funcionan. | | | |
| Mozilla Firefox (última versión) | Permiso de cámara, análisis, actividad y Emi funcionan. Anotar diferencias. | | | |
| Cámara 1 (integrada de la laptop) | La vista previa funciona y el análisis llega a un resultado. Anotar marca, modelo y resolución. | | | |
| Cámara 2 (USB externa) | La vista previa funciona y el análisis llega a un resultado. Anotar marca, modelo y resolución. | | | |
| Cámara ocupada por otra aplicación (por ejemplo, una videollamada abierta) | Al probar la cámara aparece «Otra aplicación está usando la cámara…» y el requisito queda «Bloqueado». | | | |
| Permiso de cámara denegado en el navegador | Aparece «El navegador bloqueó la cámara…» con los pasos para permitirla. No se crea ninguna sesión. | | | |

## Conexión desde otra computadora

| Prueba | Resultado esperado | Resultado obtenido | Fecha | Observaciones |
|---|---|---|---|---|
| Otra computadora en la misma red por HTTPS (`docker compose --profile https`, `https://<IP>:8443`) | Tras aceptar el certificado local (docs/docker.md), se inicia sesión, se abre la cámara y el análisis llega a un resultado. | | | |
| La misma computadora por HTTP con la IP de la red (`http://<IP>:8080`) | La cámara no se abre y aparece el aviso de conexión segura (https). No se pide el permiso de cámara. | | | |
| Cerrar la pestaña con la cámara encendida | El indicador de cámara del sistema se apaga al cerrar la pestaña. | | | |

## Emi con el workflow publicado

Usa la clave real solo en el `.env` local (`N8N_WEBHOOK_KEY`). No la escribas
en esta hoja.

| Prueba | Resultado esperado | Resultado obtenido | Fecha | Observaciones |
|---|---|---|---|---|
| Pregunta dentro del alcance («¿Cómo funciona una actividad?») | Respuesta educativa sobre EMOtv en español, en un tiempo razonable (anotar los segundos). | | | |
| Pregunta sobre una expresión («¿Qué es la sorpresa?») | Explica la expresión en general; no afirma qué siente el estudiante ni diagnostica. | | | |
| Pregunta fuera del alcance (por ejemplo, una receta de cocina) | Emi indica que solo orienta sobre EMOtv y las expresiones faciales. | | | |
| Conversación de tres o más mensajes | Mantiene el contexto de la conversación. «Nueva conversación» empieza de cero. | | | |
| Historial | Al cerrar y volver a abrir a Emi, se recupera la conversación en curso. | | | |
