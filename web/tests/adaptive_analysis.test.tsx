import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdaptiveAnalysisPage } from "../src/pages/AdaptiveAnalysisPage";
import { AuthContext } from "../src/auth/AuthContext";
import { apiRequest } from "../src/api/http";

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

function page(role: "student" | "admin" = "student") {
  const router = createMemoryRouter([{ path: "/analysis", element: <AdaptiveAnalysisPage /> }], { initialEntries: ["/analysis"] });
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "student@example.com", role, is_active: true }, token: "test", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}><RouterProvider router={router} /></AuthContext.Provider>);
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

async function openLive() {
  camera();
  page();
  await userEvent.click(screen.getByRole("button", { name: "Reconocer mi expresión" }));
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
    await userEvent.click(screen.getByRole("button", { name: "Probar cámara" }));
    expect(getUserMedia).toHaveBeenCalledOnce();
    expect(screen.getByRole("button", { name: "Apagar cámara" })).toBeInTheDocument();
    expect(apiRequest).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Apagar cámara" }));
    expect(stop).toHaveBeenCalledOnce();
  });

  it("explica la falta de consentimiento antes de abrir la cámara", async () => {
    const getUserMedia = camera();
    vi.mocked(apiRequest).mockImplementation(async (path) => path === "/consent-policy" ? { id: "EMOTV-CONSENT-DEMO-001:v0.1", mode: "demo", available: true } as never : path === "/students" ? [{ id: "student-1" }] as never : null as never);
    page();
    await userEvent.click(screen.getByRole("button", { name: "Reconocer mi expresión" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Debes aceptar la versión vigente");
    expect(getUserMedia).not.toHaveBeenCalled();
    expect(Socket.instances).toHaveLength(0);
  });

  it("explica el permiso de cámara denegado sin crear sesión", async () => {
    camera(vi.fn().mockRejectedValue(new DOMException("denied", "NotAllowedError")));
    page();
    await userEvent.click(screen.getByRole("button", { name: "Probar cámara" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Permite el acceso a la cámara");
    expect(apiRequest).not.toHaveBeenCalled();
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
    await userEvent.click(screen.getByRole("button", { name: "Reconocer mi expresión" }));
    await waitFor(() => expect(Socket.instances).toHaveLength(1));
    act(() => Socket.instances[0].onopen?.());
    expect(JSON.parse(Socket.instances[0].send.mock.calls[0][0])).toEqual(expect.objectContaining({ emotion_model_id: "ferplus_onnx" }));
    act(() => Socket.instances[0].onmessage?.({ data: JSON.stringify({ type: "error", message: "Modelo bloqueado: Benchmark vencido" }) }));
    expect(await screen.findByText(/Modelo bloqueado: Benchmark vencido/)).toBeInTheDocument();
  });

  it("reconoce primero, muestra sugerencia y solo entonces asigna la actividad", async () => {
    const stop = vi.fn(); const getUserMedia = camera(vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] }));
    page();
    await userEvent.click(screen.getByRole("button", { name: "Reconocer mi expresión" }));
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
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "recommendation", state: "choosing_activity", message: "Actividad sugerida", emotion: "sadness", emotion_confidence: .9, activity, activities: [activity, alternative] }) }));
    expect(screen.getByText(/Expresión registrada:/)).toHaveTextContent("Tristeza (90 %)");
    expect(screen.queryByRole("heading", { name: "Movilidad suave" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Continuar" }));
    expect(screen.getByRole("heading", { name: "Movilidad suave" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Finalizar sin actividad" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Pasos de la actividad" })).toBeInTheDocument();
    expect(screen.getByText("Abre los brazos")).toBeInTheDocument();
    expect(screen.getByText("Eleva los brazos")).toBeInTheDocument();
    expect(screen.queryByLabelText("Actividad que deseas realizar")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ver otras actividades" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ver otras actividades" }));
    expect(screen.getByLabelText("Actividad que deseas realizar")).toHaveValue("open_and_reach");
    expect(screen.getByRole("option", { name: "Abrir y alcanzar" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Realizar actividad recomendada" }));
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
    await userEvent.click(screen.getByRole("button", { name: "Registrar otra expresión" }));
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
    expect(screen.getByRole("list", { name: "Clases más probables" }).children).toHaveLength(3);
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
    await userEvent.click(screen.getByRole("button", { name: "Continuar" }));
    await userEvent.click(screen.getByRole("button", { name: "Finalizar sin actividad" }));
    expect(JSON.parse(socket.send.mock.calls.at(-1)![0])).toEqual({ type: "finish_without_activity" });
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "completed", message: "Sesión finalizada", emotion: "neutral", emotion_confidence: .7, exercise_result: "skipped" }) }));
    expect(screen.getByText("Sesión finalizada sin actividad. Tu expresión quedó registrada.")).toBeInTheDocument();
    expect(screen.getByText(/Expresión registrada:/)).toHaveTextContent("Neutral (70 %)");
    expect(screen.getByRole("button", { name: "Registrar otra expresión" })).toBeInTheDocument();
  });
});
