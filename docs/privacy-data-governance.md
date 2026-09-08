# Política preliminar de privacidad y gobierno de datos de EMOtv

**Estado:** borrador técnico para aprobación institucional.  
**Propietario propuesto:** Universidad Nacional Hermilio Valdizán (por confirmar).  
**Revisión obligatoria:** Facultad de Psicología, asesoría jurídica, seguridad/TI
y responsable institucional de protección de datos.

Esta política no sustituye asesoría legal. Antes de usar EMOtv con personas
reales, la Universidad debe aprobar el texto de consentimiento, registrar o
declarar los bancos de datos que correspondan, realizar una evaluación de
impacto y designar responsables y canales para ejercer derechos.

## Principios

- finalidad específica y comunicada;
- minimización y privacidad desde el diseño;
- acceso por necesidad de conocer y mínimo privilegio;
- consentimiento demostrable, versionado y revocable;
- exactitud, trazabilidad, seguridad y eliminación verificable;
- ninguna inferencia equivale a diagnóstico psicológico;
- no reutilizar datos para investigación, docencia o entrenamiento sin base y
  consentimiento específicos.

## Datos y retención propuesta

| Categoría | Ejemplos | Retención propuesta | Fin del plazo |
| --- | --- | --- | --- |
| Video y fotogramas crudos | webcam, rostro, cuerpo | **No almacenar**; solo memoria durante procesamiento | descarte inmediato |
| Sesiones identificables | emoción facial, actividad, cumplimiento, duración | mientras exista atención activa + 12 meses | anonimizar o eliminar en 30 días |
| Cuenta y perfil estudiantil | correo, código, rol | relación vigente + 90 días | eliminar o disociar |
| Evidencia de consentimiento | versión, aceptación, revocación | relación vigente + 5 años, sujeto a validación legal | eliminación segura |
| Logs de acceso y seguridad | usuario, acción, fecha, resultado | 12 meses | eliminación automática |
| Backups cifrados | copia de datos persistentes | máximo 90 días, rotación cerrada | vencimiento automático |
| Investigación | datos pseudonimizados | según protocolo aprobado y consentimiento separado | fecha del protocolo |

Los plazos son una propuesta inicial. Jurídica debe confirmar obligaciones de
archivo, investigación, defensa de reclamaciones y normas universitarias. Una
retención superior exige finalidad documentada y aprobación.

## Acceso

| Actor | Acceso permitido |
| --- | --- |
| Estudiante | su perfil, consentimientos y sesiones propias |
| Psicólogo asignado | sesiones de estudiantes bajo su atención; no contraseñas ni secretos |
| Administrador funcional | usuarios, roles y configuración; sin contenido clínico por defecto |
| Administrador TI | operación técnica; acceso excepcional, temporal y auditado |
| Investigador | conjunto pseudonimizado aprobado; sin acceso directo a identidad |
| Terceros | prohibido salvo contrato, base válida, información al titular y aprobación institucional |

Todo acceso debe autenticarse, autorizarse en servidor y registrarse. Las cuentas
compartidas están prohibidas. El acceso de Psicología requerirá en una fase
posterior una relación explícita psicólogo–estudiante; el rol por sí solo no debe
dar acceso indiscriminado en producción.

## Consentimiento

Antes de asociar una sesión a un estudiante, debe existir consentimiento activo
para la versión vigente. La interfaz debe informar como mínimo:

- responsable y contacto institucional;
- datos tratados y cuáles no se almacenan;
- finalidad asistencial/educativa concreta;
- ausencia de diagnóstico automatizado;
- destinatarios y transferencias;
- plazo de conservación;
- carácter facultativo y consecuencias de no consentir;
- mecanismo de revocación y ejercicio de derechos;
- uso separado para investigación o entrenamiento, desmarcado por defecto.

La revocación impide iniciar nuevas sesiones asociadas. No reactiva ni altera
silenciosamente consentimientos históricos.

## Eliminación y anonimización

1. Verificar identidad y alcance de la solicitud.
2. Suspender nuevos tratamientos cuando corresponda.
3. Identificar datos activos, derivados, logs y backups.
4. Evaluar una retención legal documentada; no usarla como bloqueo genérico.
5. Eliminar o anonimizar irreversiblemente dentro del plazo aprobado.
6. Propagar la baja a copias y terceros en su siguiente ciclo de purga.
7. Conservar solamente evidencia mínima de atención de la solicitud.
8. Notificar al titular el resultado o la razón legal de una limitación.

Nunca se debe hacer `DELETE` físico sin auditoría y autorización. En desarrollo,
usar IDs ficticios y bases separadas.

## Seguridad mínima antes de producción

- TLS en tránsito y cifrado administrado en almacenamiento/backups;
- Argon2id para contraseñas y secretos fuera del repositorio;
- JWT de corta duración, revocación/sesiones de acceso y rotación de claves;
- MFA para Psicología, administración y TI;
- auditoría de lectura, exportación, modificación y eliminación;
- separación entre desarrollo, pruebas y producción;
- backups probados y procedimiento de incidentes;
- evaluación de impacto de privacidad y pruebas de seguridad;
- prohibición de logs con tokens, contraseñas, imágenes o cadenas de conexión.

## Responsabilidades por aprobar

| Decisión | Universidad | Psicología | TI/Seguridad | Jurídica/Privacidad |
| --- | --- | --- | --- | --- |
| Finalidades y responsable del banco | aprueba | consulta | informa | valida |
| Texto y versión del consentimiento | aprueba | valida lenguaje | implementa | valida legalmente |
| Acceso psicólogo–estudiante | supervisa | responsable funcional | implementa/audita | consulta |
| Retención y eliminación | aprueba | justifica necesidad | automatiza | valida |
| Investigación y datos derivados | comité competente | protocolo | controles técnicos | valida |
| Incidentes y notificaciones | responsable institucional | coopera | detecta/contiene | dirige cumplimiento |

## Prohibiciones

- diagnóstico clínico automatizado;
- almacenar video crudo por defecto;
- entrenar modelos con sesiones sin consentimiento separado;
- exportar datos identificables a cuentas personales;
- usar datos para disciplina, calificación o vigilancia;
- permitir que un administrador técnico consulte contenido por conveniencia;
- desplegar antes de contar con aprobación institucional y canal de derechos.

## Aprobaciones pendientes

- responsable formal y encargado(s) del tratamiento;
- contacto para derechos de acceso, rectificación, cancelación y oposición;
- plazos finales de cada categoría;
- relación y alcance de psicólogos asignados;
- texto `privacy-v1` y procedimiento de cambio de versión;
- tratamiento de menores de edad, si llegara a aplicar;
- ubicación de hosting, proveedores y transferencias internacionales;
- procedimiento y plazos de respuesta a incidentes;
- evaluación de impacto y revisión del comité de ética para investigación.

## Marco de referencia

- Ley peruana N.º 29733, Ley de Protección de Datos Personales.
- Decreto Supremo N.º 016-2024-JUS, reglamento vigente desde el 31 de marzo de
  2025.
- Políticas internas de seguridad, archivo, investigación y ética de UNHEVAL,
  que deben ser incorporadas por la institución.
