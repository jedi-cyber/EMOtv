import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiBlob, apiRequest } from "../src/api/http";
import type { GuidedState, ParticipantGame, ParticipantViewState, SessionMetrics, SessionTimeline as Timeline } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { SessionTimeline } from "../src/insights/SessionTimeline";
import { StimulusMetrics } from "../src/insights/StimulusMetrics";
import { GuidedConductorPage } from "../src/pages/GuidedConductorPage";
import { ParticipantViewPage } from "../src/pages/ParticipantViewPage";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";
import { gameSentence, protocolStepParts } from "../src/stimuli/labels";

// Bloque 5: juego de emparejar expresiones. Botones, ayuda y explicación; sin puntaje.

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
  vi.mocked(apiBlob).mockResolvedValue(new Blob(["x"], { type: "image/png" }));
  URL.createObjectURL = vi.fn(() => "blob:ronda");
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

const options = [
  { key: "sadness", label: "Tristeza", available: true },
  { key: "happiness", label: "Alegría", available: true },
  { key: "anger", label: "Enojo", available: true },
];

function gameView(game: Partial<ParticipantGame> = {}): ParticipantViewState {
  return {
    phase: "stimuli", message: null, stimulus: { exposure: "0-1-0-1-0" }, remaining_seconds: 80, capture_frames: false,
    frame_interval_ms: 500, abstract_notice: null, uses_camera: false,
    game: { round: "0-1-0", number: 1, total: 3, question: "¿Qué emoción muestra esta cara?", state: "playing",
      options, answer: null, message: null, explanation: null, can_help: true, last_round: false, ...game },
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

const posted = () => vi.mocked(apiRequest).mock.calls.filter(([, init]) => init?.method === "POST")
  .map(([path, init]) => [path, JSON.parse(String(init?.body ?? "null"))]);

describe("el juego en el editor de protocolos", () => {
  it("«Agregar juego de emparejar» empieza con pocas opciones y deja subir la dificultad", async () => {
    withUser(<ProtocolsPage />);
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
    await userEvent.click(screen.getByRole("radio", { name: /Para niños/ }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Emparejar");
    await userEvent.click(screen.getByRole("button", { name: "Agregar juego de emparejar" }));
    expect(screen.getByText("1. Juego: empareja la emoción")).toBeInTheDocument();
    expect(screen.getByText(/una imagen emocional aprobada por ronda «Para niños»/)).toBeInTheDocument();
    expect(screen.getByLabelText("Opciones por ronda")).toHaveValue("2");
    await userEvent.selectOptions(screen.getByLabelText("Rondas"), "5");
    await userEvent.selectOptions(screen.getByLabelText("Opciones por ronda"), "3");
    vi.mocked(apiRequest).mockResolvedValue({ id: "p1", version: 1 } as never);
    await userEvent.click(screen.getByRole("button", { name: "Guardar protocolo" }));
    const [, init] = vi.mocked(apiRequest).mock.calls.find(([path]) => path === "/protocols")!;
    expect(JSON.parse(String(init?.body)).steps).toEqual([{ kind: "game", game_type: "matching", stimulus_id: null,
      rounds: 5, option_count: 3, game_stimulus_ids: [], exposure_seconds: 30, capture_after_seconds: 0,
      record_verbal_response: false, shown_before_analyzer: false }]);
  });

  it("el resumen del protocolo cuenta los juegos", () => {
    expect(protocolStepParts([{ kind: "game" }, { kind: "drawing" }])).toEqual(["1 dibujo", "1 juego"]);
  });
});

describe("el juego en la pantalla de la persona", () => {
  it("se juega con botones: reintento, ayuda, la emoción con su explicación y «Siguiente»", async () => {
    const retry = gameView({ state: "retry", message: "Mira otra vez la cara. Puedes pedir ayuda.",
      options: options.map((item) => item.key === "anger" ? { ...item, available: false } : item) });
    const helped = { ...retry, game: { ...retry.game!, can_help: false } };
    const found = gameView({ state: "matched", answer: "sadness", message: "Lo encontraste: es tristeza.",
      explanation: "La tristeza aparece cuando perdemos algo.", can_help: false });
    participant({ "answer:anger": retry, "help:": helped, "answer:sadness": found,
      "next:": gameView({ round: "0-1-1", number: 2 }) }, gameView());
    expect(await screen.findByText("Ronda 1 de 3")).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: "Cara de la ronda" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Siguiente" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Enojo" }));
    expect(await screen.findByText("Mira otra vez la cara. Puedes pedir ayuda.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Enojo" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Ayuda" }));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Ayuda" })).not.toBeInTheDocument());
    await userEvent.click(screen.getByRole("button", { name: "Tristeza" }));
    expect(await screen.findByText("Lo encontraste: es tristeza.")).toBeInTheDocument();
    expect(screen.getByText("La tristeza aparece cuando perdemos algo.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Tristeza/ })).toHaveTextContent("✓ Es esta");
    await userEvent.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(await screen.findByText("Ronda 2 de 3")).toBeInTheDocument();
    expect(posted()).toEqual([
      ["/participant-view/tok/game", { action: "answer", expression: "anger" }],
      ["/participant-view/tok/game", { action: "help" }],
      ["/participant-view/tok/game", { action: "answer", expression: "sadness" }],
      ["/participant-view/tok/game", { action: "next" }],
    ]);
    // Sin puntaje ni cuadros de la cámara.
    expect(screen.queryByText(/puntos|puntaje|correcto|incorrecto/i)).not.toBeInTheDocument();
    expect(vi.mocked(apiRequest).mock.calls.some(([path]) => String(path).endsWith("/frames"))).toBe(false);
  });

  it("en la última ronda, el botón dice «Terminar el juego»; «Quiero parar» sigue a la vista", async () => {
    participant({}, gameView({ state: "shown", answer: "anger", message: "Es enojo.", number: 3, last_round: true, can_help: false }));
    expect(await screen.findByRole("button", { name: "Terminar el juego" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Quiero parar" })).toBeInTheDocument();
  });
});

const conductorState: GuidedState = {
  session_id: "s1", session_code: "S-4F7K2Q", phase: "stimuli", audience: "infantil", has_protocol: true, stop_reason: null,
  step_index: 0, step_count: 1, remaining_seconds: 60, steps_log: [],
  steps: [{ index: 0, stimulus_id: null, title: "", kind: "", exposure_seconds: 30, capture_after_seconds: 0,
    record_verbal_response: false, shown_before_analyzer: false, step_kind: "game", target_expression: null,
    hold_seconds: null, option_count: 3 }],
  calibration: { state: "none", progress: 0, notice: null }, capture_status: [], pre_questionnaire_id: null,
  post_questionnaire_id: null, abstract_notice: null, captures: [], markers: [], verbal_responses: [],
  game: { round: 1, rounds: 3, stimulus_id: "img-1", target_expression: "sadness", options: ["sadness", "happiness", "anger"],
    tried: ["anger"], removed: null, state: "retry", helped: false, rounds_done: 0, matched: 0, first_try: 0, help_used: 0,
    outcome: null },
  waiting_for_conductor: false, attempt: 1, can_repeat: false, max_attempts: 3, uses_camera: false,
};

describe("el juego para quien conduce", () => {
  it("registra la emoción señalada, da la ayuda y salta", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? conductorState : {}) as never);
    withUser(<GuidedConductorPage />, "/guided/s1");
    expect(await screen.findByText(/Paso 1 de 1 · juego de emparejar/)).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Empareja la emoción · ronda 1 de 3" })).toBeInTheDocument();
    expect(screen.getByText(/Ya eligió: Enojo/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Enojo" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Tristeza" }));
    expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/game",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ action: "answer", expression: "sadness" }) }));
    await userEvent.click(screen.getByRole("button", { name: "Dar la ayuda" }));
    expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/game",
      expect.objectContaining({ body: JSON.stringify({ action: "help" }) }));
    expect(screen.getByRole("button", { name: "Saltar el juego" })).toBeInTheDocument();
  });

  it("al terminar, describe cada juego y sus repeticiones sin puntaje", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? {
      ...conductorState, phase: "finished", step_index: null, game: null, attempt: null,
      game_results: [{ step_index: 0, game_type: "matching", outcome: "completed", rounds_total: 3, rounds_done: 3,
        matched: 3, first_try: 2, help_used: 1, by_conductor: 0 }],
      repeated_attempts: [{ step_index: 0, attempt: 2, step_kind: "game", target_expression: null, outcome: "skipped",
        rounds_total: 3, rounds_done: 1, matched: 1, first_try: 1, help_used: 0 }],
    } : {}) as never);
    withUser(<GuidedConductorPage />, "/guided/s1");
    const section = (await screen.findByRole("heading", { name: "Juegos de emparejar" })).closest("section")!;
    const items = within(section).getAllByRole("listitem").map((item) => item.textContent);
    expect(items[0]).toMatch(/^Paso 1 · Completo. Jugó 3 de 3 rondas\. Emparejó 3 imágenes, 2 a la primera; usó la ayuda 1 vez\./);
    expect(items[1]).toBe("2.º intento · Se saltó. Jugó 1 de 3 rondas. Emparejó 1 imagen, 1 a la primera; no usó la ayuda.");
  });
});

describe("el juego en el reporte", () => {
  it("las métricas y la línea de tiempo describen las rondas", async () => {
    const metrics: SessionMetrics = {
      session_id: "s1", emotional: [], abstract: [], abstract_notice: null,
      totals: { emotional_stimuli: 0, counted: 0, matched: 0, excluded_captures: 0, sentence: "" },
      game: { notice: "Describe lo que ocurrió en el juego.",
        totals: { games: 1, completed: 1, timed_out: 0, skipped: 0, stopped: 0, not_reached: 0, rounds_total: 3,
          rounds_done: 3, matched: 2, first_try: 1, help_used: 1,
          sentence: gameSentence({ rounds_total: 3, rounds_done: 3, matched: 2, first_try: 1, help_used: 1 }) },
        exercises: [{ step_index: 0, game_type: "matching", rounds: 3, option_count: 2, outcome: "completed", rounds_done: 3,
          matched: 2, first_try: 1, help_used: 1, by_conductor: 1,
          sentence: "Jugó 3 de 3 rondas. Emparejó 2 imágenes, 1 a la primera; usó la ayuda 1 vez." }] },
    };
    render(<StimulusMetrics metrics={metrics} expressionLabel={(key) => key ?? "—"} />);
    const region = within(screen.getByRole("region", { name: "Juegos de emparejar" }));
    expect(region.getAllByText(/Jugó 3 de 3 rondas\. Emparejó 2 imágenes, 1 a la primera; usó la ayuda 1 vez\./).length).toBe(2);
    expect(region.getByText("3 rondas · 2 opciones")).toBeInTheDocument();

    const timeline: Timeline = {
      session_id: "s1", started_at: "2026-11-06T10:00:00Z", duration_seconds: 60,
      lanes: { questionnaires: [], captures: [], said: [], markers: [], heart_rate: [],
        stimuli: [{ step_index: 0, title: "", kind: "game", start: 0, end: 50, skipped: false, outcome: "completed",
          rounds: 3, sentence: "Jugó 3 de 3 rondas. Emparejó 2 imágenes, 1 a la primera; usó la ayuda 1 vez." }] },
    };
    render(<SessionTimeline timeline={timeline} expressionLabel={(key) => key ?? "—"} />);
    await waitFor(() => expect(screen.getAllByText(/Juego de emparejar: completo. Jugó 3 de 3 rondas/).length).toBeGreaterThan(0));
  });
});
