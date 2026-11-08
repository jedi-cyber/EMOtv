# Descripción fija de EMOtv para el workflow de Emi en Sim

Texto que el workflow de Emi en Sim guarda como conocimiento fijo y combina con
el campo `knowledge` que envía FastAPI en cada pregunta. Todo sale del
repositorio (README, `CLAUDE.md`, `docs/`, `src/emotv/domain/expression_info.py`,
`web/src/analysis/camera.ts`, `docs/privacy/`); no hay datos inventados. Si
cambia una función de EMOtv, se actualiza aquí y se vuelve a pegar en Sim.

El bloque entre las dos líneas `---` es lo que se pega en Sim.

---

## 1. Qué es EMOtv y para quién

EMOtv es una herramienta de apoyo de la Facultad de Psicología de la UNHEVAL
(Huánuco, Perú), pensada para la psicoeducación sobre el reconocimiento de
emociones, en especial en la niñez. La usan Usuarios y Docentes, que la aplican
con personas adultas o con niños y niñas, siempre con autorización. Estima la
expresión facial visible con la cámara del navegador, permite aplicar
protocolos (cuestionarios, «¿Qué emoción es?», ejercicios de práctica, «Haz la
misma cara», dibujos y dos juegos, con apoyos configurables) durante una
sesión, con o sin cámara, muestra una línea de tiempo con métricas descriptivas
y un reporte que revisa el Docente, y presenta estadísticas agregadas de
sesiones. Emi es su asistente: responde a Usuarios y Docentes
sobre Psicología en general y sobre el uso de EMOtv. Las personas evaluadas no
tienen cuenta ni usan Emi.

## 2. Análisis facial con la cámara

Toda sesión empieza en el **Analizador**:

1. Se elige un protocolo o «Sin protocolo (solo analizar)». Sin protocolo se
   indica con quién es la sesión: «Conmigo», «Un adulto» o «Un niño o niña».
2. Se confirma una sola vez la autorización según el público (ver punto 6).
   Sin confirmación no hay sesión.
3. La sesión muestra un código aleatorio (por ejemplo S-4F7K2Q) al empezar y al
   terminar, para anotarlo en el formato firmado.
4. Se pulsa «Empezar el análisis» (o «Empezar la sesión» con protocolo): el
   navegador pide permiso para usar la cámara. La imagen de la cámara se obtiene en el navegador; el servidor nunca
   abre una cámara.
5. Cada imagen se envía al servidor de EMOtv, que detecta el rostro (YuNet),
   estima la expresión con un modelo local (HSEmotion; FER+ como respaldo) y
   descarta la imagen. Puede hacerse antes una calibración neutral: «Mantén el
   rostro relajado y mira a la cámara».
6. La expresión se registra cuando la lectura es estable (por defecto, la misma
   expresión durante 1 segundo con confianza de al menos 50 %). Mientras tanto
   se muestran mensajes como «Esperando una expresión estable.» o «Mantén la
   expresión un momento más.».
7. El resultado muestra la expresión estimada, su confianza y textos educativos
   del catálogo: qué es, por qué suele presentarse, cómo se reconoce en el
   rostro, una sugerencia para practicarla y su limitación. Debajo siempre
   aparece la limitación común: el reconocimiento facial estima una expresión a
   partir de la imagen y no determina por sí mismo el estado emocional ni
   psicológico de la persona. El botón «Preguntar a Emi sobre esta expresión»
   abre a Emi con una pregunta general y editable, sin datos de la sesión.

Con protocolo, la sesión sigue sus pasos: cuestionario previo, calibración
neutral, los pasos en orden («¿Qué emoción es?», imágenes, ejercicios de
práctica, «Haz la misma cara», dibujos y juegos) y cuestionario posterior. La
persona evaluada ve los pasos en su propia pantalla («Abrir la pantalla de la
persona», o en Android con «Vincular Android»), sin resultados, y puede pedir
parar en cualquier momento («Quiero parar»). Emi no aparece en esa pantalla.

## 3. Otras funciones

- **Guía de uso**: cada cuenta tiene, al final del menú, «Guía de uso» con las
  tareas de su papel paso a paso. Emi recibe la misma guía en `knowledge`;
  ante una pregunta de «cómo se hace», responde con esos pasos.
- **Protocolos**: recetas guardadas para adultos o para niños, con un
  cuestionario previo opcional, pasos en orden (imágenes con sus segundos de
  exposición, «¿Qué emoción es?», ejercicios de práctica y «Haz la misma
  cara») y un cuestionario posterior opcional. Un protocolo para niños solo
  admite imágenes leves y aprobadas. Uno ya usado no se edita: se crea una
  versión nueva. El «Modo accesible» usa dos opciones con pictograma, botones
  grandes y más tiempo por paso.
- **Plantillas y banco inicial**: «Usar la plantilla inicial» copia el
  protocolo «Emociones básicas 4 a 6 años» (para niños y en modo accesible). El
  banco inicial trae dibujos de expresiones listos para usar. Un Docente puede
  compartir un protocolo con su grupo como plantilla, y cada Usuario lo copia.
- **«¿Qué emoción es?»**: un paso de reconocimiento. La persona ve un dibujo y
  elige entre opciones; después se lee el nombre de la emoción del dibujo, sin
  valorar la respuesta. El resultado se describe («Eligió la emoción de la imagen
  en X de Y»), nunca como puntaje.
- **Sin cámara**: «¿Qué emoción es?», los dibujos y los juegos no usan la
  cámara. Un protocolo solo con esos pasos no la pide. Si la cámara falla,
  quien conduce pulsa «Continuar sin cámara»: siguen esos pasos y se saltan los
  que la necesitan.
- **Dibujo** («Agregar dibujo»): la persona dibuja con el dedo
  (colores, grosor, borrador, «Deshacer» y «Limpiar»), pulsa «Terminé» y elige
  qué emoción quiso dibujar. **El dibujo no se guarda ni se envía, y EMOtv no lo
  interpreta**: solo se registra la emoción elegida, los tiempos y quién
  respondió. Emi tampoco interpreta dibujos.
- **Juegos**, de 2 a 6 rondas, sin puntaje:
  - «Agregar juego de emparejar»: la persona ve una cara y toca el nombre de su
    emoción;
  - «Agregar juego: busca la misma emoción»: ve una cara arriba y elige otra
    cara («Cara 1», «Cara 2»…) que muestre la misma emoción.

  Si elige otra, se la invita a mirar otra vez; tras dos intentos, se muestra
  la respuesta con una explicación sencilla. «Ayuda» quita una opción una vez
  por ronda.
- **Repetir un paso**: quien conduce puede pulsar «Repetir este paso», «Repetir
  este ejercicio», «Repetir este dibujo» o «Repetir el juego».
- **Apoyos del protocolo**: «Modo accesible» junta pictogramas, botones
  grandes, nada que se mueva y pausas más largas. También se eligen uno por
  uno: «Pictogramas junto a cada emoción», «Botones y letra grandes, sin
  animaciones», «Leer la consigna en voz alta al empezar cada paso», «Sin
  límite de tiempo en «¿Qué emoción es?» y en la práctica» y la pausa tras cada
  paso (normal, larga o esperar a que quien conduce pulse «Seguir»).
- **Resultados educativos**: el reporte y las estadísticas describen lo
  ocurrido en cada actividad (por ejemplo, «Jugó 2 de 2 rondas.») y nunca
  valoran a la persona. Una sesión breve no permite sacar conclusiones.
- **Imágenes**: los Docentes y la administración crean estímulos; los Usuarios
  suben imágenes propias, que pasan por detección automática de personas y
  quedan pendientes hasta que su Docente las aprueba («Para niños» o «Para
  adultos») o las elimina.
- **Sesiones y línea de tiempo**: la línea de tiempo ordena cuestionarios,
  imágenes, respuestas de reconocimiento, ejercicios, capturas y los marcadores
  de quien conduce (se distrajo, se rió, lloró, pidió parar o una nota). Antes de cada
  captura se revisa la calidad; una captura con problemas no cuenta en las
  métricas. Para cada imagen emocional se describe si la expresión estimada
  coincidió con la esperada («En X de Y imágenes…»): es una descripción, no una
  evaluación.
- **Reportes**: los redacta quien condujo la sesión («Redactar el reporte»),
  los envía a revisión y los revisa su Docente en «Por revisar».
  Estados: borrador, enviado a revisión, con observaciones y aprobado. Un
  reporte aprobado no se edita (se crea una versión nueva) y solo se imprime un
  reporte aprobado.
- **Estadísticas agregadas**: cuentan sesiones, nunca personas. No hay
  seguimiento ni estadísticas por persona.
- **Ejercicios de práctica de expresiones**: un paso del protocolo en el que la
  persona recibe una instrucción («Muestra alegría») y ve una señal de 0 a 1
  que crece cuando su expresión estimada se acerca a la pedida, y «¡Lo
  lograste!» al sostenerla. No ve etiquetas, probabilidades ni calidad. Quien
  conduce puede saltar un ejercicio o apagar la señal. El resultado se describe
  («Logró la expresión pedida en 3 de 5 ejercicios») y nunca valora a la
  persona. Es actividad guiada, no terapia ni evaluación diagnóstica. Una
  variante, «Haz la misma cara», muestra un dibujo como modelo y pide la misma
  expresión que muestra el dibujo; quien conduce ve «Imitar el modelo».
- **Funciones que no están disponibles**: las actividades de posturas, el
  examen simulado y las imágenes abstractas con respuesta verbal están
  desactivadas porque no forman parte del objetivo actual. Si alguien pregunta
  por ellas, Emi dice que no están disponibles en esta versión.
- **Aplicativo móvil (Android)**: no conduce sesiones ni usa la cámara.
  - Con cuenta: muestra las sesiones y su detalle, los reportes (el Usuario
    redacta, corrige y envía; el Docente comenta, devuelve o aprueba), las
    estadísticas agregadas y los pendientes del Docente.
  - Sin cuenta, como pantalla de la persona: quien conduce pulsa «Vincular
    Android» en la web y la persona escribe el código en «Abrir una actividad
    con código». El código vence en 5 minutos y sirve una sola vez. Ahí se
    dibuja y se juegan los dos juegos. El dibujo y las imágenes viven solo en
    la memoria del teléfono.

## 4. Expresiones que estima EMOtv

Ocho expresiones, con sus nombres en la interfaz:

| Clave interna | Nombre en EMOtv |
| --- | --- |
| `neutral` | Neutral |
| `happiness` | Felicidad |
| `surprise` | Sorpresa |
| `sadness` | Tristeza |
| `anger` | Enojo |
| `disgust` | Desagrado |
| `fear` | Miedo |
| `contempt` | Desprecio |

En los ejercicios de práctica se pueden pedir todas menos desprecio, con estos
nombres: Alegría, Sorpresa, Tristeza, Enojo, Miedo, Asco y Cara tranquila.

## 5. Cuentas y papeles

- **Usuario**: conduce sesiones desde el Analizador (propias o con otras
  personas), arma sus cuestionarios y protocolos, sube imágenes propias y
  redacta reportes. Tiene un solo Docente.
- **Docente**: supervisa a su grupo sin estar presente en cada sesión. Revisa
  y aprueba los reportes que le envían, aprueba sus imágenes y ejecuta la
  eliminación de sesiones con acta; lo pendiente aparece en «Por revisar». No
  conduce las sesiones de sus usuarios: sus sesiones propias son de
  demostración, para enseñar a usar EMOtv, y no cuentan en las estadísticas.
- **Administración**: gestiona cuentas y grupos. No accede a sesiones, reportes
  ni resultados. Hay además una cuenta de soporte técnico (superadministrador),
  que tampoco accede a contenidos.
- **No hay autorregistro**: la administración crea las cuentas y arma los
  grupos. Algunas cuentas deben cambiar su contraseña provisional al entrar.
- Para usar la cámara se necesita un navegador con cámara, abrir EMOtv con una
  dirección `https://` (o `localhost` en el propio equipo) y permitir la cámara
  cuando el navegador lo pida.

## 6. Datos y privacidad

- **Ninguna imagen ni video de una persona evaluada se guarda ni sale del
  servidor.** Cada imagen se analiza en memoria y se descarta. No se usa ningún
  servicio externo de visión y nunca se reconoce a nadie. Las únicas imágenes
  guardadas son los estímulos que suben Usuarios, Docentes o la administración.
- No se registra a la persona evaluada: no se guarda nombre, DNI ni foto. Cada
  sesión lleva solo un código aleatorio.
- Se guardan la expresión estimada y su confianza, las respuestas a
  cuestionarios, los marcadores, los resultados de práctica y los reportes.
  Notas, respuestas, comentarios y textos de reportes se guardan cifrados.
- **Quién ve qué**: a una sesión solo acceden quien la condujo y el Docente de
  ese Usuario. La administración nunca accede a contenidos.
- **Retención**: cada sesión se conserva por un periodo configurado
  (12 meses en la configuración de ejemplo) y se puede eliminar antes: quien la
  condujo pide la eliminación y su Docente la ejecuta, con un acta sin datos
  personales. Las conversaciones con Emi se guardan hasta 90 días y cada
  persona puede borrar la suya.
- **Autorización de cada sesión**: sesión propia o con una persona adulta
  («cuento con su autorización firmada»); con un niño o niña, su tutor autorizó
  por escrito, está presente y el niño aceptó participar.
- **Compromiso de confidencialidad**: Usuarios y Docentes lo aceptan una vez
  (por versión); sin aceptarlo no inician sesiones con personas.
- Los dibujos no se guardan ni salen del dispositivo de la persona.
- A Emi nunca llegan datos de sesiones, reportes ni resultados. EMOtv rechaza,
  antes de enviarlos, los mensajes con DNI, correos o teléfonos. No se deben
  escribir nombres ni datos de niños o familias.

## 7. Límites

- EMOtv **estima una expresión facial visible**; no indica lo que una persona
  siente, no diagnostica, no determina el estado psicológico de nadie y no
  sustituye a un profesional.
- Influyen la iluminación, el ángulo, la distancia, los lentes, la mascarilla,
  el cabello y el movimiento. Las expresiones varían entre personas, culturas y
  edades; con niños la estimación puede ser menos precisa. Una persona puede
  contener o actuar una expresión, y una captura dura un instante.
- Los cuestionarios, las respuestas de reconocimiento y las estadísticas solo
  muestran y resumen lo registrado: EMOtv no calcula puntajes, no interpreta
  respuestas, dibujos ni juegos, y no relaciona una imagen con ninguna
  condición. Una sesión breve no permite concluir nada sobre la persona.
- Si alguien pide interpretar el dibujo o el resultado de una persona concreta,
  Emi explica que ni EMOtv ni Emi lo hacen y sugiere conversarlo con su Docente.
- Los resultados son de apoyo y los interpreta un profesional, nunca el
  sistema.

## 8. Problemas comunes de cámara y detección

Mensajes reales de la interfaz y qué hacer:

| Mensaje | Qué hacer |
| --- | --- |
| «La cámara solo funciona en una conexión segura. Abre EMOtv con una dirección https:// (o en localhost si estás probando en este equipo).» | Abrir EMOtv con `https://` |
| «El navegador bloqueó la cámara. Pulsa el icono de la cámara o del candado junto a la dirección, elige «Permitir» y vuelve a probar.» | Dar permiso en el navegador |
| «Otra aplicación está usando la cámara. Cierra las videollamadas u otras pestañas que la usen y vuelve a probar.» | Cerrar la otra aplicación o pestaña |
| «No encontramos ninguna cámara. Conecta una cámara o revisa que esté activada y vuelve a probar.» | Conectar o activar la cámara |
| «No se pudo abrir la cámara. Vuelve a probar; si continúa, reinicia el navegador.» | Reintentar o reiniciar el navegador |
| «No se detecta un rostro. Ubica tu cara en el centro de la cámara.» | Centrar el rostro, de frente y con buena luz |
| «La confianza del modelo es baja; mantén la expresión de forma clara.» | Mantener la expresión clara unos segundos |
| «Esperando una expresión estable.» / «Mantén la expresión un momento más.» | Sostener la expresión |
| «El servidor está ocupado; intenta de nuevo en un momento» | Esperar y volver a intentar |
| «Se perdió la conexión con el analizador. La cámara se apagó.» | Revisar la conexión e iniciar de nuevo |

En una sesión con protocolo, quien conduce ve por qué una captura no cuenta:
«no llegó imagen de la cámara», «no se ve el rostro», «rostro no centrado»,
«rostro muy lejos», «poca luz», «demasiada luz» o «cabeza inclinada». En la
pantalla de la persona evaluada, si la cámara falla, aparece «No se pudo usar
la cámara. Avisa a quien conduce la sesión.».

---
