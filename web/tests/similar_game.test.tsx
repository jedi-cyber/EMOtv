import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiBlob, apiRequest } from "../src/api/http";
import type { GuidedState, ParticipantGame, ParticipantViewState, SessionMetrics } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { StimulusMetrics } from "../src/insights/StimulusMetrics";
import { GuidedConductorPage } from "../src/pages/GuidedConductorPage";
import { ParticipantViewPage } from "../src/pages/ParticipantViewPage";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";

// Bloque 6: «Busca la misma emoción». Mismo paso y motor que el juego de emparejar;
// las opciones son caras (imágenes), sin decir su emoción hasta terminar la ronda.

const data = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === null ? null : data.value[path] ?? [], loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(), apiBlob: vi.fn(),
}));

beforeEach(() => {
  data.value = {};
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiBlob).mockReset();
  vi.mocked(apiBlob).mockImplementation(async (path) => new Blob([String(path)], { type: "image/png" }));
  let made = 0;
  URL.createObjectURL = vi.fn(() => `blob:imagen-${made += 1}`);
  URL.revokeObjectURL = vi.fn();
});

function withUser(element: React.ReactNode, path = "/") {
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={[path]}><Routes>
      <Route path="/" element={element} />
      <Route path="/guided/:sessionId" element={element} />
    </Routes></MemoryRouter>
  </AuthContext.Provider>);
}

const faces = [
  { key: "1", label: "Cara 1", available: true },
  { key: "2", label: "Cara 2", available: true },
  { key: "3", label: "Cara 3", available: true },
];

function gameView(game: Partial<ParticipantGame> = {}): ParticipantViewState {
  return {
    phase: "stimuli", message: null, stimulus: { exposure: "0-1-0-1-0" }, remaining_seconds: 80, capture_frames: false,
    frame_interval_ms: 500, abstract_notice: null, uses_camera: false,
    supports: { pictograms: true, large_controls: false, read_aloud: false },
    game: { round: "0-1-0", number: 1, total: 2, game_type: "similar",
      question: "¿Qué cara muestra la misma emoción que la de arriba?", state: "playing",
      options: faces, answer: null, message: null, explanation: null, can_help: true, last_round: false, ...game },
  };
}

function participant(views: Record<string, ParticipantViewState>, first: ParticipantViewState) {
  let current = first;
  vi.mocked(apiRequest).mockImplementation(async (path, init) => {
    if (path === "/participant-view/tok/game") {
      const body = JSON.parse(String(init?.body)) as { action: string; expression?: string };
      current = views[`${body.action}:${body.expression ?? ""}`] ?? current;
      return { received: true } as never;
    }
    return (path === "/participant-view/tok" ? current : { stopped: true }) as never;
  });
  return render(<MemoryRouter initialEntries={["/participant-view/tok"]}>
    <Routes><Route path="/participant-view/:token" element={<ParticipantViewPage />} /></Routes>
  </MemoryRouter>);
}

describe("«Busca la misma emoción» en el editor", () => {
  it("se agrega con pocas caras y explica qué imágenes necesita", async () => {
    withUser(<ProtocolsPage />);
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
    await userEvent.click(screen.getByRole("radio", { name: /Para adultos/ }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Misma emoción");
    await userEvent.click(screen.getByRole("button", { name: "Agregar juego: busca la misma emoción" }));
    expect(screen.getByText("1. Juego: busca la misma emoción")).toBeInTheDocument();
    expect(screen.getByText(/otra imagen de la misma emoción que se ve distinta \(nunca la misma imagen repetida\)/)).toBeInTheDocument();
    expect(screen.getByLabelText("Caras para elegir")).toHaveValue("2");
    await userEvent.selectOptions(screen.getByLabelText("Caras para elegir"), "3");
    vi.mocked(apiRequest).mockResolvedValue({ id: "p1", version: 1 } as never);
    await userEvent.click(screen.getByRole("button", { name: "Guardar protocolo" }));
    const [, init] = vi.mocked(apiRequest).mock.calls.find(([path]) => path === "/protocols")!;
    expect(JSON.parse(String(init?.body)).steps).toEqual([{ kind: "game", game_type: "similar", stimulus_id: null,
      rounds: 3, option_count: 3, game_stimulus_ids: [], exposure_seconds: 30, capture_after_seconds: 0,
      record_verbal_response: false, shown_before_analyzer: false }]);
  });
});

describe("«Busca la misma emoción» en la pantalla de la persona", () => {
  it("muestra la cara de arriba y una cara por botón, sin emociones ni pictogramas, con ayuda y reintento", async () => {
    const helped = gameView({ can_help: false, options: faces.map((item) => item.key === "3" ? { ...item, available: false } : item) });
    const retry = { ...helped, game: { ...helped.game!, state: "retry" as const,
      message: "Mira otra vez la cara de arriba. Puedes pedir ayuda.",
      options: helped.game!.options.map((item) => item.key === "1" ? { ...item, available: false } : item) } };
    const found = gameView({ state: "matched", answer: "2", can_help: false,
      message: "Lo encontraste: las dos caras muestran la misma emoción, alegría.", explanation: "La alegría aparece cuando algo nos gusta." });
    participant({ "help:": helped, "answer:1": retry, "answer:2": found }, gameView());
    expect(await screen.findByRole("img", { name: "Cara de arriba, la que hay que comparar" })).toBeInTheDocument();
    // Cada opción es un botón con su cara; el nombre accesible no dice la emoción.
    const buttons = ["Cara 1", "Cara 2", "Cara 3"].map((name) => screen.getByRole("button", { name }));
    await waitFor(() => expect(buttons[0].querySelector("img")).not.toBeNull());
    expect(vi.mocked(apiBlob).mock.calls.map(([path]) => path)).toEqual(expect.arrayContaining([
      "/participant-view/tok/stimulus", "/participant-view/tok/game/option/1", "/participant-view/tok/game/option/2",
      "/participant-view/tok/game/option/3"]));
    expect(screen.queryByText(/Alegría|Tristeza|Enojo|😊|😢/)).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Ayuda" }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Cara 3" })).toBeDisabled());
    await userEvent.click(screen.getByRole("button", { name: "Cara 1" }));
    expect(await screen.findByText("Mira otra vez la cara de arriba. Puedes pedir ayuda.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cara 2" }));
    expect(await screen.findByText("Lo encontraste: las dos caras muestran la misma emoción, alegría.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Cara 2/ })).toHaveTextContent("✓ Es esta");
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Quiero parar" })).toBeInTheDocument();
    expect(screen.queryByText(/puntos|puntaje|correcto|incorrecto/i)).not.toBeInTheDocument();
  });
});

const conductorState: GuidedState = {
  session_id: "s1", session_code: "S-4F7K2Q", phase: "stimuli", audience: "infantil", has_protocol: true, stop_reason: null,
  step_index: 0, step_count: 1, remaining_seconds: 60, steps_log: [],
  steps: [{ index: 0, stimulus_id: null, title: "", kind: "", exposure_seconds: 30, capture_after_seconds: 0,
    record_verbal_response: false, shown_before_analyzer: false, step_kind: "game", target_expression: null,
    hold_seconds: null, option_count: 2 }],
  calibration: { state: "none", progress: 0, notice: null }, capture_status: [], pre_questionnaire_id: null,
  post_questionnaire_id: null, abstract_notice: null, captures: [], markers: [], verbal_responses: [],
  game: { round: 1, rounds: 2, game_type: "similar", stimulus_id: "modelo", target_expression: "happiness",
    options: ["1", "2"], option_details: [{ key: "1", expression: "sadness", stimulus_id: "b" },
      { key: "2", expression: "happiness", stimulus_id: "c" }],
    tried: ["1"], removed: null, state: "retry", helped: false, rounds_done: 0, matched: 0, first_try: 0, help_used: 0,
    outcome: null },
  waiting_for_conductor: false, attempt: 1, can_repeat: false, max_attempts: 3, uses_camera: false,
};

describe("«Busca la misma emoción» para quien conduce", () => {
  it("ve la emoción de cada cara y registra la que la persona señaló por su lugar", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? conductorState : {}) as never);
    withUser(<GuidedConductorPage />, "/guided/s1");
    expect(await screen.findByText(/Paso 1 de 1 · juego de la misma emoción/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Busca la misma emoción · ronda 1 de 2" })).toBeInTheDocument();
    expect(screen.getByText(/Emoción de la cara de arriba: Alegría\. Ya eligió: Cara 1 \(Tristeza\)\./)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Cara 2 (Alegría)" }));
    expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/game",
      expect.objectContaining({ body: JSON.stringify({ action: "answer", expression: "2" }) }));
  });
});

describe("«Busca la misma emoción» en el reporte", () => {
  it("las métricas nombran el juego", () => {
    const metrics: SessionMetrics = {
      session_id: "s1", emotional: [], abstract: [], abstract_notice: null,
      totals: { emotional_stimuli: 0, counted: 0, matched: 0, excluded_captures: 0, sentence: "" },
      game: { notice: "Describe lo que ocurrió en el juego.",
        totals: { games: 1, completed: 1, timed_out: 0, skipped: 0, stopped: 0, not_reached: 0, rounds_total: 2,
          rounds_done: 2, matched: 2, first_try: 2, help_used: 0, sentence: "Jugó 2 de 2 rondas." },
        exercises: [{ step_index: 0, game_type: "similar", rounds: 2, option_count: 2, outcome: "completed", rounds_done: 2,
          matched: 2, first_try: 2, help_used: 0, by_conductor: 0, sentence: "Jugó 2 de 2 rondas." }] },
    };
    render(<StimulusMetrics metrics={metrics} expressionLabel={(key) => key ?? "—"} />);
    expect(screen.getByRole("cell", { name: "Juego: busca la misma emoción" })).toBeInTheDocument();
  });
});
