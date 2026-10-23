# Compromiso de confidencialidad

> El compromiso **no sustituye las obligaciones de la institución** como
> responsable del tratamiento (`[1: RESPONSABLE DEL TRATAMIENTO]`) según la Ley
> N.° 29733 y el D.S. 016-2024-JUS. **Debe confirmarse con asesoría legal cómo
> se reparte la responsabilidad** entre la institución, quien usa el sistema y
> quien lo administra técnicamente. Aprobado el `[8: FECHA DE APROBACIÓN DEL COMPROMISO]`.

## Cómo funciona en el sistema

- El texto vive en `src/emotv/resources/confidentiality_commitment.md`, con su
  versión en el encabezado. La versión vigente es **`2026-10-provisional`**,
  marcada como provisional hasta que la Facultad la apruebe.
- Lo aceptan **usuarios y docentes** en su primer ingreso y cada vez que cambia
  la versión. El administrador y el superadministrador no lo aceptan porque no
  acceden a participantes.
- Sin aceptarlo, el servidor rechaza registrar participantes e iniciar sesiones
  con ellos (respuesta `428`).
- Antes de registrar al primer niño o niña, la cuenta acepta además el **aviso
  reforzado sobre datos de menores** (`src/emotv/resources/child_data_notice.md`,
  versión `2026-10-provisional`).
- Cada aceptación se guarda con la cuenta, la versión y la fecha
  (`commitment_acceptances`) y queda en la auditoría.
- Antes de cada sesión guiada se muestra un recordatorio del compromiso.

Al aprobarlo, la Facultad debe cambiar la versión en el encabezado del archivo
(y quitar `provisional: true`); el sistema pedirá entonces a todas las cuentas
aceptar la versión nueva.

## Texto vigente (versión `2026-10-provisional`)

> **Texto provisional:** está pendiente de la revisión de la Facultad de
> Psicología de la UNHEVAL y puede cambiar. Cuando cambie su versión, se te
> pedirá aceptarlo de nuevo.
>
> **Qué hace el sistema**
>
> - EMOtv **no guarda imágenes** de las personas. La cámara se usa solo durante
>   el análisis y cada cuadro se descarta en el momento.
> - Los participantes no tienen cuenta ni nombre en el sistema: se identifican
>   con un código.
> - Los datos están protegidos con **controles de acceso** (solo los ve quien
>   registró al participante y su docente), **cifrado** de las notas y
>   respuestas, y una **auditoría** de cada consulta, creación, impresión y
>   eliminación.
> - El sistema estima una expresión facial; no diagnostica ni determina el
>   estado psicológico de nadie.
>
> **A qué te comprometes**
>
> - No compartir, fotografiar ni grabar la pantalla mientras uses EMOtv con
>   datos de participantes.
> - No divulgar fuera del sistema los códigos de los participantes, sus
>   resultados ni sus respuestas.
> - No compartir imágenes de participantes por ningún medio: está prohibido.
> - Usar los datos solo dentro de EMOtv y para la finalidad autorizada.
>
> **Responsabilidad**
>
> El sistema protege los datos mientras permanecen dentro de él. Si los datos
> salen por un medio ajeno a esas protecciones (una foto, una captura de
> pantalla, un mensaje, una copia), **la responsabilidad es de quien los sacó**.

## Aviso reforzado sobre datos de menores (versión `2026-10-provisional`)

> **Texto provisional:** pendiente de la revisión de la Facultad de Psicología
> de la UNHEVAL.
>
> Los datos de menores de edad son **más sensibles** que los de una persona
> adulta: un niño no puede decidir por sí mismo cómo se usan y una filtración
> puede afectarle durante más tiempo.
>
> - Necesitas la **autorización firmada en papel** del padre, la madre o el
>   tutor, y el **asentimiento** del niño o la niña. Sin eso no hay sesión.
> - El padre, la madre o el tutor **debe estar presente** durante la sesión.
> - Registra solo lo necesario. No escribas nombres, colegios, direcciones ni
>   rasgos que permitan reconocer al niño en las notas.
> - Nunca fotografíes ni grabes la pantalla, y no compartas su código ni sus
>   resultados fuera de EMOtv.

## Qué asume cada parte

Esta división describe lo que hace el sistema y lo que pide el compromiso; no es
una asignación legal de responsabilidades.

| Le corresponde al sistema (lo aplica el código) | Le corresponde a quien usa el sistema |
| --- | --- |
| No guardar imágenes: los cuadros de la cámara se analizan en memoria y se descartan | No fotografiar, grabar ni capturar la pantalla |
| Identificar a los participantes solo por código, sin nombre, DNI ni foto (la API rechaza esos campos) | No escribir nombres, DNI, colegios, direcciones ni rasgos reconocibles en notas, respuestas, reportes o mensajes a Emi |
| Limitar el acceso a quien registró al participante y su docente, en el servidor | No compartir su contraseña ni dejar la sesión abierta en un equipo compartido |
| Cifrar notas, respuestas, comentarios y reportes | Custodiar las fichas código–persona y los formatos firmados en papel |
| Auditar cada consulta, impresión y eliminación, sin contenido | Usar los datos solo para la finalidad formativa autorizada |
| Borrar los datos al vencer la retención y generar un acta en cada eliminación a pedido | Entregar los reportes impresos solo al participante adulto o a su tutor, y no hacer copias adicionales |
| Bloquear en Emi los mensajes con DNI, correos o teléfonos y no enviarle datos de participantes | Avisar de inmediato ante una sospecha de filtración ([procedimiento-incidentes.md](procedimiento-incidentes.md)) |

Le corresponde a la **institución**, y no se resuelve con este compromiso:
aprobar la política, el formato de autorización y el plazo de retención;
designar el contacto para ejercer derechos; operar el servidor de forma segura
([checklist-despliegue-seguro.md](checklist-despliegue-seguro.md)); atender
solicitudes e incidentes; y cumplir las demás obligaciones del responsable del
tratamiento. `[Verificar con asesoría legal.]`
