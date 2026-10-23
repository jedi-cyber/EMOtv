# Matriz de accesos

> Derivada de `AuthorizationService` (`src/emotv/application/authorization_service.py`:
> `can_access_participant`, `can_access_session` y `ROLE_ACTIONS`), de los servicios
> de cada módulo y de las pruebas que lo comprueban (lista al final). Todas las
> restricciones las aplica el servidor (FastAPI); la interfaz solo oculta lo que
> el servidor ya rechaza. Sujeta a revisión de la Facultad.

## Cuentas

| Papel interno | En pantalla | Quién es |
| --- | --- | --- |
| `superadmin` | Superadministrador | Soporte técnico |
| `admin` | Administrador | Persona con cargo superior en la Facultad (una cuenta activa por defecto, `MAX_ADMIN_ACCOUNTS=1`) |
| `psychologist` | Docente | Tiene un grupo de usuarios y también conduce sesiones propias |
| `student` | Usuario | Conduce sesiones con sus participantes; tiene un solo docente |

Los **participantes no tienen cuenta**. Solo ven, desde un enlace temporal
(`/participant-view/{token}`, guardado como hash y válido mientras dura la
sesión), los estímulos y un botón para pedir parar. Nunca reciben expresiones,
probabilidades, calidad ni notas.

## Regla central

`can_access_participant(cuenta, participante)` es verdadera solo si la cuenta
está activa, es usuario o docente, y:

1. registró al participante, **o**
2. es el docente asignado **en este momento** a quien lo registró.

Se aplica a todo lo del participante: autorizaciones, sesiones, capturas,
cuestionarios, respuestas, marcadores, línea de tiempo, métricas, tendencias y
reportes. Si un usuario cambia de grupo, el acceso pasa al nuevo docente. Cada
consulta, y cada acceso denegado, queda en la auditoría sin contenido.

## Qué ve y qué puede hacer cada cuenta

✓ = puede · — = no puede · «propios» = registrados por la cuenta · «del grupo» = registrados por los usuarios asignados a ese docente.

| Acción | Superadministrador | Administrador | Docente | Usuario |
| --- | --- | --- | --- | --- |
| **Participantes** | | | | |
| Registrar participantes (tras aceptar el compromiso) | — | — | ✓ | ✓ |
| Ver participantes, notas y autorizaciones | — | — | Propios y del grupo | Propios |
| Registrar y retirar autorizaciones firmadas | — | — | Propios y del grupo | Propios |
| Iniciar una sesión con un participante | — | — | Solo propios | Solo propios |
| Ver sesiones, capturas, respuestas, línea de tiempo, métricas y tendencias | — | — | Propios y del grupo | Propios |
| Solicitar la eliminación de un participante | — | — | Solo propios | Solo propios |
| Ejecutar la eliminación con acta | — | — | Propios y del grupo | — |
| Ver la lista de participantes por vencer | — | — | ✓ | — |
| Ver e imprimir un acta de eliminación | — | — | Si la ejecutó o la solicitó | Si la solicitó |
| **Reportes** | | | | |
| Redactar el reporte de una sesión que condujo | — | — | ✓ (se cierra sin revisión) | ✓ |
| Comentar, aprobar o devolver un reporte | — | — | Reportes de su grupo | — |
| Imprimir un reporte aprobado | — | — | Propios y del grupo | Propios |
| **Material de sesión** | | | | |
| Crear estímulos | — | Para toda la institución | Para su grupo | — |
| Usar estímulos | — | Los institucionales | Institucionales y suyos | Institucionales y de su docente, si están activos |
| Crear protocolos y cuestionarios | — | — | ✓ | ✓ |
| Aprobar protocolos para niños | — | — | Los de su grupo y los suyos | — |
| Compartir un cuestionario con el grupo | — | — | ✓ | — |
| **Sesiones propias** | | | | |
| Analizar la propia expresión y hacer actividades | — | — | ✓ | ✓ (con el consentimiento aceptado) |
| Ver sesiones propias | — | — | Propias y de su grupo | Propias |
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
  participantes y de cuentas.
- Una cuenta desactivada no accede a nada (`is_active` se comprueba en cada regla).
- El superadministrador crea la cuenta de administrador con
  `scripts/security/create_admin.py` en el servidor y recupera su contraseña con
  `scripts/security/reset_admin_password.py`; ninguno de los dos da acceso a
  participantes.

## Pruebas que lo comprueban

| Prueba | Qué verifica |
| --- | --- |
| `tests/integration/test_privacy_accounts.py` | Administrador, superadministrador y otro usuario nunca acceden a un participante; el docente ve solo su grupo; el acceso sigue al cambiar de grupo; un usuario no tiene dos docentes; solo el superadministrador crea el administrador; la gestión nunca llega a sesiones; compromiso y aviso de menores obligatorios; cifrado; auditoría sin contenido e inmodificable; retención y eliminación con acta |
| `tests/integration/test_participant_practices.py` | Autorizaciones, estímulos y protocolos por papel |
| `tests/integration/test_questionnaires.py` | Cuestionarios y respuestas cifradas, solo para quien condujo y su docente |
| `tests/integration/test_guided_sessions.py` | La vista del participante no recibe resultados; solo quien conduce controla la sesión |
| `tests/integration/test_session_insights.py` y `test_session_reports.py` | Línea de tiempo, métricas, tendencias y reportes por papel |
| `tests/integration/test_no_participant_images.py` | Ninguna ruta GET devuelve imágenes de participantes, con los cuatro papeles |
| `tests/integration/test_psychologist_assignments.py` | Asignación docente–usuario |
| `tests/unit/test_emi_chat.py` | Emi solo para usuarios y docentes; cada cuenta solo ve y borra sus conversaciones |
