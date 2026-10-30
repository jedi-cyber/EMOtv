# Política de privacidad de EMOtv

> **Documento sujeto a revisión y aprobación de la Facultad.** Los datos entre
> corchetes y numerados (por ejemplo, `[1: RESPONSABLE DEL TRATAMIENTO]`) los
> completa la Facultad; la lista está en el [README](README.md#datos-que-debe-completar-la-facultad).
> Se basa en la Ley N.° 29733 y su reglamento (Decreto Supremo 016-2024-JUS).

Versión del documento: borrador del 2026-10-23 · Aprobada el `[5: FECHA DE APROBACIÓN DE LA POLÍTICA]`
por `[6: ÓRGANO QUE APRUEBA]`.

## ¿Qué es EMOtv?

EMOtv es una herramienta de la Facultad de Psicología de la UNHEVAL. La usan
personas de la Facultad (usuarios y docentes) en sesiones propias o con
personas adultas, niños y niñas. Durante una sesión se muestran imágenes, se pueden
responder preguntas y una cámara **estima la expresión de la cara**.

EMOtv **no diagnostica**, no dice lo que una persona siente ni sustituye a un
profesional. La expresión estimada es solo un apoyo.

## ¿Quién es responsable de tus datos?

`[1: RESPONSABLE DEL TRATAMIENTO]`, con domicilio en `[2: DOMICILIO DEL RESPONSABLE]`.
Para cualquier consulta o para ejercer tus derechos: `[3: CONTACTO PARA EJERCER DERECHOS]`.

## ¿Qué datos tuyos se guardan?

**No se guarda tu nombre, tu DNI ni tu foto.** En el sistema eres un código, por
ejemplo `P-7KQ2MD`. La hoja de papel que relaciona ese código contigo la guarda
el docente responsable, fuera del sistema.

Se guarda:

| Dato | Ejemplo | Protección |
| --- | --- | --- |
| Tu código, si eres adulto o niño, y tu edad en años | `P-7KQ2MD`, niño, 8 años | Acceso restringido |
| Lo que autorizaste en el formato de papel: versión del formato, fecha y las casillas marcadas | Participación sí, cámara sí | Acceso restringido. No se guarda quién firmó |
| La **expresión estimada** por la cámara en cada momento de la sesión, con su nivel de confianza y si la imagen tenía buena calidad | «Sorpresa (estimada)» | Acceso restringido |
| Tus respuestas a los cuestionarios | Una carita, un sí o no, un texto | Cifradas |
| Lo que dijiste ver en una imagen abstracta | «Una nube» | Cifrado |
| Notas y marcas de quien condujo la sesión | «Se distrajo», «Pidió parar» | Las notas, cifradas |
| El reporte de la sesión y los comentarios del docente | Texto del reporte | Cifrados |

**Ninguna imagen tuya se guarda ni sale del servidor.** La cámara envía cada
imagen al servidor de EMOtv, que la analiza en ese instante y la descarta. Las
únicas imágenes guardadas son las que se te muestran (estímulos), que suben los
docentes, la administración o los usuarios para sus protocolos; nunca son fotos
de las personas evaluadas. Las que suben los usuarios pasan por una detección
automática de personas, que no es infalible, y por la revisión del docente.

## ¿Para qué se usan?

Solo para la actividad formativa de la Facultad de Psicología: conducir la
sesión, describir lo que ocurrió en ella y que el docente revise el trabajo de
quien la condujo. EMOtv no calcula puntajes de tus respuestas ni las interpreta,
y no relaciona las imágenes abstractas con ninguna condición.

La base para tratar tus datos es tu **consentimiento** (o el de tu padre, madre o
tutor si eres menor de edad), firmado en papel, con dos autorizaciones separadas:
participar y usar la cámara. Sin las dos no hay sesión. Si eres niño o niña,
además se te pregunta si quieres participar. `[Verificar con asesoría legal: la
base de legitimación y los requisitos del consentimiento de menores según la
Ley N.° 29733 y el D.S. 016-2024-JUS.]`

## ¿Quién puede ver tus datos?

- La persona que te registró y condujo la sesión (usuario o docente).
- El docente a cargo de esa persona.

Nadie más. La administración de la Facultad y el soporte técnico **no pueden ver**
tus datos ni tus resultados, y el sistema anota cada vez que alguien los consulta
(sin copiar su contenido).

## ¿Interviene algún servicio externo?

- **Ninguno recibe tus imágenes.** El análisis de la cara se hace con modelos que
  funcionan dentro del servidor de EMOtv, sin servicios externos de visión.
- EMOtv tiene un asistente, **Emi**, que solo usan usuarios y docentes. Emi
  funciona con servicios externos en la nube (n8n y Groq), pero **nunca recibe
  tus datos**: ni tu código, ni tus respuestas, ni tus resultados. El servidor
  bloquea los mensajes a Emi que contienen un DNI, un correo o un teléfono.
  `[Verificar con asesoría legal: si el uso de estos servicios constituye flujo
  transfronterizo de datos de usuarios y docentes y qué requisitos aplica.]`
- El servidor se ubica en `[12: UBICACIÓN DEL SERVIDOR Y DE LOS RESPALDOS]`.

## ¿Cuánto tiempo se guardan?

Tus datos se borran automáticamente **`[9: PLAZO DE RETENCIÓN APROBADO]`** después
de registrarte (el sistema viene configurado en 12 meses de 30 días, es decir,
360 días desde el registro). Al borrarte se eliminan todos tus registros: sesiones,
respuestas, expresiones estimadas, notas y reportes.

Las copias de seguridad cifradas pueden conservar tus datos hasta que se
eliminen; la Facultad debe borrarlas dentro del mismo plazo.

## ¿Qué derechos tienes y cómo los ejerces?

Tú (o tu padre, madre o tutor si eres menor de edad) puedes pedir:

- **Acceso:** saber qué datos tuyos hay. El docente te entrega una copia impresa
  del reporte aprobado de tu sesión.
- **Rectificación:** corregir un dato equivocado.
- **Cancelación:** que se borren tus datos. El docente los elimina y el sistema
  genera un acta de eliminación, sin datos personales.
- **Oposición:** dejar de participar. Desde ese momento no se hacen sesiones
  nuevas contigo y el docente decide la eliminación de tus datos.

También puedes **retirar** tu autorización (o la de tu hijo o hija) cuando
quieras, sin dar explicaciones.

Para hacerlo, comunícate con `[3: CONTACTO PARA EJERCER DERECHOS]` o con el
docente responsable. Ten a mano tu código o la hoja que te entregaron, porque el
sistema no conoce tu nombre. El procedimiento está en
[procedimiento-derechos.md](procedimiento-derechos.md). Si no estás de acuerdo
con la respuesta, puedes acudir a la autoridad de protección de datos personales.
`[Verificar con asesoría legal: plazos de respuesta y canal ante la autoridad.]`

## ¿Cómo se protegen?

- Acceso solo para quien te registró y su docente, comprobado por el servidor.
- Cifrado de respuestas, notas, comentarios y reportes.
- Registro de cada consulta, impresión y eliminación.
- Las personas que usan EMOtv aceptan un compromiso de confidencialidad: no
  fotografiar ni grabar la pantalla y no sacar tus datos del sistema.

## Cambios en esta política

Si esta política cambia, la nueva versión se publicará con su fecha. Para usar
los datos con otra finalidad se pedirá una nueva autorización.
