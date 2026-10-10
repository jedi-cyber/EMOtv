# Configuración del workflow EMI en n8n Cloud

El prompt de sistema de Emi y el clasificador de alcance viven en el workflow
**EMI** de n8n Cloud (versión publicada «Version 1.0 EMI»). El repositorio no lo
modifica: genera el conocimiento que viaja en el campo `knowledge`
(`src/emotv/application/emi_knowledge.py`) y documenta aquí la configuración.
Contrato del webhook y comportamiento de FastAPI: [../chatbot-emi.md](../chatbot-emi.md).

Las URL de esta guía se comprobaron el 2026-10-09 en la documentación oficial
de n8n y de Groq. Los nombres de menús pueden cambiar entre versiones de n8n;
si algo no coincide, la referencia es el enlace oficial indicado.

## 1. Credencial de Groq

1. Crea una cuenta en [Groq](https://groq.com/) si no la tienes.
2. Abre la página de claves de la consola: <https://console.groq.com/keys>.
   Pulsa **Create API Key**, ponle un nombre (por ejemplo `n8n EMOtv`),
   pulsa **Submit** y copia la clave. Groq asocia la clave a la organización,
   no a la persona.
3. En n8n, crea una credencial de tipo **Groq**. Solo pide el campo **API Key**:
   pega la clave.
4. Abre el workflow EMI y, en los dos nodos de modelo, **«Modelo de Emi
   (Groq)»** y **«Modelo clasificador (Groq)»**, elige esa credencial en el
   campo de credencial del nodo.

Referencias: [credencial de Groq en n8n](https://docs.n8n.io/integrations/builtin/credentials/groq/)
y [guía de inicio de Groq](https://console.groq.com/docs/quickstart).

La clave de Groq solo se guarda en n8n. EMOtv no la conoce ni la necesita.

## 2. Credencial Header Auth `X-EMOtv-Key`

FastAPI se identifica ante el webhook con la cabecera `X-EMOtv-Key`.

1. Genera un valor aleatorio largo, por ejemplo en PowerShell:
   `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
2. En n8n, crea una credencial **Header Auth** con:
   - **Name:** `X-EMOtv-Key`
   - **Value:** el valor generado.
3. En el nodo **Webhook** del workflow EMI, elige **Header Auth** como
   autenticación y selecciona esa credencial.
4. Escribe **el mismo valor** en tu `.env.docker` local (y en `.env` si
   ejecutas la API fuera de Docker):
   `N8N_WEBHOOK_KEY=<el valor>`. Nunca lo pongas en archivos versionados,
   commits ni capturas de pantalla: quien lo tenga puede gastar la cuota de Groq.
5. Si cambias el valor, cámbialo en los dos lugares y recrea la API:
   `docker compose --env-file .env.docker up -d api`. Mientras no coincidan,
   n8n responde 403 y Emi muestra un mensaje de configuración.

Referencias: [autenticación del nodo Webhook](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
y [credenciales del Webhook (Header Auth: Name y Value)](https://docs.n8n.io/integrations/builtin/credentials/webhook/).

## 3. Publicar el workflow

1. Abre el workflow y pulsa **Publish** en la cabecera del lienzo
   (atajo `Shift + P`). Puedes nombrar la versión, por ejemplo «Version 1.0 EMI»,
   y vuelves a pulsar **Publish**.
2. Las ejecuciones de producción usan siempre la versión publicada. Un cambio
   sin publicar no afecta a EMOtv.
3. Si el estado queda en «Published, partial», un disparador no se activó:
   publica de nuevo.
4. Para despublicar, usa la flecha junto a **Publish** (`Ctrl + U`). Con el
   workflow despublicado, la URL de producción responde 404 y Emi muestra que el
   asistente no está activo.

Referencia: [Save and publish workflows](https://docs.n8n.io/build/understand-workflows/save-and-publish-workflows).

## 4. URL de prueba y URL de producción

| | URL de prueba | URL de producción |
| --- | --- | --- |
| Ruta | `/webhook-test/...` | `/webhook/...` |
| Cuándo funciona | Mientras el editor escucha (**Listen for Test Event** o **Execute workflow**); la escucha dura 120 segundos | Desde que el workflow se publica y hasta que se despublica |
| Dónde se ven los datos | En el editor | En la pestaña **Executions** del workflow, si se guardan |

EMOtv usa **solo** la URL de producción:
`https://emotv.app.n8n.cloud/webhook/emi-chat`. La URL de prueba
(`https://emotv.app.n8n.cloud/webhook-test/emi-chat`) sirve para depurar desde
el editor; no la pongas en `N8N_WEBHOOK_URL`.

Las rutas `webhook` y `webhook-test` son los valores por defecto de n8n
(`N8N_ENDPOINT_WEBHOOK` y `N8N_ENDPOINT_WEBHOOK_TEST`).

Referencias: [nodo Webhook](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/),
[desarrollo de workflows con webhooks](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/workflow-development)
y [variables de endpoints](https://docs.n8n.io/hosting/configuration/environment-variables/endpoints/).

## 5. Ejecuciones guardadas y privacidad

n8n guarda por defecto las ejecuciones, con los datos de entrada. Configura el
workflow EMI así (menú de tres puntos → **Settings**):

| Ajuste | Valor | Motivo |
| --- | --- | --- |
| Save successful production executions | **Do not save** | Las ejecuciones exitosas de producción no se guardan: n8n no conserva esas conversaciones |
| Save failed production executions | **Save** | Permite diagnosticar fallos |
| Save manual executions | según necesidad, solo para pruebas propias | — |

Importante: **las ejecuciones fallidas sí se guardan e incluyen el texto de la
pregunta** y el historial enviado. Se conservan según el plan de n8n Cloud
(Start y Starter: 7 días y hasta 2 500 ejecuciones; Pro: 30 días y hasta
25 000). Revísalas solo para diagnosticar y bórralas cuando ya no sean
necesarias. Las preguntas que el filtro de riesgo de FastAPI bloquea nunca
llegan a n8n.

Referencias: [ajustes del workflow](https://docs.n8n.io/workflows/settings/) y
[gestión de datos en n8n Cloud](https://docs.n8n.io/manage-cloud/cloud-data-management/).

## 6. Copia del workflow en el repositorio

`docs/chatbot/emi-workflow.json` **todavía no existe**. No se inventa: debe
exportarse desde n8n.

1. Abre el workflow EMI, menú de tres puntos → **Download**. n8n descarga el
   workflow como JSON.
2. El JSON exportado no contiene los secretos de las credenciales, pero sí sus
   **nombres e identificadores**, y un nodo HTTP Request importado desde cURL
   podría contener cabeceras de autenticación. Antes de confirmarlo:
   - busca `X-EMOtv-Key`, `Authorization`, `Bearer`, `gsk_`, `apiKey`,
     `password`, `token` y el valor de `N8N_WEBHOOK_KEY`;
   - elimina cualquier valor secreto; deja solo referencias a credenciales;
   - ejecuta `python scripts/security/check_secrets.py --all` después de
     agregarlo al índice (`git add`).
3. Guárdalo como `docs/chatbot/emi-workflow.json` y confírmalo en un commit
   propio.

Referencia: [exportar e importar workflows](https://docs.n8n.io/workflows/export-import/).

## 7. Verificación

- Prueba manual del chat con Docker: [../chatbot-emi.md](../chatbot-emi.md#prueba-manual-con-docker-compose).
- Evaluación con 35 preguntas: [../../tests/chatbot/emi_eval.md](../../tests/chatbot/emi_eval.md)
  y `scripts/chatbot/run_eval.py`.
