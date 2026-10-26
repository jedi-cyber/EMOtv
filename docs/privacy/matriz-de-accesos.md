# Matriz de accesos

> Derivada de `AuthorizationService` (`src/emotv/application/authorization_service.py`:
> `can_access_session` y `ROLE_ACTIONS`), de los servicios
> de cada módulo y de las pruebas que lo comprueban (lista al final). Todas las
> restricciones las aplica el servidor (FastAPI); la interfaz solo oculta lo que
> el servidor ya rechaza. Sujeta a revisión de la Facultad.

## Cuentas

| Papel interno | En pantalla | Quién es |
| --- | --- | --- |
| `superadmin` | Superadministrador | Soporte técnico |
| `admin` | Administrador | Persona con cargo superior en la Facultad (una cuenta activa por defecto, `MAX_ADMIN_ACCOUNTS=1`) |
| `psychologist` | Docente | Tiene un grupo de usuarios y también conduce sesiones propias |
| `student` | Usuario | Conduce sesiones, propias o con otras personas; tiene un solo docente |

Las **personas evaluadas no se registran ni tienen cuenta**: cada sesión lleva
solo un código aleatorio. Solo ven, desde un enlace temporal
(`/participant-view/{token}`, guardado como hash y válido mientras dura la
sesión), los estímulos y un botón para pedir parar. Nunca reciben expresiones,
probabilidades, calidad ni notas.

## Regla central

`can_access_session(cuenta, sesión)` es verdadera solo si la cuenta está activa,
es usuario o docente, y:

1. condujo la sesión, **o**
2. es el docente asignado **en este momento** a quien la condujo.

Se aplica a todo lo de la sesión: capturas, cuestionarios, respuestas,
marcadores, lo que dijo ver, línea de tiempo, métricas, reporte y eliminación.
Si un usuario cambia de grupo, el acceso pasa al nuevo docente. El
administrador y el superadministrador nunca acceden. Cada acceso denegado queda
en la auditoría sin contenido. No hay seguimiento ni estadísticas por persona.

## Qué ve y qué puede hacer cada cuenta

✓ = puede · — = no puede · «propias» = conducidas por la cuenta · «del grupo» = conducidas por los usuarios asignados a ese docente.

| Acción | Superadministrador | Administrador | Docente | Usuario |
| --- | --- | --- | --- | --- |
| **Sesiones** | | | | |
| Iniciar una sesión en el Analizador, con o sin protocolo (tras aceptar el compromiso y confirmar la autorización) | — | — | ✓ | ✓ |
| Ver sesiones, capturas, respuestas, línea de tiempo y métricas | — | — | Propias y del grupo | Propias |
| Pedir la eliminación de una sesión | — | — | Propias | Propias |
| Ejecutar la eliminación con acta | — | — | Propias y del grupo | — |
| Ver e imprimir un acta de eliminación | — | — | Si la ejecutó o la pidió | Si la pidió |
| **Reportes** | | | | |
| Redactar el reporte de una sesión que condujo | — | — | ✓ (se cierra sin revisión) | ✓ |
| Comentar, aprobar o devolver un reporte | — | — | Reportes de su grupo | — |
| Imprimir un reporte aprobado | — | — | De sesiones propias y del grupo | De sesiones propias |
| **Material de sesión** | | | | |
| Crear estímulos | — | Para toda la institución | Para su grupo | — |
| Usar estímulos | — | Los institucionales | Institucionales y suyos | Institucionales y de su docente, si están activos |
| Crear protocolos y cuestionarios | — | — | ✓ | ✓ |
| Compartir un cuestionario con el grupo | — | — | ✓ | — |
| **Actividades** | | | | |
| Analizar la propia expresión y hacer actividades | — | — | ✓ | ✓ (con el consentimiento aceptado) |
| **Emi** | | | | |
| Usar a Emi y borrar la propia conversación | — (403) | — (403) | ✓ | ✓ |
| Ver conversaciones de otras cuentas | — | — | — | — |
| **Cuentas y sistema** | | | | |
| Crear, desactivar o reactivar cuentas y restablecer contraseñas | Solo la cuenta de administrador | Docentes y usuarios | — | — |
| Armar los grupos docente–usuarios | — | ✓ | — | — |
| Consultar la auditoría (`GET /audit`) | ✓ | ✓ | — | — |
| Editar o borrar la auditoría | — (no existe la operación) | — | — | — |
| Modelos de expresión, actividades, catálogo de expresiones, recomendaciones y políticas de consentimiento | ✓ | — | — | — |

Notas:

- El administrador ve de los usuarios solo datos de cuenta (correo, código,
  papel, estado y grupo) para armar los grupos; nunca sesiones ni resultados.
- La auditoría muestra quién hizo qué sobre qué recurso (por su id) y con qué
  resultado. No contiene notas, respuestas, correos ni imágenes, pero sí ids de
  sesiones y de cuentas.
- Una cuenta desactivada no accede a nada (`is_active` se comprueba en cada regla).
- El superadministrador crea la cuenta de administrador con
  `scripts/security/create_admin.py` en el servidor y recupera su contraseña con
  `scripts/security/reset_admin_password.py`; ninguno de los dos da acceso a
  sesiones.

## Pruebas que lo comprueban

| Prueba | Qué verifica |
| --- | --- |
| `tests/integration/test_privacy_accounts.py` | Administrador, superadministrador y otro usuario nunca acceden a una sesión; el docente ve solo su grupo; el acceso sigue al cambiar de grupo; un usuario no tiene dos docentes; solo el superadministrador crea el administrador; la gestión nunca llega a sesiones; compromiso y aviso de menores obligatorios; cifrado; auditoría sin contenido e inmodificable; una sola confirmación por sesión; código único; retención y eliminación por sesión con acta |
| `tests/integration/test_protocols_and_stimuli.py` | Público de cada protocolo, confirmación según el público, estímulos y protocolos por papel |
| `tests/integration/test_questionnaires.py` | Cuestionarios y respuestas cifradas, solo para quien condujo y su docente |
| `tests/integration/test_guided_sessions.py` | La pantalla de la persona no recibe resultados; solo quien conduce controla la sesión |
| `tests/integration/test_session_insights.py` y `test_session_reports.py` | Línea de tiempo, métricas y reportes por papel |
| `tests/integration/test_no_participant_images.py` | Ninguna ruta GET devuelve imágenes de personas evaluadas, con los cuatro papeles |
| `tests/integration/test_psychologist_assignments.py` | Asignación docente–usuario |
| `tests/unit/test_emi_chat.py` | Emi solo para usuarios y docentes; cada cuenta solo ve y borra sus conversaciones |
