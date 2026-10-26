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
