import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../src/api/http";
import type { GuidedState, SessionTimeline as Timeline } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { SessionTimeline } from "../src/insights/SessionTimeline";
import { GuidedConductorPage } from "../src/pages/GuidedConductorPage";

// Bloque 2b, parte 2: repetir un reconocimiento o un ejercicio. Las métricas cuentan el primer intento.
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: () => ({ data: [], loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(), apiBlob: vi.fn(),
}));

function conductor(state: GuidedState) {
  vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? state : {}) as never);
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={["/guided/s1"]}><Routes>
      <Route path="/guided/:sessionId" element={<GuidedConductorPage />} />
    </Routes></MemoryRouter>
  </AuthContext.Provider>);
}

const base: GuidedState = {
  session_id: "s1", session_code: "S-4F7K2Q", phase: "stimuli", audience: "propia", has_protocol: true, stop_reason: null,
  step_index: 0, step_count: 2, remaining_seconds: null, steps_log: [],
  steps: [{ index: 0, stimulus_id: "sad", title: "Niño triste", kind: "emotional", exposure_seconds: 15, capture_after_seconds: 0,
    record_verbal_response: false, shown_before_analyzer: false, step_kind: "recognition", target_expression: "sadness",
    hold_seconds: null, option_count: 2 }],
  calibration: { state: "none", progress: 0, notice: null }, capture_status: [], pre_questionnaire_id: null,
  post_questionnaire_id: null, abstract_notice: null, captures: [], markers: [], verbal_responses: [],
  recognition: { target_expression: "sadness", situation: null, options: ["sadness", "happiness"], chosen_expression: "happiness", outcome: "answered" },
  recognition_results: [], waiting_for_conductor: true, attempt: 1, can_repeat: true, max_attempts: 3,
  supports: { pictograms: false, large_controls: false, read_aloud: false, no_time_limit: true, pause: "wait" },
};

beforeEach(() => { vi.mocked(apiRequest).mockReset(); });

describe("repetir un paso", () => {
  it("«Repetir este paso» aparece al terminar el paso y lo pide al servidor", async () => {
    conductor(base);
    await userEvent.click(await screen.findByRole("button", { name: "Repetir este paso" }));
    expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/repeat", expect.objectContaining({ method: "POST" }));
    expect(screen.getByRole("button", { name: "Seguir" })).toBeInTheDocument();
  });

  it("sin intentos libres no se ofrece y el paso dice en qué intento va", async () => {
    conductor({ ...base, attempt: 3, can_repeat: false });
    expect(await screen.findByText(/Paso 1 de 2 · reconocimiento · intento 3 de 3/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Repetir este paso" })).not.toBeInTheDocument();
  });

  it("el primer intento no muestra el número de intento", async () => {
    conductor({ ...base, can_repeat: false, waiting_for_conductor: false });
    expect(await screen.findByText(/Paso 1 de 2 · reconocimiento/)).not.toHaveTextContent("intento");
  });

  it("al terminar, cada repetición se describe debajo de su primer intento", async () => {
    conductor({
      ...base, phase: "finished", step_index: null, recognition: null, can_repeat: false, attempt: null,
      recognition_results: [{ step_index: 0, stimulus_id: "sad", target_expression: "sadness", options: ["sadness", "happiness"],
        outcome: "answered", chosen_expression: "happiness", matched: false, seconds_to_answer: 6, answered_by: "participant" }],
      repeated_attempts: [{ step_index: 0, attempt: 2, step_kind: "recognition", target_expression: "sadness",
        outcome: "answered", chosen_expression: "sadness", seconds_to_answer: 3, answered_by: "conductor" }],
    });
    const section = (await screen.findByRole("heading", { name: "Reconocimiento de emociones" })).closest("section")!;
    const items = within(section).getAllByRole("listitem").map((item) => item.textContent);
    expect(items[0]).toMatch(/^Paso 1 · imagen de Tristeza · Respondió: Alegría a los 6 s/);
    expect(items[1]).toBe("2.º intento · Respondió: Tristeza a los 3 s · registrado por quien conduce");
  });
});

describe("repeticiones en la línea de tiempo", () => {
  it("se listan después del primer intento, sin valorar", () => {
    const timeline: Timeline = {
      session_id: "s1", started_at: "2026-11-06T10:00:00Z", duration_seconds: 30,
      lanes: {
        questionnaires: [], captures: [], said: [], markers: [], heart_rate: [],
        stimuli: [{ step_index: 0, title: "Niño triste", kind: "recognition", start: 0, end: 20, skipped: false,
          target_expression: "sadness", outcome: "answered", chosen_expression: "happiness", seconds_to_answer: 6,
          repeats: [{ attempt: 2, outcome: "answered", chosen_expression: "sadness", seconds_to_answer: 3 }] }],
      },
    };
    render(<SessionTimeline timeline={timeline} expressionLabel={(key) => key ?? "—"} />);
    // En el dibujo y en la lista de eventos.
    expect(screen.getAllByText(/«Niño triste» \(Tristeza\) · respondió: Alegría a los 6 s · 2\.º intento: respondió: Tristeza a los 3 s/)
      .length).toBeGreaterThan(0);
  });
});
