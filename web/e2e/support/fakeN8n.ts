import { createServer, type IncomingMessage, type Server } from "node:http";

/** Cuerpo que EMOtv envía al workflow EMI (docs/chatbot-emi.md). */
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
 * Servidor falso con el contrato del webhook "Version 1.0 EMI":
 * POST + X-EMOtv-Key → 200 {answer, in_scope, category, request_id};
 * 502 {error: "llm_unavailable", answer, request_id}; 403 si la clave no coincide.
 */
export async function startFakeN8n(port: number, expectedKey = ""): Promise<FakeN8n> {
  const requests: FakeN8n["requests"] = [];
  const server: Server = createServer(async (request, response) => {
    const reply = (status: number, body: unknown) => {
      response.writeHead(status, { "Content-Type": "application/json" });
      response.end(JSON.stringify(body));
    };
    if (request.method !== "POST" || !request.url?.startsWith("/webhook/")) return reply(404, { message: "not found" });
    const key = request.headers["x-emotv-key"];
    const keyValue = Array.isArray(key) ? key[0] : key;
    if (!keyValue || (expectedKey && keyValue !== expectedKey)) return reply(403, { message: "forbidden" });
    let body: unknown;
    try { body = await readJson(request); } catch { return reply(400, { message: "invalid json" }); }
    if (!isEmiRequest(body)) return reply(400, { message: "invalid body" });
    requests.push({ key: keyValue, body });
    const question = body.question.toLowerCase();
    if (question.includes(triggers.llmDown)) return reply(502, { error: "llm_unavailable", answer: LLM_DOWN_ANSWER, request_id: body.request_id });
    if (question.includes(triggers.outOfScope)) return reply(200, { answer: OUT_OF_SCOPE_ANSWER, in_scope: false, category: "fuera_de_alcance", request_id: body.request_id });
    return reply(200, { answer: IN_SCOPE_ANSWER, in_scope: true, category: "plataforma", request_id: body.request_id });
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
