# Frontend web de EMOtv

Aplicación React + TypeScript construida con Vite. Durante el desarrollo, Vite
redirige las rutas de API hacia FastAPI en `http://127.0.0.1:8000`.

```powershell
# Terminal 1, desde la raíz
.venv\Scripts\python.exe scripts/run_api.py

# Terminal 2
cd web
npm ci
npm run dev
```

Abre `http://localhost:5173`. Para usar otra dirección de API, copia
`.env.example` como `.env.local` y configura `VITE_API_URL`.

Comprobaciones locales:

```powershell
npm run typecheck
npm test
npm run build
```

La autenticación actual conserva el token solamente en `sessionStorage`. Antes
de un despliegue público debe evaluarse el cambio a cookies seguras `HttpOnly`.

## Acceso por roles

- `student`: analizador, actividades y sesiones propias;
- `psychologist`: seguimiento de estudiantes, sesiones y actividades;
- `admin`: usuarios, estudiantes, administración de actividades y sesiones generales.

El analizador facial aparece solo al estudiante; no forma parte del menú de
Administración ni de Psicología. Para probar cada vista con cuentas locales,
consulta [el script de cuentas de prueba](../scripts/README.md#cuentas-locales-de-prueba-por-rol).

## Estructura de navegación

Las URLs del frontend son rutas por recurso y se definen en `src/routes/paths.ts`.
Los módulos visibles y su orden por rol se definen en `src/routes/navigation.ts`;
`AppLayout` solo los representa. Añadir un módulo requiere actualizar esa
configuración y registrar la ruta con su protección correspondiente.
Los parámetros de detalle se codifican al construir enlaces. No se duplican
pantallas compartidas bajo prefijos de rol: Psicología y Administración usan
el mismo listado de estudiantes y sesiones, con permisos aplicados por ruta y API.

| Ruta | Acceso |
| --- | --- |
| `/dashboard` | Todos los roles autenticados |
| `/activities`, `/activities/:activityId` | Todos los roles autenticados |
| `/analysis` | Estudiante |
| `/sessions`, `/sessions/:sessionId` | Todos, según autorización de la API |
| `/students`, `/students/:studentId/sessions` | Psicología y Administración |
| `/users`, `/admin/activities` | Administración |

`/login` es pública; `/unauthorized` y `/connection-error` muestran estados
transversales. Las URL existentes se conservan para no invalidar enlaces.
La página 404 explica que no se encontró el destino y ofrece volver al inicio.
La página de acceso restringido indica que la cuenta no puede abrir esa sección,
sin mostrar detalles técnicos ni reglas internas de autorización.

Todas las rutas autenticadas comparten `AppLayout`: sidebar de módulos por rol,
encabezado con ubicación, correo y rol, cierre de sesión y área de contenido.
El encabezado agrupa correo, rol y salida en un menú de usuario desplegable;
se cierra con Escape, al pulsar fuera o al cambiar de ruta.
El rol se muestra siempre como una etiqueta en el botón del menú, incluso en
móvil y con el desplegable cerrado.
Esto incluye las pantallas de acceso denegado, error de conexión y página 404;
solo `/login` queda fuera del layout autenticado.
El menú marca la ruta activa y se convierte en un panel desplegable en móvil.
En escritorio conserva la barra lateral; en tablet reduce su ancho y distribuye
tarjetas y formularios en dos columnas; en móvil el botón «Menú» abre un panel
lateral superpuesto. Se cierra al elegir una ruta, tocar fuera o pulsar Escape.
No se utiliza navegación inferior.
Los enlaces de navegación combinan iconos SVG decorativos con etiquetas de texto
visibles; el icono nunca sustituye el nombre accesible del destino.
El foco pasa al contenido principal al cambiar de ruta. En móvil, Tab y Shift+Tab
permanecen dentro del panel abierto; Escape lo cierra y devuelve el foco al
botón del menú. Una señal discreta «Servicio no disponible» aparece en la barra
superior solo tras un fallo de red o del servidor y desaparece al recuperarse;
no muestra códigos ni diagnósticos a estudiantes.
Los colores, bordes y espacios principales usan variables CSS compartidas. Los
módulos y sus vistas de detalle usan `PageHeader` para mantener sección, título,
descripción y acciones con la misma estructura.
Los breadcrumbs aparecen solo en vistas con jerarquía real: detalle de actividad,
detalle de sesión y sesiones de un estudiante. No aparecen en inicio, listados,
analizador ni páginas de error. Estas vistas de detalle también incluyen un
enlace de retorno con destino explícito, como «Volver a sesiones».

Durante un análisis con sesión activa, la navegación interna solicita confirmación
antes de salir. Confirmar cancela primero la sesión en la API y apaga la cámara;
si la cancelación falla, permanece en el análisis. Recargar o cerrar la pestaña
activa la advertencia nativa del navegador. El menú muestra «Sesión activa ·
Volver al análisis» mientras la sesión está en curso; en móvil también aparece
en la barra superior. Tras completar o cancelar la sesión, el indicador desaparece.

Durante el análisis se muestran tres etapas: reconocimiento de expresión,
preparación de postura y actividad. El progreso y el resultado siguen dentro
del panel de actividad.

El frontend consulta `/auth/me` al iniciar, protege las rutas y cierra la sesión
cuando vence el JWT o cuando una petición autenticada devuelve `401`. Las rutas
de otro rol redirigen a una pantalla de acceso restringido. La vista de
estudiantes usa `GET /students` y enlaza a sus sesiones. Los estudiantes solo acceden a sus recursos;
los permisos institucionales por psicólogo asignado siguen pendientes.
Al vencer el token se muestra un aviso en `/login`, sin exponer el mensaje técnico
del `401`. Si `/auth/me` falla por red o error del servidor, se conserva el token
y se muestra una pantalla de conexión con reintento; no se trata como cierre de
sesión. Cada consulta de página muestra un indicador y un esqueleto de carga.
Los fallos de conexión ofrecen reintentar y abrir la ayuda de conexión; otros
errores mantienen su tratamiento local sin enviar al usuario a esa página.

## Actividades y cámara

El recorrido principal del estudiante comienza en `/analysis`, sin elegir una
actividad previamente: se reconoce la expresión facial, se ofrece una actividad
sugerida (con alternativas) y, tras confirmarla, se valida la postura. El catálogo
de actividades se puede consultar por separado; los enlaces antiguos con
`?activity=` se conservan solo por compatibilidad.

«Probar cámara» abre una vista previa local sin crear sesión ni enviar imágenes.
Al iniciar el análisis se exige consentimiento activo, se crea la sesión y se
envían JPEG al WebSocket `/ws/activity`. Si falta consentimiento, la pantalla lo
explica antes de pedir permiso de cámara. El flujo incluye landmarks opcionales,
progreso y limpieza al cancelar, completar o abandonar.
El selector permite FER+ ONNX (predeterminado) o HardlyHumans ViT/PyTorch
(experimental). La inferencia ocurre en FastAPI: la RAM y CPU relevantes son las
del servidor, no las del navegador del estudiante. `GET /analysis/models`
requiere autenticación y muestra disponibilidad, advertencias o bloqueo según
informes de benchmark y recursos actuales. El WebSocket reevalúa antes de
cargar; no hay cambio silencioso de modelo ni conmutación durante la sesión.
El ID y la versión del clasificador cargado aparecen en el detalle de la
sesión; las sesiones anteriores pueden mostrar «No registrado».
Para instalar, medir y habilitar cada modelo, consultar
[modelos faciales y admisión](../docs/emotion-model-candidates.md).

La comprobación de cierre de la navegación por rol y los casos especiales está
en [Fase 1: navegación web](../docs/web-navigation-phase1.md).

Las actividades se administran por API y persisten en PostgreSQL. Antes de arrancar
FastAPI, aplicar las migraciones desde la raíz. Para dominios separados configurar
CORS/hosts/orígenes y el proxy de producción:
[preparación para producción](../docs/production-readiness.md).
# Primer acceso

Administración crea cuentas en **Usuarios**. El servidor muestra una clave
provisional única una sola vez; el usuario la cambia al entrar. Los estudiantes
pueden aceptar o rechazar por ahora el análisis facial en **Consentimiento** y
revocar una aceptación previa. La institución debe configurar una política
aprobada mediante `CONSENT_POLICY_VERSION` y `CONSENT_POLICY_URL` en el backend;
sin ella no se habilita el análisis. Una cuenta demo existente puede recibir
una nueva clave provisional desde **Usuarios → Restablecer clave**.
