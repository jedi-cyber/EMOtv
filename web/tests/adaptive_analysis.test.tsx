import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdaptiveAnalysisPage } from "../src/pages/AdaptiveAnalysisPage";
import { AuthContext } from "../src/auth/AuthContext";
import { apiRequest } from "../src/api/http";
import { AssistantProvider } from "../src/components/AssistantContext";
import { AssistantWidget } from "../src/components/AssistantWidget";

const { admissions } = vi.hoisted(() => ({ admissions: { value: [{ model_id: "ferplus_onnx", state: "SUPPORTED", reasons: [] as string[] }] } }));
vi.mock("../src/api/useApiQuery", () => ({ useApiQuery: (path: string | null) => ({ data: path === null ? null : admissions.value, loading: false, error: "", reload: vi.fn() }) }));
vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn() }));

class Socket {
  static OPEN = 1;
  static instances: Socket[] = [];
  readyState = 1;
  binaryType = "";
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn();
  constructor() { Socket.instances.push(this); }
}

function page(role: "student" | "admin" = "student", withAssistant = false) {
  const element = withAssistant
    ? <AssistantProvider><AdaptiveAnalysisPage /><AssistantWidget /></AssistantProvider>
    : <AdaptiveAnalysisPage />;
  const router = createMemoryRouter([{ path: "/analysis", element }], { initialEntries: ["/analysis"] });
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "student@example.com", role, is_active: true }, token: "test", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}><RouterProvider router={router} /></AuthContext.Provider>);
}

const sadnessInfo = {
  expression_key: "sadness", label_es: "Tristeza",
  what_it_is: "La tristeza es una emoción relacionada con la pérdida. Se muestra con un gesto de decaimiento.",
  why_it_occurs: "En general aparece ante pérdidas o despedidas. Favorece la reflexión.",
  facial_cues: "Las cejas internas se elevan. Las comisuras descienden.",
  practice_tip: "Eleva la parte interna de las cejas. Observa la lectura en vivo.",
  limitation_note: "La cultura, el contexto, la iluminación y el ángulo influyen. Solo indica una expresión compatible con tristeza.",
  common_limitation: "El reconocimiento facial estima una expresión a partir de la imagen y no determina por sí mismo el estado emocional ni psicológico de la persona.",
  review_status: "draft", reviewed_by_user_id: null, reviewed_at: null, updated_at: "2026-10-08T09:00:00Z",
};

function recognize(socket: Socket, expression: Record<string, unknown> | null) {
  const activity = { id: "morning_mobility", name: "Movilidad suave", description: "Realiza tres posturas", required_posture: "arms_open", duration_seconds: 4, repetitions: 1, steps: [{ posture: "arms_open", instruction: "Abre los brazos", duration_seconds: 4 }, { posture: "arms_up", instruction: "Eleva los brazos", duration_seconds: 4 }] };
  act(() => socket.onmessage?.({ data: JSON.stringify({ type: "recognized", message: "Expresión registrada", emotion: "sadness", emotion_confidence: .9 }) }));
  act(() => socket.onmessage?.({ data: JSON.stringify({ type: "recommendation", message: "Actividad sugerida", emotion: "sadness", emotion_confidence: .9, activity, activities: [activity, { ...activity, id: "open_and_reach", name: "Abrir y alcanzar" }], expression }) }));
}

function camera(getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] })) {
  vi.stubGlobal("navigator", Object.create(navigator, { mediaDevices: { value: { getUserMedia }, configurable: true } }));
  return getUserMedia;
}

function liveReading(overrides: Record<string, unknown> = {}) {
  return {
    type: "live", state: "live", face_detected: true, emotion: "happiness", emotion_confidence: .8,
    top: [{ emotion: "happiness", probability: .8 }, { emotion: "sadness", probability: .15 }, { emotion: "neutral", probability: .05 }],
    stable_seconds: .4, required_stable_seconds: 1, can_confirm: false,
    blocked_reason: "Mantén la expresión un momento más.", ...overrides,
  };
}

/** La cámara es un requisito: se prueba primero y el botón se habilita cuando se cumplen los tres. */
async function startAnalysis() {
  await userEvent.click(screen.getAllByRole("button", { name: "Probar cámara" })[0]);
  await waitFor(() => expect(screen.getByRole("button", { name: "Reconocer mi expresión" })).toBeEnabled());
  await userEvent.click(screen.getByRole("button", { name: "Reconocer mi expresión" }));
}

async function openLive(withAssistant = false) {
  camera();
  page("student", withAssistant);
  await startAnalysis();
  await waitFor(() => expect(Socket.instances).toHaveLength(1));
  const socket = Socket.instances[0];
  act(() => socket.onopen?.());
  act(() => socket.onmessage?.({ data: JSON.stringify({ type: "ready", state: "live", message: "Cámara conectada" }) }));
  return socket;
}

beforeEach(() => {
  admissions.value = [{ model_id: "ferplus_onnx", state: "SUPPORTED", reasons: [] }];
  Socket.instances = [];
  vi.stubGlobal("WebSocket", Socket);
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  vi.mocked(apiRequest).mockReset().mockImplementation(async (path) => {
    if (path === "/consent-policy") return { id: "EMOTV-CONSENT-DEMO-001:v0.1", version: "v0.1", mode: "demo", available: true } as never;
    if (path === "/students") return [{ id: "student-1" }] as never;
    if (path.endsWith("/consents/active")) return { id: "consent-1", policy_version: "EMOTV-CONSENT-DEMO-001:v0.1" } as never;
    if (path === "/sessions") return { id: "session-1", state: "in_progress" } as never;
    return {} as never;
  });
});

describe("analizador emoción → recomendación → postura", () => {
  it("prueba la cámara local sin iniciar sesión ni enviar frames", async () => {
    const stop = vi.fn(); const getUserMedia = camera(vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] }));
    page();
    await userEvent.click(screen.getAllByRole("button", { name: "Probar cámara" })[0]);
    expect(getUserMedia).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Apagar cámara" })).toBeInTheDocument();
    // Solo se consultan los requisitos; probar la cámara no crea sesión ni abre el WebSocket.
    expect(apiRequest).not.toHaveBeenCalledWith("/sessions", expect.anything());
    expect(Socket.instances).toHaveLength(0);
    await userEvent.click(screen.getByRole("button", { name: "Apagar cámara" }));
    expect(stop).toHaveBeenCalledOnce();
  });

  it("muestra la guía previa: luz de frente, rostro centrado y distancia para la actividad", () => {
    camera();
    page();
    const guide = screen.getByRole("region", { name: "Antes de empezar" });
    expect(guide).toHaveTextContent("Luz de frente");
    expect(guide).toHaveTextContent("Rostro centrado");
    expect(guide).toHaveTextContent("cuerpo completo");
  });

  it.each([
    ["NotReadableError", "Otra aplicación está usando la cámara", "Otra aplicación la está usando."],
    ["NotFoundError", "No encontramos ninguna cámara", "No se encontró ninguna cámara."],
    ["SecurityError", "conexión segura", "Requiere una conexión segura (https)."],
  ])("explica el error %s de getUserMedia", async (name, message, detail) => {
    camera(vi.fn().mockRejectedValue(new DOMException("x", name)));
    page();
    await userEvent.click(screen.getAllByRole("button", { name: "Probar cámara" })[0]);
    expect(await screen.findByRole("alert")).toHaveTextContent(message);
    expect(within(screen.getByRole("list", { name: "Requisitos para empezar" })).getByText(detail)).toBeInTheDocument();
  });

  it("avisa del contexto no seguro sin pedir la cámara", async () => {
    const getUserMedia = camera();
    vi.stubGlobal("isSecureContext", false);
    page();
    await userEvent.click(screen.getAllByRole("button", { name: "Probar cámara" })[0]);
    expect(await screen.findByRole("alert")).toHaveTextContent("https://");
    expect(getUserMedia).not.toHaveBeenCalled();
    vi.stubGlobal("isSecureContext", true);
  });

  it("apaga todas las pistas al salir de la página y al cerrar la pestaña", async () => {
    const stopVideo = vi.fn(); const stopOther = vi.fn();
    camera(vi.fn().mockResolvedValue({ getTracks: () => [{ stop: stopVideo }, { stop: stopOther }] }));
    const view = page();
    await userEvent.click(screen.getAllByRole("button", { name: "Probar cámara" })[0]);
    await screen.findByRole("button", { name: "Apagar cámara" });
    act(() => { window.dispatchEvent(new Event("pagehide")); });
    expect(stopVideo).toHaveBeenCalledOnce(); expect(stopOther).toHaveBeenCalledOnce();
    await userEvent.click(screen.getAllByRole("button", { name: "Probar cámara" })[0]);
    view.unmount();
    expect(stopVideo).toHaveBeenCalledTimes(2); expect(stopOther).toHaveBeenCalledTimes(2);
  });

  it("apaga la cámara al cancelar el análisis", async () => {
    const stop = vi.fn();
    camera(vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] }));
    page();
    await startAnalysis();
    await waitFor(() => expect(Socket.instances).toHaveLength(1));
    act(() => Socket.instances[0].onopen?.());
    act(() => Socket.instances[0].onmessage?.({ data: JSON.stringify({ type: "ready", state: "live", message: "Cámara conectada" }) }));
    await userEvent.click(screen.getByRole("button", { name: "Cancelar análisis" }));
    await userEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Cancelar sesión" }));
    await waitFor(() => expect(stop).toHaveBeenCalledOnce());
    expect(apiRequest).toHaveBeenCalledWith("/sessions/session-1/cancel", expect.objectContaining({ method: "POST" }));
    expect(screen.getAllByRole("button", { name: "Probar cámara" }).length).toBeGreaterThan(0);
  });

  it("explica la falta de consentimiento antes de abrir la cámara", async () => {
    const getUserMedia = camera();
    vi.mocked(apiRequest).mockImplementation(async (path) => path === "/consent-policy" ? { id: "EMOTV-CONSENT-DEMO-001:v0.1", mode: "demo", available: true } as never : path === "/students" ? [{ id: "student-1" }] as never : null as never);
    page();
    const requirements = await screen.findByRole("list", { name: "Requisitos para empezar" });
    expect(await within(requirements).findByRole("link", { name: "Revisar consentimiento" })).toHaveAttribute("href", "/consent");
    expect(within(requirements).getAllByText("Pendiente").length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Reconocer mi expresión" })).toBeDisabled();
    expect(screen.getByText(/Para empezar falta: .*consentimiento vigente/)).toBeInTheDocument();
    expect(getUserMedia).not.toHaveBeenCalled();
    expect(Socket.instances).toHaveLength(0);
  });

  it("explica el permiso de cámara denegado sin crear sesión", async () => {
    camera(vi.fn().mockRejectedValue(new DOMException("denied", "NotAllowedError")));
    page();
    await userEvent.click(screen.getAllByRole("button", { name: "Probar cámara" })[0]);
    expect(await screen.findByRole("alert")).toHaveTextContent("El navegador bloqueó la cámara");
    const requirements = screen.getByRole("list", { name: "Requisitos para empezar" });
    expect(within(requirements).getByText("Bloqueado")).toBeInTheDocument();
    expect(within(requirements).getByText("El navegador bloqueó el permiso.")).toBeInTheDocument();
    expect(apiRequest).not.toHaveBeenCalledWith("/sessions", expect.anything());
  });

  it("impide a administración iniciar con un modelo bloqueado e indica el motivo", async () => {
    admissions.value = [{ model_id: "ferplus_onnx", state: "BLOCKED", reasons: ["Benchmark vencido"] }];
    page("admin");
    expect(screen.getByRole("button", { name: "Reconocer mi expresión" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Modelo no disponible: Benchmark vencido");
  });

  it("el estudiante no ve el selector de modelo y recibe el motivo del bloqueo desde el servidor", async () => {
    camera();
    page();
    expect(screen.queryByLabelText("Modelo facial")).not.toBeInTheDocument();
    await startAnalysis();
    await waitFor(() => expect(Socket.instances).toHaveLength(1));
    act(() => Socket.instances[0].onopen?.());
    expect(JSON.parse(Socket.instances[0].send.mock.calls[0][0])).toEqual(expect.objectContaining({ emotion_model_id: "ferplus_onnx" }));
    act(() => Socket.instances[0].onmessage?.({ data: JSON.stringify({ type: "error", message: "Modelo bloqueado: Benchmark vencido" }) }));
    expect(await screen.findByText(/Modelo bloqueado: Benchmark vencido/)).toBeInTheDocument();
  });

  it("reconoce primero, muestra sugerencia y solo entonces asigna la actividad", async () => {
    const stop = vi.fn(); const getUserMedia = camera(vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] }));
    page();
    await startAnalysis();
    await waitFor(() => expect(Socket.instances).toHaveLength(1));
    const socket = Socket.instances[0];
    act(() => socket.onopen?.());
    expect(JSON.parse(socket.send.mock.calls[0][0])).toEqual(expect.objectContaining({ session_id: "session-1", emotion_model_id: "ferplus_onnx" }));
    expect(JSON.parse(socket.send.mock.calls[0][0])).not.toHaveProperty("activity_id");
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "ready", state: "live", message: "Cámara conectada" }) }));
    act(() => socket.onmessage?.({ data: JSON.stringify(liveReading({ can_confirm: true, blocked_reason: null, stable_seconds: 1.2 })) }));
    await userEvent.click(screen.getByRole("button", { name: "Registrar esta expresión" }));
    expect(JSON.parse(socket.send.mock.calls.at(-1)![0])).toEqual({ type: "confirm_expression" });
    const activity = { id: "morning_mobility", name: "Movilidad suave", description: "Realiza tres posturas", required_posture: "arms_open", duration_seconds: 4, repetitions: 1, steps: [{ posture: "arms_open", instruction: "Abre los brazos", duration_seconds: 4 }, { posture: "arms_up", instruction: "Eleva los brazos", duration_seconds: 4 }] };
    const alternative = { ...activity, id: "open_and_reach", name: "Abrir y alcanzar" };
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "recognized", state: "recognized", message: "Expresión registrada", emotion: "sadness", emotion_confidence: .9 }) }));
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "recommendation", state: "choosing_activity", message: "Actividad sugerida", emotion: "sadness", emotion_confidence: .9, activity, activities: [activity, alternative], expression: sadnessInfo }) }));
    expect(screen.getByRole("heading", { name: "Tristeza" })).toBeInTheDocument();
    expect(screen.getByText(/Confianza del modelo/)).toHaveTextContent("90 %");
    expect(screen.getByRole("heading", { name: "Movilidad suave" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Finalizar sin actividad" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Analizar otra expresión" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pasos de la actividad" })).toBeInTheDocument();
    expect(screen.getByText("Abre los brazos")).toBeInTheDocument();
    expect(screen.getByText("Eleva los brazos")).toBeInTheDocument();
    expect(screen.queryByLabelText("Actividad que deseas realizar")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ver otras actividades" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ver otras actividades" }));
    expect(screen.getByLabelText("Actividad que deseas realizar")).toHaveValue("open_and_reach");
    expect(screen.getByRole("option", { name: "Abrir y alcanzar" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Realizar actividad" }));
    expect(JSON.parse(socket.send.mock.calls.at(-1)![0])).toEqual({ type: "select_activity", activity_id: "morning_mobility" });
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "activity_started", activity, message: "Adopta la postura" }) }));
    expect(screen.getByRole("heading", { name: "Movilidad suave" })).toBeInTheDocument();
    expect(screen.getByText(/Paso 1 de 2:/)).toBeInTheDocument();
    expect(screen.getByText("Abre los brazos")).toBeInTheDocument();
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "status", state: "performing_exercise", message: "Siguiente postura", progress: .5, step: activity.steps[1], step_index: 1, step_count: 2 }) }));
    expect(screen.getByText(/Paso 2 de 2:/)).toBeInTheDocument();
    expect(screen.getByText("Eleva los brazos")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Progreso de la actividad" })).toHaveAttribute("aria-valuenow", "50");
    expect(screen.getByText(/cancelar solo detiene la actividad/)).toBeInTheDocument();
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "completed", activity, message: "Completada", progress: 1, exercise_result: "completed" }) }));
    expect(screen.getByRole("link", { name: "Ver resultado" })).toHaveAttribute("href", "/sessions/session-1");
    expect(stop).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole("button", { name: "Analizar otra expresión" }));
    await waitFor(() => expect(Socket.instances).toHaveLength(2));
    expect(getUserMedia).toHaveBeenCalledTimes(2);
    expect(vi.mocked(apiRequest).mock.calls.filter(([path]) => path === "/sessions")).toHaveLength(2);
    expect(screen.queryByText(/Expresión registrada:/)).not.toBeInTheDocument();
  });

  it("muestra la lectura en vivo en español y explica por qué no se puede registrar", async () => {
    const setItem = vi.spyOn(Storage.prototype, "setItem");
    const socket = await openLive();
    expect(screen.getByRole("button", { name: "Registrar esta expresión" })).toBeDisabled();
    expect(screen.getByText("Esperando la primera lectura del modelo.")).toBeInTheDocument();

    act(() => socket.onmessage?.({ data: JSON.stringify(liveReading({ face_detected: false, emotion: null, emotion_confidence: null, top: [], blocked_reason: "No se detecta un rostro. Ubica tu cara en el centro de la cámara." })) }));
    expect(screen.getByText(/Ubica tu rostro en el centro de la cámara/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Registrar esta expresión" })).toBeDisabled();

    act(() => socket.onmessage?.({ data: JSON.stringify(liveReading()) }));
    expect(screen.getByText("Felicidad", { selector: ".live-expression-name" })).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Confianza de la expresión estimada" })).toHaveAttribute("aria-valuenow", "80");
    expect(screen.getByRole("list", { name: "Expresiones más probables" }).children).toHaveLength(3);
    expect(screen.getByText(/Tristeza · 15 %/)).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "Estabilidad de la expresión" })).toHaveAttribute("aria-valuenow", "40");
    expect(screen.getByText("Estimación del modelo sobre la expresión visible; no indica lo que sientes.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Registrar esta expresión" })).toBeDisabled();
    expect(screen.getByText("Mantén la expresión un momento más.")).toBeInTheDocument();

    act(() => socket.onmessage?.({ data: JSON.stringify(liveReading({ stable_seconds: 1.1, can_confirm: true, blocked_reason: null })) }));
    expect(screen.getByRole("button", { name: "Registrar esta expresión" })).toBeEnabled();
    expect(screen.getByRole("progressbar", { name: "Estabilidad de la expresión" })).toHaveAttribute("aria-valuenow", "100");
    // La lectura en vivo no se guarda en el navegador.
    expect(setItem).not.toHaveBeenCalled();
    setItem.mockRestore();
  });

  it("muestra el motivo si el servidor rechaza el registro", async () => {
    const socket = await openLive();
    act(() => socket.onmessage?.({ data: JSON.stringify(liveReading({ stable_seconds: 1.1, can_confirm: true, blocked_reason: null })) }));
    await userEvent.click(screen.getByRole("button", { name: "Registrar esta expresión" }));
    expect(screen.getByRole("button", { name: "Registrando…" })).toBeDisabled();
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "confirm_rejected", message: "Mantén la expresión un momento más." }) }));
    expect(screen.getByText("Mantén la expresión un momento más.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Registrar esta expresión" })).toBeEnabled();
  });

  it("permite finalizar sin actividad conservando la expresión", async () => {
    const socket = await openLive();
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "recognized", message: "Expresión registrada", emotion: "neutral", emotion_confidence: .7 }) }));
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "recommendation", message: "Actividad sugerida", emotion: "neutral", emotion_confidence: .7, activity: null, activities: [] }) }));
    await userEvent.click(screen.getByRole("button", { name: "Finalizar sin actividad" }));
    expect(JSON.parse(socket.send.mock.calls.at(-1)![0])).toEqual({ type: "finish_without_activity" });
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "completed", message: "Sesión finalizada", emotion: "neutral", emotion_confidence: .7, exercise_result: "skipped" }) }));
    expect(screen.getByText("Sesión finalizada sin actividad. Tu expresión quedó registrada.")).toBeInTheDocument();
    expect(screen.getByText(/Expresión registrada:/)).toHaveTextContent("Neutral (70 %)");
    expect(screen.getByRole("button", { name: "Analizar otra expresión" })).toBeInTheDocument();
  });

  it("muestra el resultado educativo en el orden indicado, con la limitación y la nota de borrador", async () => {
    const socket = await openLive();
    recognize(socket, sadnessInfo);
    const article = screen.getByRole("article");
    const headings = within(article).getAllByRole("heading").map((heading) => heading.textContent);
    expect(headings).toEqual(["Tristeza", "¿Qué es?", "¿Por qué suele presentarse?", "¿Cómo se reconoce en el rostro?", "Para practicar"]);
    expect(within(article).getByText(/Confianza del modelo/)).toHaveTextContent("90 %");
    expect(within(article).getByText(sadnessInfo.why_it_occurs)).toBeInTheDocument();
    const limitation = within(article).getByRole("note");
    expect(limitation).toHaveTextContent("no determina por sí mismo el estado emocional ni psicológico");
    const draftNote = within(article).getByText("Contenido pendiente de revisión por profesionales de Psicología.");
    expect(limitation.compareDocumentPosition(draftNote) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    // La actividad recomendada y sus botones van debajo del resultado.
    const activityHeading = screen.getByRole("heading", { name: "Movilidad suave" });
    expect(article.compareDocumentPosition(activityHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    for (const name of ["Realizar actividad", "Ver otras actividades", "Finalizar sin actividad", "Analizar otra expresión"])
      expect(screen.getByRole("button", { name })).toBeInTheDocument();
    expect(vi.mocked(apiRequest).mock.calls.some(([path]) => path === "/chat")).toBe(false);
  });

  it("no muestra la nota de borrador cuando el texto está revisado y usa respaldo si falta el catálogo", async () => {
    const socket = await openLive();
    recognize(socket, { ...sadnessInfo, review_status: "reviewed", reviewed_at: "2026-10-08T10:00:00Z", reviewed_by_user_id: "admin" });
    expect(screen.queryByText(/pendiente de revisión/)).not.toBeInTheDocument();
    cleanup(); Socket.instances = [];
    const fallbackSocket = await openLive();
    recognize(fallbackSocket, null);
    expect(screen.getByRole("heading", { name: "Tristeza" })).toBeInTheDocument();
    expect(within(screen.getByRole("article", { name: "Tristeza" })).getByRole("note")).toHaveTextContent("no determina por sí mismo");
  });

  it("abre a Emi con una pregunta general editable, sin datos de la sesión, y no envía hasta pulsar Enviar", async () => {
    const socket = await openLive(true);
    recognize(socket, sadnessInfo);
    await userEvent.click(screen.getByRole("button", { name: "Preguntar a Emi sobre esta expresión" }));
    const question = screen.getByLabelText("Tu pregunta") as HTMLTextAreaElement;
    expect(question).toBeVisible();
    expect(question.value).toBe("¿Qué es la tristeza y cómo se reconoce en el rostro?");
    expect(question.value).not.toMatch(/\d|%|session|sesión|confianza/i);
    expect(vi.mocked(apiRequest).mock.calls.some(([path]) => path === "/chat")).toBe(false);
    await userEvent.clear(question);
    await userEvent.type(question, "¿Qué diferencia hay entre la tristeza y la neutralidad?");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    const chatCall = vi.mocked(apiRequest).mock.calls.find(([path]) => path === "/chat");
    expect(JSON.parse(String(chatCall?.[1]?.body))).toEqual({ question: "¿Qué diferencia hay entre la tristeza y la neutralidad?" });
  });

  it("si la recomendación falla, avisa y deja elegir de la lista o finalizar", async () => {
    const socket = await openLive();
    const notice = "No se pudo calcular la actividad recomendada. Tu expresión quedó registrada; puedes elegir una actividad de la lista o finalizar sin actividad.";
    const option = { id: "open_and_reach", name: "Abrir y alcanzar", description: "Varias posturas", required_posture: "arms_open", duration_seconds: 4, repetitions: 1, steps: [] };
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "recognized", emotion: "sadness", emotion_confidence: .9 }) }));
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "recommendation", emotion: "sadness", emotion_confidence: .9, activity: null, activities: [option], notice }) }));
    expect(screen.getByText(notice)).toBeInTheDocument();
    expect(screen.getByLabelText("Actividad que deseas realizar")).toHaveValue("open_and_reach");
    expect(screen.getByRole("button", { name: "Finalizar sin actividad" })).toBeInTheDocument();
  });

  it("muestra qué etapa falló", async () => {
    const socket = await openLive();
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "error", stage: "recognition", message: "Falló el reconocimiento de la expresión. Intenta de nuevo en unos minutos." }) }));
    expect(screen.getByRole("alert")).toHaveTextContent("Falló el reconocimiento de la expresión");
  });
});

describe("actividad secuencial con repeticiones", () => {
  it("muestra paso, repetición, postura esperada y tiempo restante, y anuncia cada paso una sola vez", async () => {
    class Utterance { lang = ""; rate = 1; voice: unknown = null; constructor(public text: string) {} }
    const synth = { getVoices: vi.fn(() => []), cancel: vi.fn(), speak: vi.fn() };
    vi.stubGlobal("SpeechSynthesisUtterance", Utterance);
    vi.stubGlobal("speechSynthesis", synth);
    const socket = await openLive();
    recognize(socket, sadnessInfo);
    const steps = [
      { posture: "arms_up", instruction: "Eleva los brazos", duration_seconds: 2 },
      { posture: "arms_open", instruction: "Abre los brazos", duration_seconds: 2 },
      { posture: "hands_on_hips", instruction: "Manos en las caderas", duration_seconds: 2 },
    ];
    const activity = { id: "flow", name: "Secuencia", description: "Tres posturas", required_posture: "arms_up", duration_seconds: 2, repetitions: 2, steps };
    const status = (index: number, remaining: number) => ({
      type: "status", state: "performing_exercise", message: "Mantén la postura", progress: index / 6,
      step: steps[index % 3], step_index: index, step_count: 6,
      repetition_index: Math.floor(index / 3), repetition_count: 2, step_remaining_seconds: remaining,
    });
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "activity_started", activity, message: "Adopta la postura" }) }));
    expect(screen.getByText(/Paso 1 de 3:/)).toBeInTheDocument();
    expect(screen.getByText("Repetición 1 de 2")).toBeInTheDocument();

    act(() => socket.onmessage?.({ data: JSON.stringify(status(0, 1.4)) }));
    act(() => socket.onmessage?.({ data: JSON.stringify(status(0, 0.9)) }));
    expect(screen.getByText("Tiempo restante del paso: 1 s")).toBeInTheDocument();
    for (let frame = 0; frame < 3; frame += 1) act(() => socket.onmessage?.({ data: JSON.stringify(status(3, 2)) }));

    expect(screen.getByText(/Paso 1 de 3:/)).toBeInTheDocument();
    expect(screen.getByText("Repetición 2 de 2")).toBeInTheDocument();
    expect(screen.getByText(/Postura esperada: Brazos arriba/)).toBeInTheDocument();
    expect(screen.getByText("Tiempo restante del paso: 2 s")).toBeInTheDocument();
    const spoken = synth.speak.mock.calls.map(([utterance]) => (utterance as Utterance).text);
    expect(spoken).toEqual([
      expect.stringContaining("Paso 1 de 3. Repetición 1 de 2. Eleva los brazos"),
      expect.stringContaining("Paso 1 de 3. Repetición 2 de 2. Eleva los brazos"),
    ]);
    vi.unstubAllGlobals();
  });
});
