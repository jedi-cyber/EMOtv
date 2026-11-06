import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../src/api/http";
import type { GuidedState, ParticipantViewState } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { GuidedConductorPage } from "../src/pages/GuidedConductorPage";
import { ParticipantViewPage } from "../src/pages/ParticipantViewPage";

vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(), apiBlob: vi.fn(),
}));

const NOTICE = "Registro descriptivo. Una sesión breve no permite sacar conclusiones a partir de una imagen.";
const baseState: GuidedState = {
  session_id: "s1", session_code: "S-4F7K2Q", phase: "calibration", audience: "adulto", has_protocol: true, stop_reason: null, step_index: null, step_count: 2,
  steps: [
    { index: 0, stimulus_id: "e1", title: "Paisaje", kind: "emotional", exposure_seconds: 6, capture_after_seconds: 2, record_verbal_response: false, shown_before_analyzer: false },
    { index: 1, stimulus_id: "a1", title: "Forma", kind: "abstract", exposure_seconds: 8, capture_after_seconds: 2, record_verbal_response: true, shown_before_analyzer: false },
  ],
  remaining_seconds: null, steps_log: [], calibration: { state: "none", progress: 0, notice: null }, capture_status: [],
  pre_questionnaire_id: null, post_questionnaire_id: null, abstract_notice: NOTICE, captures: [], markers: [], verbal_responses: [],
};

function conductor(state: GuidedState) {
  vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? state : {}) as never);
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={["/guided/s1"]}><Routes><Route path="/guided/:sessionId" element={<GuidedConductorPage />} /></Routes></MemoryRouter>
  </AuthContext.Provider>);
}

function participant(view: ParticipantViewState) {
  vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/participant-view/tok" ? view : { stopped: true }) as never);
  return render(<MemoryRouter initialEntries={["/participant-view/tok"]}>
    <Routes><Route path="/participant-view/:token" element={<ParticipantViewPage />} /></Routes>
  </MemoryRouter>);
}

beforeEach(() => { vi.mocked(apiRequest).mockReset(); sessionStorage.clear(); });

describe("sesión con protocolo", () => {
  it("no vuelve a pedir confirmación: se confirmó una vez en el Analizador, y muestra el código", async () => {
    conductor(baseState);
    expect(await screen.findByText("S-4F7K2Q")).toBeInTheDocument();
    expect(screen.getByText(/Anótalo en el formato firmado/)).toBeInTheDocument();
    expect(screen.queryByRole("checkbox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Confirmar/ })).not.toBeInTheDocument();
    expect(apiRequest).not.toHaveBeenCalledWith("/guided-sessions/s1/confirm", expect.anything());
    expect(screen.queryByRole("button", { name: "El tutor pidió parar" })).not.toBeInTheDocument();
  });

  it("con un niño ofrece que el tutor pida parar", async () => {
    conductor({ ...baseState, audience: "infantil" });
    expect(await screen.findByRole("button", { name: "El tutor pidió parar" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "La persona pidió parar" })).toBeInTheDocument();
  });

  it("registra marcadores con teclas rápidas y recuerda no escribir datos que identifiquen", async () => {
    conductor({ ...baseState, phase: "stimuli", step_index: 1, remaining_seconds: 5 });
    expect(await screen.findByText("Forma")).toBeInTheDocument();
    expect(screen.getByText(NOTICE)).toBeInTheDocument();
    expect(screen.getAllByText(/No escribas nombres ni datos que identifiquen a la persona/).length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Lo que la persona dice ver")).toBeInTheDocument();
    await userEvent.keyboard("d");
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/markers", expect.objectContaining({ body: JSON.stringify({ kind: "distracted" }) })));
    await userEvent.click(screen.getByRole("button", { name: /Lloró/ }));
    expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/markers", expect.objectContaining({ body: JSON.stringify({ kind: "cried" }) }));
    // Escribir en un campo no dispara las teclas rápidas.
    vi.mocked(apiRequest).mockClear();
    await userEvent.type(screen.getByLabelText("Nota breve"), "d");
    expect(apiRequest).not.toHaveBeenCalledWith("/guided-sessions/s1/markers", expect.anything());
  });

  it("la pantalla de la persona no muestra resultados y tiene un botón visible para parar", async () => {
    participant({ phase: "stimuli", message: null, stimulus: null, remaining_seconds: 4, capture_frames: false,
      frame_interval_ms: 500, abstract_notice: NOTICE });
    const stop = await screen.findByRole("button", { name: "Quiero parar" });
    expect(screen.getByText(NOTICE)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/felicidad|tristeza|confianza|%|calidad|nota/i);
    expect(screen.queryByRole("navigation")).not.toBeInTheDocument();
    await userEvent.click(stop);
    expect(apiRequest).toHaveBeenCalledWith("/participant-view/tok/stop", expect.objectContaining({ method: "POST" }));
    expect(await screen.findByText("La sesión terminó. Gracias.")).toBeInTheDocument();
  });
});

describe("sesión sin cámara (solo reconocimientos)", () => {
  const ready: GuidedState = { ...baseState, phase: "ready", uses_camera: false, abstract_notice: null };

  it("quien conduce no ve la calibración y empieza el primer paso con «Empezar»", async () => {
    conductor(ready);
    const start = await screen.findByRole("button", { name: "Empezar" });
    expect(screen.getByText(/no usa la cámara: no hay calibración/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Iniciar calibración" })).not.toBeInTheDocument();
    await userEvent.click(start);
    expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/start", expect.objectContaining({ method: "POST" }));
    expect(apiRequest).not.toHaveBeenCalledWith("/guided-sessions/s1/calibration", expect.anything());
  });

  it("con cámara sigue mostrando la calibración", async () => {
    conductor(baseState);
    expect(await screen.findByRole("button", { name: "Iniciar calibración" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Empezar" })).not.toBeInTheDocument();
  });

  it("la pantalla de la persona espera sin pedir la cámara", async () => {
    const getUserMedia = vi.fn();
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
    const { container } = participant({ phase: "ready", message: "En un momento empezamos.", stimulus: null,
      remaining_seconds: null, capture_frames: false, frame_interval_ms: 500, abstract_notice: null, uses_camera: false });
    expect(await screen.findByText("En un momento empezamos.")).toBeInTheDocument();
    expect(container.querySelector("video")).toBeNull();
    expect(getUserMedia).not.toHaveBeenCalled();
  });
});

describe("sin cámara en una sesión que la usa", () => {
  const participantView: ParticipantViewState = { phase: "calibration", message: "Mira a la pantalla con el rostro relajado.",
    stimulus: null, remaining_seconds: null, capture_frames: true, frame_interval_ms: 500, abstract_notice: null };

  it("si se niega el permiso, la persona sabe qué puede seguir haciendo y quien conduce recibe el motivo", async () => {
    const getUserMedia = vi.fn().mockRejectedValue(new DOMException("denied", "NotAllowedError"));
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
    participant(participantView);
    expect(await screen.findByText(/puedes seguir con las actividades de elegir emociones/)).toBeInTheDocument();
    expect(getUserMedia).toHaveBeenCalledTimes(1);
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/participant-view/tok/camera-problem",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ reason: "denied" }) })));
  });

  it("la cámara se libera cuando deja de hacer falta", async () => {
    const stop = vi.fn();
    const getUserMedia = vi.fn().mockResolvedValue({ getTracks: () => [{ stop }] });
    Object.defineProperty(navigator, "mediaDevices", { configurable: true, value: { getUserMedia } });
    vi.spyOn(HTMLMediaElement.prototype, "play").mockResolvedValue();
    let current: ParticipantViewState = participantView;
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/participant-view/tok" ? current : {}) as never);
    render(<MemoryRouter initialEntries={["/participant-view/tok"]}>
      <Routes><Route path="/participant-view/:token" element={<ParticipantViewPage />} /></Routes>
    </MemoryRouter>);
    await waitFor(() => expect(getUserMedia).toHaveBeenCalledTimes(1));
    // Un paso «¿Qué emoción es?»: ya no se envían cuadros y la cámara se apaga.
    current = { ...participantView, phase: "stimuli", capture_frames: false, message: null };
    await waitFor(() => expect(stop).toHaveBeenCalled(), { timeout: 2000 });
  });

  it("quien conduce ve por qué no hay cámara y puede seguir sin ella", async () => {
    conductor({ ...baseState, uses_camera: true, camera_problem: "denied", camera_off: false });
    expect(await screen.findByText(/no pudo usar la cámara: se negó el permiso/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Continuar sin cámara" }));
    expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/continue-without-camera", expect.objectContaining({ method: "POST" }));
  });

  it("tras seguir sin cámara, quien conduce lo ve y no se ofrece de nuevo", async () => {
    conductor({ ...baseState, phase: "stimuli", step_index: 0, remaining_seconds: 4, uses_camera: true, camera_off: true });
    expect(await screen.findByText(/La sesión sigue sin cámara/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Continuar sin cámara" })).not.toBeInTheDocument();
  });
});
