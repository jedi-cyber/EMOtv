import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiBlob, apiRequest } from "../src/api/http";
import type { GuidedState, ParticipantRecognition, ParticipantViewState, SessionMetrics, SessionRecognition } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { StimulusMetrics } from "../src/insights/StimulusMetrics";
import { GuidedConductorPage } from "../src/pages/GuidedConductorPage";
import { ParticipantViewPage } from "../src/pages/ParticipantViewPage";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";
import { protocolStepParts } from "../src/stimuli/labels";

const data = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === null ? null : data.value[path] ?? [], loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(), apiBlob: vi.fn(),
}));

const VALUATIONS = /correct|incorrect|acertaste|fallaste|bien hecho|excelente|mal\b|diagn|patol/i;

function withUser(element: React.ReactNode, path = "/") {
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={[path]}><Routes>
      <Route path="/" element={element} />
      <Route path="/guided/:sessionId" element={element} />
      <Route path="/participant-view/:token" element={element} />
    </Routes></MemoryRouter>
  </AuthContext.Provider>);
}

beforeEach(() => { data.value = {}; vi.mocked(apiRequest).mockReset(); vi.mocked(apiBlob).mockReset(); });

describe("«¿Qué emoción es?» en el editor de protocolos", () => {
  async function openEditor() {
    data.value["/stimuli"] = [
      { id: "sad", title: "Niño triste", kind: "emotional", expected_expression: "sadness", intensity: "mild", audience: "children", scope: "group", approved: true, active: true, category: "Dibujo", min_age: 1 },
      { id: "own", title: "Mi foto de un paisaje", kind: "emotional", expected_expression: null, intensity: "mild", audience: "children", scope: "user", approved: true, active: true, category: "", min_age: 1 },
    ];
    withUser(<ProtocolsPage />);
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
    await userEvent.click(screen.getByRole("radio", { name: /Para niños/ }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Reconocer emociones");
  }

  it("agrega una imagen emocional con su respuesta, 3 opciones y tiempo para responder", async () => {
    await openEditor();
    const add = screen.getByRole("button", { name: "Agregar como «¿Qué emoción es?»" });
    expect(add).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Imagen"), "own");
    expect(add).toBeDisabled();                            // sin expresión esperada no hay respuesta
    await userEvent.selectOptions(screen.getByLabelText("Imagen"), "sad");
    await userEvent.click(add);
    expect(screen.getByText(/Respuesta: Tristeza/)).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Opciones"), "4");
    vi.mocked(apiRequest).mockResolvedValue({ id: "p1", version: 1 } as never);
    await userEvent.click(screen.getByRole("button", { name: "Guardar protocolo" }));
    const [, init] = vi.mocked(apiRequest).mock.calls.find(([path]) => path === "/protocols")!;
    expect(JSON.parse(String(init?.body)).steps).toEqual([{ kind: "recognition", stimulus_id: "sad", option_count: 4,
      exposure_seconds: 15, capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false }]);
  });

  it("el resumen de pasos cuenta los reconocimientos aparte", () => {
    expect(protocolStepParts([{ kind: "stimulus" }, { kind: "recognition" }, { kind: "recognition" }]))
      .toEqual(["1 imagen", "2 reconocimientos"]);
    expect(protocolStepParts([{ kind: "recognition" }])).toEqual(["1 reconocimiento"]);
  });
});

const recognition: ParticipantRecognition = {
  question: "¿Qué emoción es?", chosen: null, message: null,
  options: [{ key: "anger", label: "Enojo" }, { key: "sadness", label: "Tristeza" }, { key: "happiness", label: "Alegría" }],
};
const view: ParticipantViewState = {
  phase: "stimuli", message: null, stimulus: { exposure: "0-1" }, remaining_seconds: 10, capture_frames: false,
  frame_interval_ms: 500, abstract_notice: null, recognition,
};

describe("«¿Qué emoción es?» en la pantalla de la persona", () => {
  function participant(state: ParticipantViewState) {
    vi.mocked(apiBlob).mockResolvedValue(new Blob(["png"], { type: "image/png" }));
    URL.createObjectURL = vi.fn(() => "blob:imagen");
    URL.revokeObjectURL = vi.fn();
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/participant-view/tok" ? state : { received: true }) as never);
    return withUser(<ParticipantViewPage />, "/participant-view/tok");
  }

  it("muestra la imagen, la pregunta y una opción por emoción, y envía la elegida", async () => {
    participant(view);
    expect(await screen.findByText("¿Qué emoción es?")).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: "Imagen de la sesión" })).toHaveAttribute("src", "blob:imagen");
    expect(screen.getAllByRole("button", { pressed: false }).map((button) => button.textContent)).toEqual(["Enojo", "Tristeza", "Alegría"]);
    await userEvent.click(screen.getByRole("button", { name: "Tristeza" }));
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/participant-view/tok/answer",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ expression: "sadness" }) })));
  });

  it("al terminar nombra la emoción de la imagen sin decir si acertó", async () => {
    participant({ ...view, recognition: { ...recognition, chosen: "anger", message: "Es tristeza" } });
    expect(await screen.findByRole("status")).toHaveTextContent("Es tristeza");
    expect(screen.getByRole("button", { name: "Enojo" })).toHaveAttribute("aria-pressed", "true");
    for (const button of screen.getAllByRole("button", { name: /Enojo|Tristeza|Alegría/ })) expect(button).toBeDisabled();
    expect(document.body.textContent).not.toMatch(VALUATIONS);
  });
});

const recognitionStep = { index: 0, stimulus_id: "sad", title: "Niño triste", kind: "emotional" as const, exposure_seconds: 15,
  capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false, step_kind: "recognition" as const,
  target_expression: "sadness", hold_seconds: null, option_count: 3 };
const conductorState: GuidedState = {
  session_id: "s1", session_code: "S-4F7K2Q", phase: "stimuli", audience: "infantil", has_protocol: true, stop_reason: null,
  step_index: 0, step_count: 1, steps: [recognitionStep], remaining_seconds: 12, steps_log: [],
  calibration: { state: "calibrated", progress: 1, notice: null }, capture_status: [], pre_questionnaire_id: null,
  post_questionnaire_id: null, abstract_notice: null, captures: [], markers: [], verbal_responses: [],
  recognition: { target_expression: "sadness", options: ["anger", "sadness", "happiness"], chosen_expression: null, outcome: null },
  recognition_results: [],
};

describe("«¿Qué emoción es?» para quien conduce", () => {
  function conductor(state: GuidedState) {
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? state : {}) as never);
    return withUser(<GuidedConductorPage />, "/guided/s1");
  }

  it("muestra la emoción de la imagen y registra la opción que la persona señaló", async () => {
    conductor(conductorState);
    expect(await screen.findByRole("heading", { name: "¿Qué emoción es? · Niño triste" })).toBeInTheDocument();
    expect(screen.getByText(/Emoción de la imagen: Tristeza/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Enojo" }));
    expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/recognition", expect.objectContaining({ body: JSON.stringify({ expression: "anger" }) }));
  });

  it("describe lo elegido y resume los pasos terminados", async () => {
    conductor({ ...conductorState, recognition: { ...conductorState.recognition!, chosen_expression: "anger", outcome: "answered" },
      recognition_results: [{ step_index: 0, stimulus_id: "sad", target_expression: "sadness", options: ["anger", "sadness", "happiness"],
        outcome: "answered", chosen_expression: "anger", matched: false, seconds_to_answer: 3.5, answered_by: "participant" }] });
    expect(await screen.findByText("Eligió Enojo. El paso avanza en un momento.")).toBeInTheDocument();
    expect(screen.getByText(/Paso 1 · imagen de Tristeza · Respondió: Enojo a los 3[.,]5 s/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(VALUATIONS);
  });
});

const sessionRecognition: SessionRecognition = {
  exercises: [
    { step_index: 0, stimulus_id: "sad", target_expression: "sadness", max_seconds: 15, options: ["anger", "sadness", "happiness"],
      outcome: "answered", chosen_expression: "sadness", matched: true, seconds_to_answer: 2, answered_by: "participant" },
    { step_index: 1, stimulus_id: "joy", target_expression: "happiness", max_seconds: 15, options: ["happiness", "fear"],
      outcome: "timed_out", chosen_expression: null, matched: null, seconds_to_answer: null, answered_by: null },
  ],
  totals: { exercises: 2, not_reached: 0, applied: 2, matched: 1, timed_out: 1, skipped: 0, stopped: 0,
    average_seconds_to_answer: 2, sentence: "Eligió la emoción de la imagen en 1 de 2 ejercicios." },
  by_target: [
    { target_expression: "happiness", applied: 1, matched: 0, timed_out: 1, skipped: 0, stopped: 0, other_choices: [] },
    { target_expression: "sadness", applied: 1, matched: 1, timed_out: 0, skipped: 0, stopped: 0, other_choices: [] },
  ],
  notice: "Describe las respuestas de esta práctica. Una sesión breve no permite sacar conclusiones sobre cómo reconoce emociones la persona.",
};

describe("«¿Qué emoción es?» en las métricas (detalle, reporte e impresión)", () => {
  it("muestra el aviso, la frase y cada paso tal como ocurrió", () => {
    const metrics: SessionMetrics = {
      session_id: "s1", emotional: [], abstract: [], abstract_notice: null, practice: null, recognition: sessionRecognition,
      totals: { emotional_stimuli: 0, counted: 0, matched: 0, excluded_captures: 0, sentence: "" },
    };
    render(<MemoryRouter><StimulusMetrics metrics={metrics} expressionLabel={(key) => key ?? "—"} /></MemoryRouter>);
    expect(screen.getByRole("note")).toHaveTextContent("Una sesión breve no permite sacar conclusiones");
    expect(screen.getByText("Eligió la emoción de la imagen en 1 de 2 ejercicios.")).toBeInTheDocument();
    expect(screen.getByText("Terminó el tiempo sin respuesta")).toBeInTheDocument();
    expect(screen.getByText("Enojo, Tristeza, Alegría")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(VALUATIONS);
  });
});
