# Emi: chatbot educativo con Sim

Emi responde a **usuarios y docentes** preguntas de Psicología en general (incluida
la evaluación infantil) y sobre el uso de EMOtv. No diagnostica ni etiqueta a
ninguna persona concreta, no determina el estado psicológico de nadie, no
reemplaza al docente y no sustituye la atención psicológica ni los servicios de
emergencia.

Las personas evaluadas no se registran ni tienen cuenta, así que nunca acceden
a Emi. FastAPI rechaza con 403 a las cuentas de administración y la interfaz no
muestra a Emi ni en la pantalla de la persona ni en la sesión con protocolo,
donde hay una persona evaluada delante.

## Arquitectura

```text
React (AssistantWidget) → FastAPI (/chat) → workflow de Emi en Sim (API) → modelo de lenguaje
```

`CHAT_PROVIDER` elige el workflow: `sim` (vigente) o `n8n` (el workflow anterior
de n8n Cloud, cuyo periodo de prueba terminó; queda como opción). Los dos
cumplen el mismo contrato hacia FastAPI.

| Parte | Responsabilidad |
| --- | --- |
| FastAPI | Autenticación y papel (usuario o docente), límites de uso, filtros de riesgo e identificadores, historial, borrado, retención y contador de rechazos |
| Workflow (Sim o n8n) | Bloquear intentos de cambiar las reglas, clasificar el alcance (si la clasificación falla, la pregunta se trata como fuera de alcance) y responder como Emi, con la descripción fija de EMOtv más `knowledge`. No guarda conversaciones |

El workflow se administra en Sim y **no se modifica desde este repositorio**.
Su configuración está en [chatbot/sim-setup.md](chatbot/sim-setup.md) y la
descripción fija de EMOtv que guarda, en
[chatbot/emotv-descripcion-sim.md](chatbot/emotv-descripcion-sim.md).

## Contrato del workflow

Con Sim: `POST SIM_WORKFLOW_URL` con la cabecera `X-API-Key: SIM_API_KEY` y el
cuerpo de abajo dentro de `{"input": ...}`; la respuesta llega en
`data.output` ([chatbot/sim-setup.md](chatbot/sim-setup.md)). Con n8n:
`POST N8N_WEBHOOK_URL` con la cabecera `X-EMOtv-Key: N8N_WEBHOOK_KEY` y el
cuerpo tal cual.

```json
{
  "request_id": "uuid generado por FastAPI",
  "question": "texto de la pregunta",
  "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
  "knowledge": "# Conocimiento de EMOtv ... (posturas, actividades, expresiones, flujo, datos y roles)"
}
```

| Respuesta | Cuerpo | EMOtv responde |
| --- | --- | --- |
| 200 | `{"answer", "in_scope", "category", "request_id"}` | 200 con `{conversation_id, answer, in_scope, category}`. Sin `answer` o sin `in_scope` booleano se trata como error (502) |
| 502 (n8n), o en Sim una ejecución `failed`, 402 o 429 | `{"error": "llm_unavailable", "answer", "request_id"}` | 502: el servicio de IA no está disponible |
| 401/403 | La clave no coincide o no tiene acceso | 502: problema de configuración del servidor |
| 404 | El workflow no está publicado o desplegado | 502: el asistente no está activo |
| Timeout (`CHAT_TIMEOUT_SECONDS`, 30 s) | — | 504 |
| Cualquier otro fallo | — | 502 |

`knowledge` lleva el conocimiento verificado de EMOtv que genera
`emotv.application.emi_knowledge`: textos fijos (flujo de uso, sesiones y
autorizaciones, protocolos y sesión con protocolo, línea de tiempo y métricas, estados
del reporte, limitaciones del reconocimiento facial, qué se guarda y roles) y,
desde la base de datos, las cinco posturas, las actividades y sus pasos y los
textos del catálogo de expresiones. Los textos fijos van primero: si hay que
recortar, solo se acorta el contenido editable. Se guarda en caché en memoria, se regenera cuando administración
edita actividades o el catálogo (y, como respaldo, cada 10 minutos) y su tamaño
se registra en el log. Debe quedar por debajo de 12 000 caracteres, porque el
workflow anterior cortaba lo que excedía; si el contenido crece, los textos se acortan y
una prueba falla si se supera el límite. No incluye datos de ningún usuario
ni de ninguna persona evaluada: ni sesiones, ni reportes, ni resultados.

Al workflow **nunca** se envían datos de personas evaluadas, resultados
emocionales, sesiones, reportes, nombres, correos ni el id del usuario. El
contrato no cambia: el workflow se modifica en Sim, aparte de este
repositorio. La configuración anterior de n8n queda en
[chatbot/n8n-setup.md](chatbot/n8n-setup.md).

## Qué hace FastAPI antes de llamar al workflow

1. Rechaza preguntas vacías o de más de `CHAT_MAX_QUESTION_CHARS` caracteres (1000).
2. Aplica los límites por usuario: `CHAT_LIMIT_WINDOW_MESSAGES` mensajes (20)
   cada `CHAT_LIMIT_WINDOW_MINUTES` minutos (10) y `CHAT_LIMIT_DAILY_MESSAGES`
   (200) en 24 horas. Se cuentan las preguntas guardadas; al superarlos responde
   429 con un mensaje en español.
3. Filtro de riesgo (`emotv.application.chat_safety`): una lista corta de
   patrones, como ideación de autolesión. Si coincide, **no se llama al workflow
   ni se guarda el texto**: se responde con `CHAT_RISK_MESSAGE`, que deriva a
   una persona de confianza, a un profesional o a los servicios de emergencia
   de la localidad. No incluye números de teléfono.
4. Filtro de identificadores (`emotv.application.chat_safety`): si la pregunta
   contiene un DNI (8 dígitos, también con puntos), un correo electrónico o un
   teléfono (7 o de 9 a 15 dígitos, con o sin espacios, guiones o paréntesis),
   **no se llama al workflow ni se guarda el texto**. Se responde con un mensaje
   fijo que pide quitar los datos que identifiquen a una persona, con
   `category: "filtro_identificadores"`. El contador solo suma esa categoría;
   el log tampoco guarda el texto ni el tipo de dato. Las secuencias formadas
   solo por años («2024-2025») no se bloquean. El filtro es conservador: ante la
   duda bloquea, porque el mensaje se puede reescribir.
5. Un mensaje que describe un caso, sin identificadores detectables, se envía
   tal como lo escribió la persona: FastAPI no lo reescribe ni lo resume. La
   interfaz muestra siempre el aviso de no escribir nombres ni datos de niños o
   familias; los nombres no se pueden detectar de forma fiable y dependen de
   ese aviso.
6. Envía como historial los últimos `CHAT_HISTORY_MESSAGES` mensajes (10) de
   esa conversación que estuvieron dentro de alcance. Las preguntas con
   `in_scope=false` y sus respuestas fijas no se envían, para que un tema ajeno
   no contamine el historial.

Cada petición recibe un `request_id` (UUID) que se registra en el log con el
código de respuesta del workflow (`gateway_status`). El log nunca incluye la clave ni el texto de los
mensajes.

## Datos que guarda EMOtv

- `chat_conversations` y `chat_messages`: preguntas y respuestas por usuario,
  con `in_scope` y `category`. Cada usuario solo accede a sus conversaciones.
  Una pregunta queda con `in_scope` nulo si el workflow no respondió: cuenta para los
  límites, pero no se envía como historial.
- `chat_rejection_counts`: número de rechazos por categoría (ver
  [Categorías](#categorías)), sin el texto de las preguntas.
- Cada persona puede borrar su conversación desde Emi («Borrar conversación»):
  se eliminan la conversación y sus mensajes. El contador de rechazos no
  cambia, porque no guarda texto ni se vincula a nadie.
- Retención: se borran los mensajes de más de `CHAT_RETENTION_DAYS` días (90)
  al arrancar la API y en cada pregunta. En las pruebas con voluntarios, los
  datos de su cuenta se eliminan como máximo a los 30 días
  ([testing/volunteer-protocol.md](testing/volunteer-protocol.md)).

## API

| Método | Ruta | Uso |
| --- | --- | --- |
| `POST` | `/chat` | `{conversation_id?, question}` → `{conversation_id, answer, in_scope, category}` |
| `GET` | `/chat/conversations/current` | Últimos 30 mensajes de la conversación más reciente |
| `POST` | `/chat/conversations` | Crea una conversación nueva |
| `DELETE` | `/chat/conversations/{id}` | Borra la conversación propia y sus mensajes (`204`; `404` si no es suya) |

Todas las rutas exigen una cuenta de usuario o docente; con otro papel
responden `403`.

## Categorías

`emotv.application.chat_categories` define las categorías que acepta el
contador. El clasificador del workflow EMI debe usar estas:

| Categoría | in_scope | Uso |
| --- | --- | --- |
| `psicologia_general` | true | Conceptos, teorías, ética y métodos de la Psicología |
| `evaluacion_infantil` | true | Evaluación y trabajo con niños, en términos generales |
| `uso_emotv` | true | Uso de la plataforma, privacidad y datos |
| `limites_de_emi` | true | La persona pide un diagnóstico propio o cuenta cómo se siente: Emi explica sus límites |
| `matematica`, `idiomas`, `programacion`, `tareas` | false | Fuera de la disciplina |
| `diagnostico_persona` | false | Pide diagnosticar o etiquetar a una persona concreta |
| `reemplazo_docente` | false | Pide calificar, aprobar o decidir en lugar del docente |
| `cambio_de_reglas` | false | Intenta cambiar las instrucciones de Emi |
| `otro` | false | Cualquier otro tema |

El workflow añade `vacio`, `demasiado_largo` y `error_clasificador`, y FastAPI
añade `filtro_riesgo` y `filtro_identificadores` (esas preguntas nunca llegan al
workflow). Las etiquetas del clasificador anterior se traducen (`plataforma` y
`privacidad` → `uso_emotv`; `expresiones` y `otra_psicologia` →
`psicologia_general`) y cualquier etiqueta desconocida se cuenta como `otro`.

## Configuración

| Variable | Uso |
| --- | --- |
| `CHAT_PROVIDER` | `sim` (por defecto) o `n8n` |
| `SIM_WORKFLOW_URL` | `https://www.sim.ai/api/v2/workflows/<id>/execute` |
| `SIM_API_KEY` | Clave de API de Sim (cabecera `X-API-Key`) |
| `CHAT_TIMEOUT_SECONDS` | Espera máxima, 30 s (`N8N_TIMEOUT_SECONDS` se acepta como nombre anterior) |
| `N8N_WEBHOOK_URL`, `N8N_WEBHOOK_KEY` | Solo con `CHAT_PROVIDER=n8n` |

En los archivos de ejemplo la URL y la clave de Sim van vacías. La clave
**solo** va en tu `.env` o `.env.docker` locales, nunca en archivos versionados:
quien la tenga puede gastar la cuota del workflow. Si una clave queda expuesta,
se revoca en Sim y se crea otra. Si falta la URL o la clave del proveedor
elegido, la API arranca, registra una advertencia y `POST /chat` responde 503.

En redes que interceptan HTTPS, `SSL_CERT_FILE` indica el almacén de CA que usa
httpx. En Docker apunta por defecto a `/etc/ssl/certs/ca-certificates.crt`, que
incluye las CA de `docker/certs/`.

## Prueba manual con Docker Compose

Las pruebas automáticas usan un workflow falso y nunca llaman a Sim ni a n8n.
Para probar contra el workflow desplegado en Sim:

1. En `.env.docker`, define `CHAT_PROVIDER=sim`, `SIM_WORKFLOW_URL` con la URL
   de ejecución del workflow y `SIM_API_KEY` con tu clave de Sim.
2. Levanta el sistema (las migraciones se aplican al arrancar la API):
   `docker compose --env-file .env.docker up -d --build`.
3. Comprueba que no aparece la advertencia de configuración vacía:
   `docker compose --env-file .env.docker logs api | Select-String SIM_`.
4. Entra en http://localhost:8080 con una cuenta de prueba de usuario o
   docente, abre **Emi** y pregunta algo dentro de alcance («¿Qué es la
   regulación emocional?» o «¿Qué expresiones estima EMOtv?»). La respuesta
   puede tardar varios segundos.
5. Pregunta algo fuera de alcance («¿Quién ganó el último mundial?»): Emi debe
   negarse con su respuesta fija.
6. Revisa el log: `docker compose --env-file .env.docker logs api | Select-String "Emi request_id"`.
   Cada pregunta muestra su `request_id` y `gateway_status=200`; nunca la clave
   ni el texto.
7. Escribe una pregunta con un DNI inventado de 8 dígitos: Emi responde con el
   mensaje fijo y el log indica que se bloqueó sin llamar al workflow.
8. Pulsa **Nueva conversación**, recarga la página y vuelve a abrir Emi: se
   carga la conversación más reciente. Pulsa **Borrar conversación** y
   confirma: la conversación desaparece.
9. Opcional: cambia temporalmente la clave en `.env.docker`, recrea la API
   (`docker compose --env-file .env.docker up -d api`) y comprueba el mensaje
   de configuración (Sim responde 401). Restaura la clave al terminar.
