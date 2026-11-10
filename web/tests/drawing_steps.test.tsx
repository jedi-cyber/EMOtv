import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../src/api/http";
import type { GuidedState, ParticipantViewState, SessionMetrics, SessionTimeline as Timeline } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { DRAWING_TIME_UP } from "../src/drawing/DrawingActivity";
import { SessionTimeline } from "../src/insights/SessionTimeline";
import { StimulusMetrics } from "../src/insights/StimulusMetrics";
import { GuidedConductorPage } from "../src/pages/GuidedConductorPage";
import { ParticipantViewPage } from "../src/pages/ParticipantViewPage";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";
import { protocolStepParts } from "../src/stimuli/labels";

// Bloque 4, subtarea 4a: el dibujo como paso de un protocolo. Solo viaja la emoción elegida.

const data = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === null ? null : data.value[path] ?? [], loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(), apiBlob: vi.fn(),
}));

class FakePointerEvent extends MouseEvent {
  pointerId: number;
  isPrimary: boolean;
  constructor(type: string, init: PointerEventInit = {}) {
    super(type, init);
    this.pointerId = init.pointerId ?? 1;
    this.isPrimary = init.isPrimary ?? true;
  }
  getCoalescedEvents() { return []; }
}

const ctx = {
  save: vi.fn(), restore: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(), stroke: vi.fn(),
  arc: vi.fn(), fill: vi.fn(), clearRect: vi.fn(),
  globalCompositeOperation: "source-over", strokeStyle: "", fillStyle: "", lineWidth: 1, lineCap: "butt", lineJoin: "miter",
};

beforeEach(() => {
  data.value = {};
  vi.mocked(apiRequest).mockReset();
  vi.stubGlobal("PointerEvent", FakePointerEvent);
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => ctx as never);
  Object.defineProperty(HTMLCanvasElement.prototype, "clientWidth", { configurable: true, get: () => 200 });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientHeight", { configurable: true, get: () => 100 });
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  Reflect.deleteProperty(HTMLCanvasElement.prototype, "clientWidth");
  Reflect.deleteProperty(HTMLCanvasElement.prototype, "clientHeight");
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
  { key: "happiness", label: "Alegría" }, { key: "sadness", label: "Tristeza" }, { key: "anger", label: "Enojo" },
  { key: "fear", label: "Miedo" }, { key: "surprise", label: "Sorpresa" }, { key: "disgust", label: "Asco" },
  { key: "neutral", label: "Cara tranquila" },
];

function drawingView(drawing: Partial<NonNullable<ParticipantViewState["drawing"]>> = {}): ParticipantViewState {
  return {
    phase: "stimuli", message: null, stimulus: null, remaining_seconds: 80, capture_frames: false, frame_interval_ms: 500,
    abstract_notice: null, uses_camera: false,
    drawing: { instruction: "Dibuja una cara que muestre una emoción.", question: "¿Qué emoción quisiste dibujar?",
      options, round: "0-1", finished: false, chosen: null, message: null, ...drawing },
  };
}

function participant(view: ParticipantViewState) {
  let current = view;
  vi.mocked(apiRequest).mockImplementation(async (path, init) => {
    if (path === "/participant-view/tok/answer") {
      const chosen = JSON.parse(String(init?.body)).expression as string;
      current = drawingView({ finished: true, chosen, message: "Dibujaste alegría." });
      return { received: true } as never;
    }
    return (path === "/participant-view/tok" ? current : { stopped: true }) as never;
  });
  return render(<MemoryRouter initialEntries={["/participant-view/tok"]}>
    <Routes><Route path="/participant-view/:token" element={<ParticipantViewPage />} /></Routes>
  </MemoryRouter>);
}

function draw(target: HTMLElement) {
  fireEvent.pointerDown(target, { pointerId: 1, isPrimary: true, clientX: 20, clientY: 20 });
  fireEvent.pointerMove(target, { pointerId: 1, isPrimary: true, clientX: 80, clientY: 60 });
  fireEvent.pointerUp(target, { pointerId: 1, isPrimary: true, clientX: 80, clientY: 60 });
}

describe("el dibujo en el editor de protocolos", () => {
  it("«Agregar dibujo» crea un paso sin imagen ni opciones y lo envía al servidor", async () => {
    withUser(<ProtocolsPage />);
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
    await userEvent.click(screen.getByRole("radio", { name: /Para niños/ }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Dibujar emociones");
    await userEvent.click(screen.getByRole("button", { name: "Agregar dibujo" }));
    expect(screen.getByText("1. Dibujo: una cara con una emoción")).toBeInTheDocument();
    expect(screen.getByLabelText("Tiempo para dibujar (s)")).toHaveValue(90);
    vi.mocked(apiRequest).mockResolvedValue({ id: "p1", version: 1 } as never);
    await userEvent.click(screen.getByRole("button", { name: "Guardar protocolo" }));
    const [, init] = vi.mocked(apiRequest).mock.calls.find(([path]) => path === "/protocols")!;
    expect(JSON.parse(String(init?.body)).steps).toEqual([{ kind: "drawing", stimulus_id: null, exposure_seconds: 90,
      capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false }]);
  });

  it("el resumen del protocolo cuenta los dibujos", () => {
    expect(protocolStepParts([{ kind: "drawing" }, { kind: "drawing" }, { kind: "recognition" }]))
      .toEqual(["1 reconocimiento", "2 dibujos"]);
  });
});

describe("el dibujo en la pantalla de la persona", () => {
  it("dibuja, elige la emoción y solo se envía esa emoción", async () => {
    participant(drawingView());
    const canvas = await screen.findByRole("img", { name: /Lienzo/ });
    expect(screen.queryByRole("button", { name: "Dibujar otra vez" })).not.toBeInTheDocument();
    draw(canvas);
    await userEvent.click(screen.getByRole("button", { name: "Terminé" }));
    expect(screen.getByText("¿Qué emoción quisiste dibujar?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Alegría/ }));
    expect(await screen.findByText("Dibujaste alegría.")).toBeInTheDocument();
    const sent = vi.mocked(apiRequest).mock.calls.filter(([, init]) => init?.method === "POST");
    expect(sent).toEqual([["/participant-view/tok/answer", expect.objectContaining({ body: JSON.stringify({ expression: "happiness" }) })]]);
    // Ni cuadros de la cámara ni el dibujo; nada en el almacenamiento del navegador.
    expect(vi.mocked(apiRequest).mock.calls.some(([path]) => String(path).endsWith("/frames"))).toBe(false);
    expect(sessionStorage.length + localStorage.length).toBe(0);
    // En la sesión, repetir lo decide quien conduce.
    expect(screen.queryByRole("button", { name: "Dibujar otra vez" })).not.toBeInTheDocument();
  });

  it("si vence el tiempo, el lienzo se cierra y lo dice sin valorar", async () => {
    participant(drawingView({ finished: true }));
    expect(await screen.findByText(DRAWING_TIME_UP)).toBeInTheDocument();
    expect(screen.queryByRole("toolbar", { name: "Herramientas de dibujo" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Terminé" })).not.toBeInTheDocument();
  });

  it("con un dibujo en pantalla, cerrar o recargar la pestaña pide confirmación", async () => {
    participant(drawingView());
    draw(await screen.findByRole("img", { name: /Lienzo/ }));
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
  });
});

const conductorState: GuidedState = {
  session_id: "s1", session_code: "S-4F7K2Q", phase: "stimuli", audience: "infantil", has_protocol: true, stop_reason: null,
  step_index: 0, step_count: 1, remaining_seconds: 60, steps_log: [],
  steps: [{ index: 0, stimulus_id: null, title: "", kind: "", exposure_seconds: 90, capture_after_seconds: 0,
    record_verbal_response: false, shown_before_analyzer: false, step_kind: "drawing", target_expression: null,
    hold_seconds: null, option_count: null }],
  calibration: { state: "none", progress: 0, notice: null }, capture_status: [], pre_questionnaire_id: null,
  post_questionnaire_id: null, abstract_notice: null, captures: [], markers: [], verbal_responses: [],
  drawing: { options: options.map((item) => item.key), chosen_expression: null, outcome: null },
  waiting_for_conductor: false, attempt: 1, can_repeat: false, max_attempts: 3, uses_camera: false,
};

describe("el dibujo para quien conduce", () => {
  it("registra la emoción que la persona señaló, sin ver el dibujo", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? conductorState : {}) as never);
    withUser(<GuidedConductorPage />, "/guided/s1");
    expect(await screen.findByText(/Paso 1 de 1 · dibujo/)).toBeInTheDocument();
    expect(screen.getByText(/El dibujo no llega aquí ni se guarda/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Miedo" }));
    expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/recognition",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ expression: "fear" }) }));
    expect(screen.getByRole("button", { name: "Saltar este dibujo" })).toBeInTheDocument();
  });

  it("al terminar, lista cada dibujo con la emoción señalada y sus repeticiones", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? {
      ...conductorState, phase: "finished", step_index: null, drawing: null, attempt: null,
      drawing_results: [{ step_index: 0, outcome: "answered", chosen_expression: "happiness", seconds_to_answer: 40, answered_by: "participant" }],
      repeated_attempts: [{ step_index: 0, attempt: 2, step_kind: "drawing", target_expression: null, outcome: "timed_out",
        chosen_expression: null, seconds_to_answer: null, answered_by: null }],
    } : {}) as never);
    withUser(<GuidedConductorPage />, "/guided/s1");
    const section = (await screen.findByRole("heading", { name: "Dibujos" })).closest("section")!;
    const items = within(section).getAllByRole("listitem").map((item) => item.textContent);
    expect(items[0]).toMatch(/^Paso 1 · Respondió: Alegría a los 40 s/);
    expect(items[1]).toBe("2.º intento · Terminó el tiempo sin respuesta");
  });
});

describe("el dibujo en el reporte", () => {
  it("las métricas y la línea de tiempo describen solo la emoción señalada", async () => {
    const metrics: SessionMetrics = {
      session_id: "s1", emotional: [], abstract: [], abstract_notice: null,
      totals: { emotional_stimuli: 0, counted: 0, matched: 0, excluded_captures: 0, sentence: "" },
      drawing: { notice: "Describe la emoción que la persona señaló en cada dibujo.",
        totals: { exercises: 2, answered: 1, timed_out: 1, skipped: 0, stopped: 0, not_reached: 0,
          sentence: "Señaló una emoción en 1 de 2 dibujos." },
        exercises: [{ step_index: 0, max_seconds: 90, outcome: "answered", chosen_expression: "sadness", seconds_to_answer: 30, answered_by: "conductor" },
          { step_index: 1, max_seconds: 90, outcome: "timed_out", chosen_expression: null, seconds_to_answer: null, answered_by: null }] },
    };
    render(<StimulusMetrics metrics={metrics} expressionLabel={(key) => key ?? "—"} />);
    const table = within(screen.getByRole("region", { name: "Dibujos" }));
    expect(table.getByText("Señaló una emoción en 1 de 2 dibujos.")).toBeInTheDocument();
    expect(table.getByText("Tristeza")).toBeInTheDocument();

    const timeline: Timeline = {
      session_id: "s1", started_at: "2026-11-06T10:00:00Z", duration_seconds: 60,
      lanes: { questionnaires: [], captures: [], said: [], markers: [], heart_rate: [],
        stimuli: [{ step_index: 0, title: "", kind: "drawing", start: 0, end: 40, skipped: false,
          outcome: "answered", chosen_expression: "sadness", seconds_to_answer: 30 }] },
    };
    render(<SessionTimeline timeline={timeline} expressionLabel={(key) => key ?? "—"} />);
    await waitFor(() => expect(screen.getAllByText(/Dibujo: señaló tristeza a los 30 s/).length).toBeGreaterThan(0));
  });
});
