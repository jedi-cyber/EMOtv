# Lista de pruebas manuales con cámara y personas

Estas pruebas no se automatizan porque necesitan una cámara real, una persona
frente a ella o el workflow de Emi publicado. Las pruebas automáticas están en
[e2e.md](e2e.md). La lista sigue el objetivo vigente: sesiones con protocolo
(«¿Qué emoción es?», ejercicios de práctica y «Haz la misma cara»), la
supervisión del docente y Emi. Las actividades corporales están congeladas y
quedan en el [anexo](#anexo-actividades-corporales-congeladas).

## Antes de empezar

- Sigue el [protocolo de pruebas con voluntarios](volunteer-protocol.md).
  Solo participan voluntarios **mayores de edad** que **no pertenecen a la
  Facultad de Psicología de la UNHEVAL**, con el consentimiento **en papel
  firmado** antes de empezar.
- Cada persona usa **su propia cuenta `PRUEBA-NN`**, creada con
  `scripts/testdata/create_test_accounts.py`. En esta hoja se anota solo el
  código, nunca el nombre.
- `CONSENT_MODE=demo`. Cada voluntario acepta el consentimiento y el
  compromiso de confidencialidad en la aplicación antes de usar la cámara.
- **Nunca con niños.** Los protocolos para niños se prueban con una copia
  cambiada a «Para adultos» (sección 3).
- No se toman fotografías ni videos de la prueba. EMOtv tampoco los guarda.
- Recuerda a cada persona que el resultado estima la expresión visible: no dice
  lo que siente, no es un diagnóstico y los ejercicios no son terapia.
- Los datos de las cuentas se eliminan como máximo a los 30 días, con acta
  (protocolo, secciones 6 a 8).

Haz una copia de esta hoja por jornada. En «Observaciones» anota el código
`PRUEBA-NN`, el equipo, el navegador, la cámara y el modelo (HSEmotion o FER+).
Completa cada fila aunque la prueba falle: «no funcionó» también es un
resultado.

**Preparación una sola vez.** Con la cuenta de administración, en «Estímulos
institucionales», pulsa «Agregar el banco inicial».

## 1. Cámara, luz y distancia

Sesión en el Analizador, «Sin protocolo», con «Conmigo».

| Prueba | Resultado esperado | Resultado obtenido | Fecha | Observaciones |
| --- | --- | --- | --- | --- |
| Iluminación normal (luz de frente), a 1 m | Se detecta el rostro, la lectura en vivo se estabiliza y se registra la expresión. El resultado muestra la expresión en español, la confianza, la información y la limitación. | | | |
| Iluminación baja (solo luz de fondo o una lámpara tenue) | Si no se detecta el rostro, aparece «Ubica tu rostro en el centro…» y no se registra nada. Si se registra, la confianza es coherente con la lectura en vivo. | | | |
| Distancia de 2 m | Anotar si se detecta el rostro. No se registra una expresión sin rostro. | | | |
| Con gafas graduadas | Se registra una expresión. Anotar si la confianza baja o si cambia la expresión estimada respecto de la prueba sin gafas. | | | |
| Código de la sesión | Se muestra al empezar y al terminar (por ejemplo, S-4F7K2Q) y es el mismo en «Mis sesiones». | | | |

## 2. Validación con adultos

Protocolo «Validación con adultos» ([expression-practice.md §10](../expression-practice.md#10-validación-con-adultos-voluntarios)):
un ejercicio por expresión. Anota por expresión si se logró y en cuántos
segundos, primero con HSEmotion y luego con FER+.

| Prueba | Resultado esperado | Resultado obtenido | Fecha | Observaciones |
| --- | --- | --- | --- | --- |
| Agregar el protocolo | En «Protocolos» aparece «Agregar «Validación con adultos»» solo en la cuenta `PRUEBA-NN`, y se agrega una vez. | | | |
| Ejercicios con HSEmotion | La pantalla de la persona muestra solo la instrucción, la señal de 0 a 1 y «¡Lo lograste!». Anotar cuántos de los siete se lograron. | | | |
| Ejercicios con FER+ | Igual que con HSEmotion. Anotar cuántos se lograron. | | | |
| Señal apagada | Con la señal apagada por quien conduce, la persona ve solo la instrucción y el ejercicio se registra igual. | | | |

## 3. Sesión con protocolo

En «Protocolos», pulsa «Usar la plantilla inicial». En la copia de «Emociones
básicas 4 a 6 años», usa «Editar» y cambia el público a «Para adultos». Agrega
también un ejercicio de práctica y un paso «Haz la misma cara» con un dibujo
del banco inicial. Úsala en el Analizador.

| Prueba | Resultado esperado | Resultado obtenido | Fecha | Observaciones |
| --- | --- | --- | --- | --- |
| Confirmación | Sin confirmar la autorización firmada no se puede empezar. | | | |
| Pantalla de la persona | «Crear el enlace de la pantalla de la persona» y «Abrir la pantalla de la persona» la abren en otra ventana o dispositivo. No muestra resultados, etiquetas, probabilidades ni calidad. | | | |
| Calibración | Con la cara tranquila, la calibración termina y empieza el primer paso. | | | |
| «¿Qué emoción es?» en modo accesible | Se ven el dibujo, dos opciones con pictograma y botones grandes. Tras elegir se lee el nombre de la emoción del dibujo, sin valorar la respuesta. | | | |
| Ejercicio de práctica | Se lee la instrucción («Muestra alegría»). La señal crece al acercarse y aparece «¡Lo lograste!» al sostenerla. Si se vence el tiempo, no hay mensaje de fracaso. | | | |
| «Haz la misma cara» | Se ven el dibujo y «Haz la misma cara». Quien conduce ve «Imitar el modelo» y la expresión pedida. | | | |
| Marcadores y saltar | «Se distrajo», «Se rió», «Lloró» y «Pidió parar» quedan en la línea de tiempo. «Saltar este paso» avanza. | | | |
| Detener a pedido | «La persona pidió parar» termina la sesión y queda registrado el motivo. | | | |
| Línea de tiempo y métricas | En «Mis sesiones», la sesión muestra los pasos en orden y frases descriptivas («Logró la expresión pedida en X de Y ejercicios»), sin valorar a la persona. | | | |

## 4. Supervisión del docente

Con una cuenta de docente de prueba y su grupo. No hace falta una persona
frente a la cámara.

| Prueba | Resultado esperado | Resultado obtenido | Fecha | Observaciones |
| --- | --- | --- | --- | --- |
| Reporte enviado | El usuario usa «Redactar el reporte» y «Enviar a revisión». El reporte aparece en «Por revisar» del docente, con el contador del menú. | | | |
| Devolver y aprobar | «Comentar» y «Devolver con observaciones» lo devuelven al usuario. Tras corregirlo y reenviarlo, «Aprobar» lo cierra y sale de «Por revisar». | | | |
| Pedido de eliminación | «Pedir que se elimine» lo hace aparecer en «Por revisar». «Eliminar la sesión» la borra y deja un acta sin datos personales. | | | |
| Imagen propia | Una imagen que sube el usuario espera en «Imágenes por revisar» y solo se usa cuando el docente la aprueba. | | | |
| Demostración | Una sesión propia del docente se marca «Tú (demostración)» y no cambia sus estadísticas. | | | |
| Estadísticas | Cuentan sesiones, nunca personas. No hay datos por persona. | | | |

## 5. Navegadores, cámaras y conexión

| Prueba | Resultado esperado | Resultado obtenido | Fecha | Observaciones |
| --- | --- | --- | --- | --- |
| Google Chrome (última versión) | Permiso de cámara, análisis, sesión con protocolo y Emi funcionan. | | | |
| Microsoft Edge (última versión) | Igual que en Chrome. | | | |
| Mozilla Firefox (última versión) | Igual que en Chrome. Anotar diferencias. | | | |
| Cámara integrada de la laptop | La vista previa funciona y el análisis llega a un resultado. Anotar marca, modelo y resolución. | | | |
| Cámara USB externa | Igual que la integrada. | | | |
| Cámara ocupada por otra aplicación | Al probar la cámara aparece «Otra aplicación está usando la cámara…» y el requisito queda «Bloqueado». | | | |
| Permiso de cámara denegado | Aparece «El navegador bloqueó la cámara…» con los pasos para permitirla. No se crea ninguna sesión. | | | |
| Otra computadora de la red por HTTPS (`docker compose --profile https`, `https://<IP>:8443`) | Tras aceptar el certificado local ([docker.md](../docker.md)), se inicia sesión, se abre la cámara y el análisis llega a un resultado. La pantalla de la persona se abre en ese otro equipo. | | | |
| Por HTTP con la IP de la red (`http://<IP>:8080`) | La cámara no se abre y aparece el aviso de conexión segura. No se pide el permiso. | | | |
| Cerrar la pestaña con la cámara encendida | El indicador de cámara del sistema se apaga. | | | |

## 6. Emi con el workflow publicado

Usa la URL y la clave reales solo en el `.env` local (`SIM_WORKFLOW_URL` y
`SIM_API_KEY`). No las escribas en esta hoja. Antes, pega en el workflow la
descripción vigente de `docs/chatbot/emotv-descripcion-sim.md`.

| Prueba | Resultado esperado | Resultado obtenido | Fecha | Observaciones |
| --- | --- | --- | --- | --- |
| Pregunta de uso («¿Cómo inicio una sesión con protocolo?») | Responde con los pasos de la «Guía de uso», en español y en un tiempo razonable (anotar los segundos). | | | |
| Pregunta del docente («¿Dónde veo los reportes que me enviaron?») | Indica «Por revisar». | | | |
| Pregunta sobre una expresión («¿Qué es la sorpresa?») | Explica la expresión en general; no afirma qué siente nadie ni diagnostica. | | | |
| Pedido de interpretar a alguien («¿Mi alumno tiene un problema si no sonríe?») | No etiqueta ni diagnostica a la persona; recuerda que EMOtv estima una expresión. | | | |
| Mensaje con un DNI, un correo o un teléfono | Se rechaza antes de llegar a Emi, con un aviso. | | | |
| Pregunta fuera del alcance (por ejemplo, una receta de cocina) | Emi indica que solo orienta sobre EMOtv y Psicología. | | | |
| Conversación de tres o más mensajes | Mantiene el contexto. «Nueva conversación» empieza de cero. | | | |
| Historial | Al cerrar y volver a abrir a Emi, se recupera la conversación en curso. | | | |

## Anexo: actividades corporales (congeladas)

Solo si se activan para mostrar los criterios 5, 6 y 7: API con
`ACTIVITIES_ENABLED=true` y `ACTIVITIES_ENABLED = true` en
`web/src/routes/features.ts`. Cada postura se prueba a la distancia que
funcionó mejor (de 2 a 3 m, con el cuerpo completo visible).

| Prueba | Resultado esperado | Resultado obtenido | Fecha | Observaciones |
| --- | --- | --- | --- | --- |
| Brazos arriba | Mientras se mantiene, el tiempo restante del paso avanza. Al bajar los brazos, se detiene. | | | |
| Brazos abiertos | Mientras se mantiene, el tiempo restante avanza. Al bajar los brazos, se detiene. | | | |
| Brazos al frente | Mientras se mantiene, el tiempo restante avanza. Al bajar los brazos, se detiene. | | | |
| Manos en las caderas | Mientras se mantiene, el tiempo restante avanza. Al retirar las manos, se detiene. | | | |
| Sentadilla | Mientras se mantiene, el tiempo restante avanza. Al ponerse de pie, se detiene. | | | |
| Postura incorrecta a propósito | El paso no avanza y el mensaje indica la postura esperada. | | | |
| Secuencia completa (dos o más posturas, con repeticiones) | Se completan los pasos en orden, la cámara se apaga al terminar y la sesión muestra la actividad como «Completada». | | | |
