import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../src/api/http";
import type { GuidedState } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { GuidedConductorPage } from "../src/pages/GuidedConductorPage";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";
import { insertItems, moveItemTo } from "../src/stimuli/cameraGame";
import { cameraGameSteps } from "../src/stimuli/cameraGame";
import { protocolStepLines, protocolStepParts } from "../src/stimuli/labels";

// «Usar el analizador» y arrastrar y soltar en el editor de protocolos.

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
});

function withUser(element: React.ReactNode, path = "/") {
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={[path]}><Routes>
      <Route path="/" element={element} />
      <Route path="/guided/:sessionId" element={element} />
    </Routes></MemoryRouter>
  </AuthContext.Provider>);
}

async function newProtocol() {
  withUser(<ProtocolsPage />);
  await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
}

const stepItem = (text: string) => screen.getByText(text).closest("li")!;

describe("«Usar el analizador» en el editor", () => {
  it("agrega un paso sin imagen ni expresión pedida y lo envía al servidor", async () => {
    await newProtocol();
    await userEvent.click(screen.getByRole("radio", { name: /Para adultos/ }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Pedir expresiones");
    await userEvent.click(screen.getByRole("button", { name: /^Usar el analizador/ }));
    expect(screen.getByText("1. Usar el analizador")).toBeInTheDocument();
    expect(screen.getByLabelText("Tiempo máximo (s)")).toHaveValue(180);
    expect(screen.queryByLabelText("Expresión pedida")).not.toBeInTheDocument();
    vi.mocked(apiRequest).mockResolvedValue({ id: "p1", version: 1 } as never);
    await userEvent.click(screen.getByRole("button", { name: "Guardar protocolo" }));
    const [, init] = vi.mocked(apiRequest).mock.calls.find(([path]) => path === "/protocols")!;
    expect(JSON.parse(String(init?.body)).steps).toEqual([{ kind: "analyzer", stimulus_id: null, exposure_seconds: 180,
      capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false }]);
  });

  it("el resumen y la vista previa lo nombran", () => {
    const step = { kind: "analyzer" as const, stimulus_id: null, exposure_seconds: 300, capture_after_seconds: 0,
      record_verbal_response: false, shown_before_analyzer: false };
    expect(protocolStepParts([step])).toEqual(["1 paso con el analizador"]);
    expect(protocolStepLines([step], () => undefined)).toEqual(["Usar el analizador: tú pides las expresiones · hasta 300 s"]);
  });
});

describe("arrastrar y soltar en el editor", () => {
  it("un paso se arrastra por su asa a otro lugar", async () => {
    await newProtocol();
    await userEvent.click(screen.getByRole("button", { name: "Dibujo" }));
    await userEvent.click(screen.getByRole("button", { name: /Juego: busca la misma emoción/ }));
    expect(screen.getByText("1. Dibujo: una cara con una emoción")).toBeInTheDocument();
    fireEvent.dragStart(screen.getByTestId("arrastrar-paso-2"));
    const target = stepItem("1. Dibujo: una cara con una emoción");
    fireEvent.dragOver(target);
    expect(target).toHaveClass("is-drop-before");
    fireEvent.drop(target);
    expect(screen.getByText("1. Juego: busca la misma emoción")).toBeInTheDocument();
    expect(screen.getByText("2. Dibujo: una cara con una emoción")).toBeInTheDocument();
    expect(document.querySelector(".is-drop-before, .is-dragging")).toBeNull();
  });

  it("una tarjeta de «Agregar un paso» se suelta donde se quiere", async () => {
    await newProtocol();
    await userEvent.click(screen.getByRole("button", { name: "Dibujo" }));
    fireEvent.dragStart(screen.getByRole("button", { name: /^Usar el analizador/ }));
    const target = stepItem("1. Dibujo: una cara con una emoción");
    fireEvent.dragOver(target);
    fireEvent.drop(target);
    expect(screen.getByText("1. Usar el analizador")).toBeInTheDocument();
    expect(screen.getByText("2. Dibujo: una cara con una emoción")).toBeInTheDocument();
  });

  it("sin pasos, la tarjeta se suelta en la lista vacía", async () => {
    await newProtocol();
    fireEvent.dragStart(screen.getByRole("button", { name: "Dibujo" }));
    const empty = screen.getByText(/Todavía no hay pasos/);
    fireEvent.dragOver(empty);
    fireEvent.drop(empty);
    expect(screen.getByText("1. Dibujo: una cara con una emoción")).toBeInTheDocument();
  });

  it("un juego con cámara se mueve entero y no se parte", () => {
    const drawing = { kind: "drawing" as const, stimulus_id: null, exposure_seconds: 90, capture_after_seconds: 0,
      record_verbal_response: false, shown_before_analyzer: false };
    const steps = [drawing, ...cameraGameSteps(3, 2, 20)];
    const moved = moveItemTo(steps, 2, 0);
    expect(moved.map((step) => step.game_round ?? 0)).toEqual([1, 2, 3, 0]);
    expect(moveItemTo(moved, 3, 0)).toEqual(steps);
    // Soltar dentro del propio juego no cambia nada.
    expect(moveItemTo(steps, 1, 2)).toBe(steps);
    expect(insertItems([drawing], 0, [steps[1]])[0].game_round).toBe(1);
  });
});

const conductorState: GuidedState = {
  session_id: "s1", session_code: "S-4F7K2Q", phase: "stimuli", audience: "adulto", has_protocol: true, stop_reason: null,
  step_index: 0, step_count: 2, remaining_seconds: 170, steps_log: [],
  steps: [{ index: 0, stimulus_id: null, title: "", kind: "", exposure_seconds: 180, capture_after_seconds: 0,
    record_verbal_response: false, shown_before_analyzer: false, step_kind: "analyzer", target_expression: null,
    hold_seconds: null, option_count: null }],
  calibration: { state: "none", progress: 0, notice: null }, capture_status: [], pre_questionnaire_id: null,
  post_questionnaire_id: null, abstract_notice: null, markers: [], verbal_responses: [],
  captures: [
    { id: "c1", captured_at: "2026-11-24T10:00:00Z", step_index: 0, stimulus_id: null, seconds_since_stimulus: 0.5,
      emotion: "neutral", confidence: 0.8, calibrated_emotion: null, quality: "good", quality_issues: [], emotion_model_id: "m" },
    { id: "c2", captured_at: "2026-11-24T10:00:03Z", step_index: 0, stimulus_id: null, seconds_since_stimulus: 3.5,
      emotion: "happiness", confidence: 0.9, calibrated_emotion: null, quality: "good", quality_issues: [], emotion_model_id: "m" },
  ],
  waiting_for_conductor: false, attempt: null, can_repeat: false, max_attempts: 3, uses_camera: true,
} as GuidedState;

describe("«Usar el analizador» para quien conduce", () => {
  it("muestra la última expresión estimada y pasa al siguiente paso", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? conductorState : {}) as never);
    withUser(<GuidedConductorPage />, "/guided/s1");
    expect(await screen.findByText(/Paso 1 de 2 · usar el analizador/)).toBeInTheDocument();
    expect(screen.getByText(/Expresión estimada ahora:/)).toBeInTheDocument();
    expect(screen.getByText(/no un diagnóstico/)).toBeInTheDocument();
    const items = screen.getByRole("list", { name: "Últimas estimaciones" }).querySelectorAll("li");
    expect(items[0]).toHaveTextContent("3.5 s");
    await userEvent.click(screen.getByRole("button", { name: "Siguiente paso" }));
    expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/analyzer-done", expect.objectContaining({ method: "POST" }));
  });
});
