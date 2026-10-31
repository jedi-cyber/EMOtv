# Workflow de Emi en Sim

Emi usa un workflow de [Sim](https://www.sim.ai) desplegado como API. Reemplaza
al workflow de n8n Cloud, cuyo periodo de prueba terminó. El workflow se
administra en Sim y **no se modifica desde este repositorio**; aquí solo se
define el contrato que EMOtv espera.

## Llamada que hace EMOtv

```http
POST https://www.sim.ai/api/v2/workflows/<id-del-workflow>/execute
X-API-Key: <SIM_API_KEY>
Content-Type: application/json

{
  "input": {
    "request_id": "uuid generado por FastAPI",
    "question": "texto de la pregunta",
    "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
    "knowledge": "# Conocimiento de EMOtv ..."
  }
}
```

- `SIM_WORKFLOW_URL` es la URL completa de arriba (el id está en la URL del
  editor de Sim).
- `SIM_API_KEY` es una clave de API de Sim con acceso a ese workflow. Solo va en
  `.env` o `.env.docker`; nunca en archivos versionados, pruebas ni commits. Si
  una clave queda expuesta (por ejemplo, pegada en un chat), se revoca en Sim y
  se crea otra.

## Qué debe tener el workflow

1. **Bloque de inicio (API)** con cuatro entradas: `request_id` (texto),
   `question` (texto), `history` (arreglo de `{role, content}`) y `knowledge`
   (texto).
2. **Conocimiento fijo**: el texto de
   [emotv-descripcion-sim.md](emotv-descripcion-sim.md), combinado con
   `knowledge`. Si se contradicen, vale `knowledge`, que se genera desde la
   base de datos de EMOtv.
3. **Bloqueo de cambios de reglas, clasificación del alcance y respuesta**, como
   en el workflow anterior: categorías de
   [chatbot-emi.md](../chatbot-emi.md#categorías). Si la clasificación falla,
   la pregunta se trata como fuera de alcance.
4. **Bloque Response** con el contrato de Emi:

   ```json
   {"answer": "texto", "in_scope": true, "category": "uso_emotv", "request_id": "<input.request_id>"}
   ```

   `in_scope` debe ser booleano. Si el modelo de lenguaje no responde, el
   bloque devuelve `{"error": "llm_unavailable", "answer": "...", "request_id": "..."}`.
5. **Desplegar** el workflow. Sin desplegar, Sim responde 404.

El workflow no guarda conversaciones: el historial lo manda EMOtv.

## Cómo interpreta EMOtv la respuesta

La API v2 de Sim envuelve el resultado: `{"data": {"status", "output", "error", ...}}`.
EMOtv toma `data.output` (también acepta la salida anidada en `data.output.data`
o, si el bloque final es un agente con salida estructurada, el JSON de
`data.output.content`).

| Respuesta de Sim | Para EMOtv |
| --- | --- |
| 200, `status: completed` y `output` con `answer` e `in_scope` booleano | Respuesta normal |
| 200 con `status: failed`, o `output.error = "llm_unavailable"` | `llm_unavailable` → 502 |
| 402 o 429 (límite de uso de Sim) | `llm_unavailable` → 502 |
| 401 o 403 (clave inválida o sin acceso) | Problema de configuración → 502 |
| 404 (workflow inexistente o sin desplegar) | El asistente no está activo → 502 |
| Sin `answer` o sin `in_scope` booleano | Respuesta ilegible → 502 |
| Más de `CHAT_TIMEOUT_SECONDS` (30 s) | 504 |

## Privacidad

A Sim solo llegan la pregunta (sin DNI, correos ni teléfonos: FastAPI la
bloquea antes), el historial de esa conversación dentro de alcance y el
conocimiento general de EMOtv. Nunca datos de sesiones, reportes, resultados,
nombres, correos ni el id del usuario, y nunca imágenes.
