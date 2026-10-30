# Escenario de examen simulado en EMOtv

## Contexto

EMOtv nació como herramienta para practicantes de Psicología (sesiones con niños y padres, estímulos por imagen). Cambió el supervisor del proyecto y el nuevo pide aplicarlo en un entorno de exámenes, sin que los estudiantes finjan su expresión. La decana aprobó EMOtv como herramienta de la Facultad de Psicología y no como sistema de monitoreo.

La decisión que une ambas visiones: el examen simulado se implementa como un tipo más de Protocolo dentro de la Facultad. El flujo actual de prácticas no se elimina ni se rompe.

## Principio general

Cada pantalla debe pedir al usuario el mínimo de pasos posible; si algo puede calcularse automáticamente, no se le pide al usuario.

## Reglas que no se negocian

* Ningún estudiante se analiza sin consentimiento firmado (Ley 29733 y D.S. 016-2024-JUS: los datos biométricos son datos sensibles). El sistema debe registrar que la sesión tiene consentimiento antes de permitir iniciar el análisis.
* El participante sabe que será analizado, pero no qué se mide ni en qué momento. Al final se le explica (debriefing). Las cámaras son visibles y discretas, nunca ocultas.
* No se guardan imágenes. Los frames se procesan en memoria en el servidor y se descartan de inmediato. El docente ve resultados, nunca imágenes.
* No se registran datos personales de los participantes; cada uno se identifica solo con un código.

## Diseño técnico

* Una cámara por estudiante. No se usa una cámara única para todo el salón.
* Cada estudiante es una sesión individual del Analizador, igual que hoy.
* Nueva entidad "examen" (sesión grupal) que agrupa las sesiones individuales. El docente la crea y cada estudiante se une con un código.
* Registro por tiempo: cada ~0.5 s se guarda una fila con sesión, segundo, emoción y confianza.
* EMOtv registra todo el examen. El protocolo de examen no tiene segmentos que configurar.
* Resumen al cerrar el examen: la duración real se divide automáticamente en tres partes iguales (inicio, mitad y final) y se calcula el porcentaje de tiempo de cada emoción por parte, por estudiante (código) y del grupo completo.
* Gráfica de línea de las emociones a lo largo del tiempo del examen.
* Notificación al docente cuando un estudiante termina y cuando se cierra el examen, con el resumen. No se envían alertas por cada emoción detectada en vivo, porque la tensión y la concentración se confunden con emociones negativas y generarían falsas alarmas.
* Los resultados se presentan como registro descriptivo de expresiones faciales, no como diagnóstico de lo que siente la persona.

## Decisiones

### Procesamiento de la cámara

El navegador de cada estación envía los frames al servidor, que los analiza en memoria y los descarta de inmediato, igual que en las prácticas. No se analiza en el navegador ni se agregan dependencias para hacerlo.

### Flujo del docente

El docente no define bloques de tiempo ni configura segmentos. Solo tiene cuatro pasos:

1. **Crear examen**: un clic; EMOtv genera el código de unión.
2. **"Recibí los consentimientos de todos"**: un solo botón, con diálogo de confirmación. Registra el consentimiento firmado de cada código ya unido en ese momento.
3. **Iniciar**.
4. **Terminar**.

Cada sesión guarda su propia fecha de confirmación: el consentimiento queda registrado por código, aunque el docente lo confirme con un solo botón. Una estación que se une después de la confirmación queda bloqueada hasta una nueva confirmación. Ninguna estación analiza sin esa confirmación.

### Tipos de examen

Los exámenes de la Facultad son casi siempre escritos y a veces virtuales. Las PCs del salón no tienen cámara.

* **Examen escrito**: cada estudiante tiene una cámara discreta en su mesa. En el piloto, cada estación es un celular en un soporte con la página de estación de EMOtv abierta en el navegador. La página debe funcionar en navegador móvil: cámara frontal, pantalla oscura y con poco brillo, y sin que el celular se bloquee durante el examen (Screen Wake Lock). El navegador solo permite usar la cámara en HTTPS: los celulares se conectan con el perfil `https` de Docker (`docs/docker.md`).
* **Examen virtual**: se conecta una cámara web USB a cada PC. El examen se rinde fuera de EMOtv, en otra página.

### Captura en el examen virtual (pendiente)

El navegador frena las pestañas en segundo plano, así que la estación no puede quedar en una pestaña oculta mientras el estudiante rinde el examen en otra. Hay dos opciones:

* **Ventana pequeña aparte, siempre visible** (recomendada para evaluar primero): la estación se abre en una ventana propia del navegador, pequeña y en una esquina, sin que la tape la ventana del examen. Chrome no frena una ventana visible.
  * Ventajas: no se instala nada; usa la misma página y las mismas reglas que el examen escrito; el consentimiento y el debriefing se muestran en la misma pantalla.
  * Desventajas: si el estudiante maximiza la ventana del examen encima de ella, o si la minimiza, el navegador la frena y se pierden registros. Ocupa una parte de la pantalla. Una página web no puede quedar siempre encima de las demás ventanas. La página avisará cuando quede oculta y la sesión marcará los tramos sin registro.
* **Programa de estación en Python**: lee la cámara con OpenCV y envía los frames al servidor, sin navegador.
  * Ventajas: no depende del frenado del navegador; captura aunque el examen ocupe toda la pantalla.
  * Desventajas: hay que instalar Python y el programa en cada PC del laboratorio; necesita su propio inicio de sesión de estación; la pantalla de consentimiento y el debriefing quedarían fuera; es una aplicación de escritorio, que CLAUDE.md pone fuera de alcance, así que exige una decisión expresa del desarrollador.

La decisión queda pendiente hasta probar la ventana aparte en el laboratorio.

### Consentimiento y notificaciones

* El docente confirma con un solo botón que recibió los consentimientos firmados; la estación no inicia hasta entonces.
* Las notificaciones son solo un aviso dentro de EMOtv y una notificación del navegador en la PC del docente, sin dependencias nuevas.

## Trabajo futuro

* Notificaciones al celular del docente (aplicativo móvil o Web Push).
* Programa de estación sin navegador para el examen virtual, si la ventana aparte no basta.

## Alcance del piloto

Grupo pequeño de voluntarios (entre cuatro y ocho) en un laboratorio. La lista del piloto incluye una prueba de carga con varias estaciones analizando a la vez.

## Forma de trabajo

1. Antes de escribir código, revisa la estructura actual del repositorio (modelos de sesión, Protocolo, Analizador, roles) y explica cómo encaja este diseño.
2. Propón el plan dividido en bloques pequeños y espera aprobación antes de cada bloque.
3. No modifiques el flujo de prácticas existente salvo que sea necesario para reutilizarlo; si hace falta, avisa antes.
