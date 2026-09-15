import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AnalysisPage } from "../src/pages/AnalysisPage";
import { AuthContext } from "../src/auth/AuthContext";
import { apiRequest, ApiError } from "../src/api/http";

vi.mock("../src/api/useApiQuery", () => ({ useApiQuery: () => ({ data: { id: "arms_up_5s", name: "Brazos arriba", description: "Mantén ambos brazos arriba", required_posture: "arms_up", duration_seconds: 5, repetitions: 1 }, loading: false, error: "", reload: vi.fn() }) }));
vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn() }));

class Socket {
  static OPEN = 1; readyState = 1; binaryType = "";
  static instances: Socket[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null; onclose: (() => void) | null = null;
  send = vi.fn(); close = vi.fn();
  constructor() { Socket.instances.push(this); }
}

function camera(getUserMedia = vi.fn()) {
  vi.stubGlobal("navigator", Object.create(navigator, { mediaDevices: { value: { getUserMedia }, configurable: true } }));
  return getUserMedia;
}
function page() {
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "test", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}><MemoryRouter initialEntries={["/analysis?activity=arms_up_5s"]}><AnalysisPage /></MemoryRouter></AuthContext.Provider>);
}

beforeEach(() => {
  Socket.instances = []; vi.stubGlobal("WebSocket", Socket);
  vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
  vi.mocked(apiRequest).mockReset().mockImplementation(async (path) => path === "/sessions" ? { id: "s", state: "in_progress" } as never : {} as never);
});

describe("cámara y ciclo de actividad", () => {
  it("no crea una sesión si el navegador no admite cámara", async () => {
    vi.stubGlobal("navigator", Object.create(navigator, { mediaDevices: { value: undefined } }));
    page(); await userEvent.click(screen.getByRole("button", { name: "Permitir cámara e iniciar" }));
    expect(screen.getByRole("alert")).toHaveTextContent("HTTPS o localhost"); expect(apiRequest).not.toHaveBeenCalled();
  });
  it("no solicita cámara si falta consentimiento", async () => {
    const getMedia = camera(); vi.mocked(apiRequest).mockRejectedValueOnce(new ApiError(403, "El estudiante no tiene consentimiento activo"));
    page(); await userEvent.click(screen.getByRole("button", { name: "Permitir cámara e iniciar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("consentimiento activo"); expect(getMedia).not.toHaveBeenCalled();
  });
  it.each(["NotAllowedError", "NotFoundError"])("cancela la sesión al recibir %s", async (name) => {
    camera(vi.fn().mockRejectedValue(new DOMException("Cámara", name)));
    page(); await userEvent.click(screen.getByRole("button", { name: "Permitir cámara e iniciar" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/cámara/);
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/sessions/s/cancel", expect.objectContaining({ method: "POST" })));
  });
  it("muestra progreso y completa sin cancelar el resultado", async () => {
    const stop = vi.fn(); camera(vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] }));
    const view = page(); await userEvent.click(screen.getByRole("button", { name: "Permitir cámara e iniciar" }));
    await waitFor(() => expect(Socket.instances).toHaveLength(1)); const socket = Socket.instances[0];
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "status", state: "performing_exercise", progress: .5 }) }));
    expect(screen.getByRole("progressbar")).toHaveAttribute("aria-valuenow", "50");
    act(() => socket.onmessage?.({ data: JSON.stringify({ type: "completed", state: "completed", progress: 1 }) }));
    expect(screen.getByRole("link", { name: "Ver resultado" })).toBeInTheDocument(); expect(stop).toHaveBeenCalledOnce();
    view.unmount(); expect(apiRequest).not.toHaveBeenCalledWith("/sessions/s/cancel", expect.anything());
  });
  it("libera cámara y cancela al abandonar o perder conexión", async () => {
    const stop = vi.fn(); camera(vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] }));
    const view = page(); await userEvent.click(screen.getByRole("button", { name: "Permitir cámara e iniciar" }));
    await waitFor(() => expect(Socket.instances).toHaveLength(1));
    act(() => Socket.instances[0].onclose?.());
    expect(screen.getByRole("alert")).toHaveTextContent("Se perdió la conexión"); expect(stop).toHaveBeenCalledOnce();
    view.unmount(); expect(apiRequest).toHaveBeenCalledWith("/sessions/s/cancel", expect.objectContaining({ method: "POST" }));
  });
  it("detiene una cámara cuyo permiso llega después de abandonar la pantalla", async () => {
    let resolve!: (stream: unknown) => void;
    camera(vi.fn().mockReturnValue(new Promise((done) => { resolve = done; })));
    const view = page(); await userEvent.click(screen.getByRole("button", { name: "Permitir cámara e iniciar" }));
    view.unmount(); const stop = vi.fn();
    await act(async () => resolve({ getTracks: () => [{ stop }] }));
    expect(stop).toHaveBeenCalledOnce(); expect(Socket.instances).toHaveLength(0);
  });
});
