import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdaptiveAnalysisPage } from "../src/pages/AdaptiveAnalysisPage";
import { AuthContext } from "../src/auth/AuthContext";
import { apiRequest } from "../src/api/http";

const { admissions } = vi.hoisted(() => ({ admissions: { value: [{ model_id: "ferplus_onnx", state: "SUPPORTED", reasons: [] as string[] }] } }));
vi.mock("../src/api/useApiQuery", () => ({ useApiQuery: () => ({ data: admissions.value, loading: false, error: "", reload: vi.fn() }) }));
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

function page() {
  const router = createMemoryRouter([{ path: "/analysis", element: <AdaptiveAnalysisPage /> }], { initialEntries: ["/analysis"] });
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "student@example.com", role: "student", is_active: true }, token: "test", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}><RouterProvider router={router} /></AuthContext.Provider>);
}

function camera(getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => [{ stop: vi.fn() }] })) {
  vi.stubGlobal("navigator", Object.create(navigator, { mediaDevices: { value: { getUserMedia }, configurable: true } }));
  return getUserMedia;
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

  it("impide iniciar con un modelo bloqueado e indica el motivo", async () => {
    admissions.value = [{ model_id: "ferplus_onnx", state: "BLOCKED", reasons: ["Benchmark vencido"] }];
    page();
    expect(screen.getByRole("button", { name: "Reconocer mi expresión" })).toBeDisabled();
    expect(screen.getByRole("alert")).toHaveTextContent("Modelo no disponible: Benchmark vencido");
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
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "ready", state: "analyzing_emotion", message: "Cámara conectada" }) }));
    const activity = { id: "arms_up_5s", name: "Elevación de brazos", description: "Levanta los brazos", required_posture: "arms_up", duration_seconds: 5, repetitions: 1 };
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "recommendation", state: "choosing_activity", message: "Actividad sugerida", emotion: "sadness", emotion_confidence: .9, activity, activities: [activity] }) }));
    expect(screen.getByText(/Actividad sugerida:/)).toBeInTheDocument();
    expect(screen.getByText(/Expresión detectada:/)).toHaveTextContent("sadness");
    await userEvent.click(screen.getByRole("button", { name: "Continuar con la actividad" }));
    expect(JSON.parse(socket.send.mock.calls.at(-1)![0])).toEqual({ type: "select_activity", activity_id: "arms_up_5s" });
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "activity_started", activity, message: "Adopta la postura" }) }));
    expect(screen.getByRole("heading", { name: "Elevación de brazos" })).toBeInTheDocument();
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "completed", activity, message: "Completada", progress: 1 }) }));
    expect(screen.getByRole("link", { name: "Ver resultado" })).toHaveAttribute("href", "/sessions/session-1");
    expect(stop).toHaveBeenCalledOnce();
    await userEvent.click(screen.getByRole("button", { name: "Volver a analizar mi expresión" }));
    await waitFor(() => expect(Socket.instances).toHaveLength(2));
    expect(getUserMedia).toHaveBeenCalledTimes(2);
    expect(vi.mocked(apiRequest).mock.calls.filter(([path]) => path === "/sessions")).toHaveLength(2);
    expect(screen.queryByText(/Expresión detectada:/)).not.toBeInTheDocument();
  });
});
