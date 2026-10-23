# Emi: chatbot educativo con n8n

Emi responde a **usuarios y docentes** preguntas de Psicología en general (incluida
la evaluación infantil) y sobre el uso de EMOtv. No diagnostica ni etiqueta a
ninguna persona concreta, no determina el estado psicológico de nadie, no
reemplaza al docente y no sustituye la atención psicológica ni los servicios de
emergencia.

Los participantes no tienen cuenta, así que nunca acceden a Emi. FastAPI
rechaza con 403 a las cuentas de administración y la interfaz no muestra a Emi
ni en la vista del participante ni en la sesión guiada, donde hay un
participante delante.

## Arquitectura

```text
React (AssistantWidget) → FastAPI (/chat) → webhook de n8n Cloud (workflow EMI) → Groq
```

| Parte | Responsabilidad |
| --- | --- |
| FastAPI | Autenticación y papel (usuario o docente), límites de uso, filtros de riesgo e identificadores, historial, borrado, retención y contador de rechazos |
| n8n (workflow «Version 1.0 EMI») | Bloquear intentos de cambiar las reglas, clasificar el alcance con un modelo pequeño de Groq (si la clasificación falla, la pregunta se trata como fuera de alcance) y responder como Emi con un modelo mayor de Groq. No guarda conversaciones |

El workflow se administra en n8n Cloud y **no se modifica desde este
repositorio**. URL de producción: `https://emotv.app.n8n.cloud/webhook/emi-chat`.

## Contrato del webhook

Petición: `POST N8N_WEBHOOK_URL` con la cabecera `X-EMOtv-Key: N8N_WEBHOOK_KEY`.

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
| 502 | `{"error": "llm_unavailable", "answer", "request_id"}` | 502: el servicio de IA no está disponible |
| 401/403 | La clave no coincide | 502: problema de configuración del servidor |
| 404 | El workflow no está publicado | 502: el asistente no está activo |
| Timeout (`N8N_TIMEOUT_SECONDS`, 30 s) | — | 504 |
| Cualquier otro fallo | — | 502 |

`knowledge` lleva el conocimiento verificado de EMOtv que genera
`emotv.application.emi_knowledge`: textos fijos (flujo de uso, participantes y
autorizaciones, protocolos y sesión guiada, línea de tiempo y métricas, estados
del reporte, limitaciones del reconocimiento facial, qué se guarda y roles) y,
desde la base de datos, las cinco posturas, las actividades y sus pasos y los
textos del catálogo de expresiones. Los textos fijos van primero: si hay que
recortar, solo se acorta el contenido editable. Se guarda en caché en memoria, se regenera cuando administración
edita actividades o el catálogo (y, como respaldo, cada 10 minutos) y su tamaño
se registra en el log. Debe quedar por debajo de 12 000 caracteres, porque el
workflow corta lo que exceda; si el contenido crece, los textos se acortan y
una prueba falla si se supera el límite. No incluye datos de ningún usuario
ni participante: ni sesiones, ni reportes, ni resultados.

Al webhook **nunca** se envían datos de participantes, resultados
emocionales, sesiones, reportes, nombres, correos ni el id del usuario. El
contrato no cambia: el workflow EMI se modifica en n8n, aparte de este
repositorio. La configuración de n8n está en
[chatbot/n8n-setup.md](chatbot/n8n-setup.md).

## Qué hace FastAPI antes de llamar a n8n

1. Rechaza preguntas vacías o de más de `CHAT_MAX_QUESTION_CHARS` caracteres (1000).
2. Aplica los límites por usuario: `CHAT_LIMIT_WINDOW_MESSAGES` mensajes (20)
   cada `CHAT_LIMIT_WINDOW_MINUTES` minutos (10) y `CHAT_LIMIT_DAILY_MESSAGES`
   (200) en 24 horas. Se cuentan las preguntas guardadas; al superarlos responde
   429 con un mensaje en español.
3. Filtro de riesgo (`emotv.application.chat_safety`): una lista corta de
   patrones, como ideación de autolesión. Si coincide, **no se llama al webhook
   ni se guarda el texto**: se responde con `CHAT_RISK_MESSAGE`, que deriva a
   una persona de confianza, a un profesional o a los servicios de emergencia
   de la localidad. No incluye números de teléfono.
4. Filtro de identificadores (`emotv.application.chat_safety`): si la pregunta
   contiene un DNI (8 dígitos, también con puntos), un correo electrónico o un
   teléfono (7 o de 9 a 15 dígitos, con o sin espacios, guiones o paréntesis),
   **no se llama al webhook ni se guarda el texto**. Se responde con un mensaje
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
código de respuesta de n8n. El log nunca incluye la clave ni el texto de los
mensajes.

## Datos que guarda EMOtv

- `chat_conversations` y `chat_messages`: preguntas y respuestas por usuario,
  con `in_scope` y `category`. Cada usuario solo accede a sus conversaciones.
  Una pregunta queda con `in_scope` nulo si n8n no respondió: cuenta para los
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
añade `filtro_riesgo` y `filtro_identificadores` (esas preguntas nunca llegan a
n8n). Las etiquetas del clasificador anterior se traducen (`plataforma` y
`privacidad` → `uso_emotv`; `expresiones` y `otra_psicologia` →
`psicologia_general`) y cualquier etiqueta desconocida se cuenta como `otro`.

## Configuración

`N8N_WEBHOOK_URL` (la URL de producción viene en los archivos de ejemplo) y
`N8N_WEBHOOK_KEY`, la clave de la credencial Header Auth del webhook. La clave
**solo** va en tu `.env` o `.env.docker` locales, nunca en archivos versionados:
quien la tenga puede gastar la cuota de Groq. Si está vacía, la API arranca,
registra una advertencia y `POST /chat` responde 503.

En redes que interceptan HTTPS, `SSL_CERT_FILE` indica el almacén de CA que usa
httpx. En Docker apunta por defecto a `/etc/ssl/certs/ca-certificates.crt`, que
incluye las CA de `docker/certs/`.

## Prueba manual con Docker Compose

Las pruebas automáticas usan un webhook falso y nunca llaman a n8n. Para probar
contra el workflow publicado:

1. En `.env.docker`, define `N8N_WEBHOOK_URL=https://emotv.app.n8n.cloud/webhook/emi-chat`
   y `N8N_WEBHOOK_KEY` con la clave real de la credencial Header Auth.
2. Levanta el sistema (las migraciones se aplican al arrancar la API):
   `docker compose --env-file .env.docker up -d --build`.
3. Comprueba que no aparece la advertencia de clave vacía:
   `docker compose --env-file .env.docker logs api | Select-String N8N_WEBHOOK_KEY`.
4. Entra en http://localhost:8080 con una cuenta de prueba de usuario o
   docente, abre **Emi** y pregunta algo dentro de alcance («¿Qué es la
   regulación emocional?»). La
   respuesta puede tardar varios segundos.
5. Pregunta algo fuera de alcance («¿Quién ganó el último mundial?»): Emi debe
   negarse con su respuesta fija.
6. Revisa el log: `docker compose --env-file .env.docker logs api | Select-String "Emi request_id"`.
   Cada pregunta muestra su `request_id` y `n8n_status=200`; nunca la clave ni
   el texto.
7. Escribe una pregunta con un DNI inventado de 8 dígitos: Emi responde con el
   mensaje fijo y el log indica que se bloqueó sin llamar a n8n.
8. Pulsa **Nueva conversación**, recarga la página y vuelve a abrir Emi: se
   carga la conversación más reciente. Pulsa **Borrar conversación** y
   confirma: la conversación desaparece.
9. Opcional: cambia temporalmente la clave en `.env.docker`, recrea la API
   (`docker compose --env-file .env.docker up -d api`) y comprueba el mensaje
   de configuración (n8n responde 403). Restaura la clave al terminar.
