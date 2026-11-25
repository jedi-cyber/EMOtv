import { render, screen, within } from "@testing-library/react";
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
import { protocolStepLines } from "../src/stimuli/labels";

// «Reconoce y luego muéstrala»: tras cada ronda la persona pone la cara de la
// emoción; solo quien conduce ve el nivel y lo que estimó la cámara.

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
  { key: "sadness", label: "Tristeza", available: false },
  { key: "happiness", label: "Alegría", available: false },
];

function gameView(game: Partial<ParticipantGame>): ParticipantViewState {
  return {
    phase: "stimuli", message: null, stimulus: { exposure: "0-1-0-1-0" }, remaining_seconds: 80, capture_frames: false,
    frame_interval_ms: 500, abstract_notice: null, uses_camera: false,
    game: { round: "0-1-0", number: 1, total: 2, question: "¿Qué emoción muestra esta cara?", state: "matched",
      options, answer: "happiness", message: "Lo encontraste: es alegría.", explanation: "La alegría aparece…",
      can_help: false, last_round: false, asks_face: true, ...game },
  };
}

function participant(first: ParticipantViewState, next: ParticipantViewState) {
  let current = first;
  vi.mocked(apiRequest).mockImplementation(async (path) => {
    if (path === "/participant-view/tok/game") { current = next; return { received: true } as never; }
    return (path === "/participant-view/tok" ? current : { stopped: true }) as never;
  });
  return render(<MemoryRouter initialEntries={["/participant-view/tok"]}>
    <Routes><Route path="/participant-view/:token" element={<ParticipantViewPage />} /></Routes>
  </MemoryRouter>);
}

describe("el editor", () => {
  it("un juego puede pedir mostrar la emoción después de cada ronda", async () => {
    withUser(<ProtocolsPage />);
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
    await userEvent.click(screen.getByRole("radio", { name: /Para niños/ }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Reconoce y muestra");
    await userEvent.click(screen.getByRole("button", { name: "Juego: empareja la emoción" }));
    await userEvent.click(screen.getByRole("checkbox", { name: /pedir que muestre la emoción/ }));
    expect(screen.getByText(/Ella solo ve un mensaje amable; el nivel y el resultado los ves tú/)).toBeInTheDocument();
    vi.mocked(apiRequest).mockResolvedValue({ id: "p1", version: 1 } as never);
    await userEvent.click(screen.getByRole("button", { name: "Guardar protocolo" }));
    const [, init] = vi.mocked(apiRequest).mock.calls.find(([path]) => path === "/protocols")!;
    expect(JSON.parse(String(init?.body)).steps[0]).toMatchObject({ kind: "game", show_expression: true });
  });

  it("el resumen del protocolo lo menciona", () => {
    expect(protocolStepLines([{ kind: "game", game_type: "matching", rounds: 3, show_expression: true,
      stimulus_id: null, exposure_seconds: 30, capture_after_seconds: 0, record_verbal_response: false,
      shown_before_analyzer: false }], () => undefined)[0]).toMatch(/3 rondas, luego muestra la emoción/);
  });
});

describe("la pantalla de la persona", () => {
  it("ve la invitación y después un mensaje amable, sin nivel ni resultado", async () => {
    participant(
      gameView({ state: "show", message: "Ahora pon tú esa cara: alegría. Mira a la cámara.", asks_face: false }),
      gameView({ state: "showed", message: "¡Gracias por intentarlo! Sigamos jugando.", asks_face: false }));
    expect(await screen.findByText("Ahora pon tú esa cara: alegría. Mira a la cámara.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Alegría" })).not.toBeInTheDocument();
    expect(screen.queryByText("La alegría aparece…")).not.toBeInTheDocument();
    expect(screen.queryByRole("meter")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Seguir" }));
    expect(await screen.findByText("¡Gracias por intentarlo! Sigamos jugando.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeInTheDocument();
    expect(screen.queryByText(/lo logr|estim|nivel|%/i)).not.toBeInTheDocument();
  });

  it("en la última ronda, si falta mostrar la cara, el botón dice «Siguiente»", async () => {
    participant(gameView({ number: 2, last_round: true }), gameView({}));
    expect(await screen.findByRole("button", { name: "Siguiente" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Terminar el juego" })).not.toBeInTheDocument();
  });
});

const conductorState: GuidedState = {
  session_id: "s1", session_code: "S-4F7K2Q", phase: "stimuli", audience: "infantil", has_protocol: true, stop_reason: null,
  step_index: 0, step_count: 1, remaining_seconds: 60, steps_log: [],
  steps: [{ index: 0, stimulus_id: null, title: "", kind: "", exposure_seconds: 30, capture_after_seconds: 0,
    record_verbal_response: false, shown_before_analyzer: false, step_kind: "game", target_expression: null,
    hold_seconds: null, option_count: 2, show_expression: true }],
  calibration: { state: "none", progress: 0, notice: null }, capture_status: [], pre_questionnaire_id: null,
  post_questionnaire_id: null, abstract_notice: null, captures: [], markers: [], verbal_responses: [],
  game: { round: 1, rounds: 2, stimulus_id: "img-1", target_expression: "happiness", options: ["sadness", "happiness"],
    tried: [], removed: null, state: "show", helped: false, rounds_done: 1, matched: 1, first_try: 1, help_used: 0,
    outcome: null, show_expression: true, faces_asked: 1, faces_shown: 0,
    face: { showing: true, level: 0.4, achieved: null, remaining_seconds: 5.2 } },
  waiting_for_conductor: false, attempt: 1, can_repeat: false, max_attempts: 3, uses_camera: true, camera_off: true,
};

describe("la pantalla de quien conduce", () => {
  it("ve la emoción pedida, el nivel en vivo y lo que estimó la cámara", async () => {
    let current = conductorState;
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? current : {}) as never);
    const view = withUser(<GuidedConductorPage />, "/guided/s1");
    expect(await screen.findByText("Se le pide poner la cara: Alegría. Quedan 6 s.")).toBeInTheDocument();
    expect(screen.getByRole("meter")).toHaveValue(0.4);
    expect(screen.getByText("Es una estimación de la cámara, no una valoración.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Pasar sin esperar" }));
    expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/game",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ action: "next" }) }));

    current = { ...conductorState, game: { ...conductorState.game!, state: "showed", faces_shown: 1,
      face: { showing: false, level: 1, achieved: true, remaining_seconds: null } } };
    view.unmount();
    withUser(<GuidedConductorPage />, "/guided/s1");
    expect(await screen.findByText(/La cámara estimó la expresión pedida\./)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Siguiente ronda" })).toBeInTheDocument();
  });
});

describe("el reporte", () => {
  it("las métricas describen lo que estimó la cámara, sin valorar", () => {
    const sentence = "Al pedirle poner la cara, la cámara estimó la expresión pedida en 1 de 2 rondas. Es una estimación, no una valoración.";
    const metrics: SessionMetrics = {
      session_id: "s1", emotional: [], abstract: [], abstract_notice: null,
      totals: { emotional_stimuli: 0, counted: 0, matched: 0, excluded_captures: 0, sentence: "" },
      game: { notice: "Describe lo que ocurrió en el juego.",
        totals: { games: 1, completed: 1, timed_out: 0, skipped: 0, stopped: 0, not_reached: 0, rounds_total: 2,
          rounds_done: 2, matched: 2, first_try: 2, help_used: 0, sentence: "Jugó 2 de 2 rondas.",
          faces: { faces_asked: 2, faces_shown: 1 }, face_sentence: sentence },
        exercises: [{ step_index: 0, game_type: "matching", rounds: 2, option_count: 2, outcome: "completed", rounds_done: 2,
          matched: 2, first_try: 2, help_used: 0, by_conductor: 0, sentence: "Jugó 2 de 2 rondas.",
          show_expression: true, faces_asked: 2, faces_shown: 1, face_sentence: sentence }] },
    };
    render(<StimulusMetrics metrics={metrics} expressionLabel={(key) => key ?? "—"} />);
    const region = within(screen.getByRole("region", { name: "Juegos" }));
    expect(region.getAllByText(new RegExp(sentence.slice(0, 40))).length).toBe(2);
  });
});
