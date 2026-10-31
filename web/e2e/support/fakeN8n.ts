import { createServer, type IncomingMessage, type Server } from "node:http";

/** Cuerpo que EMOtv envía al workflow de Emi (en Sim, dentro de `input`; docs/chatbot-emi.md). */
export interface EmiRequest {
  request_id: string;
  question: string;
  history: { role: "user" | "assistant"; content: string }[];
  knowledge: string;
}

export interface FakeN8n {
  requests: { key: string | undefined; body: EmiRequest }[];
  close(): Promise<void>;
}

export const OUT_OF_SCOPE_ANSWER = "Solo puedo orientarte sobre EMOtv, sus actividades y las expresiones faciales. Para otros temas, consulta otra fuente.";
export const IN_SCOPE_ANSWER = "En EMOtv, una actividad es una secuencia de posturas guiadas que la cámara verifica paso a paso.";
export const LLM_DOWN_ANSWER = "El modelo de lenguaje no está disponible.";

/** Palabras clave en la pregunta que eligen la respuesta del n8n falso. */
export const triggers = { outOfScope: "receta", llmDown: "falla-llm" };

function readJson(request: IncomingMessage): Promise<unknown> {
  return new Promise((resolve, reject) => {
    let raw = "";
    request.setEncoding("utf-8");
    request.on("data", (chunk) => { raw += chunk; });
    request.on("end", () => { try { resolve(JSON.parse(raw)); } catch (error) { reject(error); } });
    request.on("error", reject);
  });
}

function isEmiRequest(value: unknown): value is EmiRequest {
  const body = value as EmiRequest;
  return typeof body?.request_id === "string" && typeof body.question === "string"
    && Array.isArray(body.history) && typeof body.knowledge === "string";
}

/**
 * Servidor falso con el contrato de Emi en sus dos proveedores (docs/chatbot-emi.md):
 * - n8n, `POST /webhook/...` + X-EMOtv-Key → 200 {answer, in_scope, category, request_id};
 *   502 {error: "llm_unavailable", answer, request_id}; 403 si la clave no coincide.
 * - Sim, `POST /api/v2/workflows/{id}/execute` + X-API-Key con {input: ...} →
 *   200 {data: {status, output}}; la caída del LLM llega como status "failed"; 401 si la clave no coincide.
 */
export async function startFakeN8n(port: number, expectedKey = ""): Promise<FakeN8n> {
  const requests: FakeN8n["requests"] = [];
  const server: Server = createServer(async (request, response) => {
    const reply = (status: number, body: unknown) => {
      response.writeHead(status, { "Content-Type": "application/json" });
      response.end(JSON.stringify(body));
    };
    const sim = request.url?.startsWith("/api/v2/workflows/") ?? false;
    if (request.method !== "POST" || !(sim || request.url?.startsWith("/webhook/"))) return reply(404, { message: "not found" });
    const key = request.headers[sim ? "x-api-key" : "x-emotv-key"];
    const keyValue = Array.isArray(key) ? key[0] : key;
    if (!keyValue || (expectedKey && keyValue !== expectedKey)) return reply(sim ? 401 : 403, { message: "forbidden" });
    let raw: unknown;
    try { raw = await readJson(request); } catch { return reply(400, { message: "invalid json" }); }
    const body = sim ? (raw as { input?: unknown })?.input : raw;
    if (!isEmiRequest(body)) return reply(400, { message: "invalid body" });
    requests.push({ key: keyValue, body });
    const answer = (status: number, output: Record<string, unknown>) => sim
      ? reply(200, { data: { runId: "run-e2e", status: status === 200 ? "completed" : "failed", output, error: status === 200 ? null : "llm_unavailable" } })
      : reply(status, output);
    const question = body.question.toLowerCase();
    if (question.includes(triggers.llmDown)) return answer(502, { error: "llm_unavailable", answer: LLM_DOWN_ANSWER, request_id: body.request_id });
    if (question.includes(triggers.outOfScope)) return answer(200, { answer: OUT_OF_SCOPE_ANSWER, in_scope: false, category: "otro", request_id: body.request_id });
    return answer(200, { answer: IN_SCOPE_ANSWER, in_scope: true, category: "uso_emotv", request_id: body.request_id });
  });
  // 0.0.0.0: el contenedor de la API llega por host.docker.internal.
  await new Promise<void>((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, "0.0.0.0", () => resolve());
  });
  return {
    requests,
    close: () => new Promise((resolve) => server.close(() => resolve())),
  };
}
