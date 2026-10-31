import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../src/api/http";
import type { GuidedState } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { GuidedConductorPage } from "../src/pages/GuidedConductorPage";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";
import { protocolStepParts } from "../src/stimuli/labels";

const data = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === null ? null : data.value[path] ?? [], loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(), apiBlob: vi.fn(),
}));

function withUser(element: React.ReactNode, path = "/") {
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={[path]}><Routes>
      <Route path="/" element={element} />
      <Route path="/guided/:sessionId" element={element} />
    </Routes></MemoryRouter>
  </AuthContext.Provider>);
}

beforeEach(() => { data.value = {}; vi.mocked(apiRequest).mockReset(); });

describe("ejercicios de práctica en el editor de protocolos", () => {
  async function openEditor() {
    data.value["/stimuli"] = [
      { id: "a", title: "Sol", kind: "emotional", intensity: "mild", audience: "children", scope: "group", approved: true, active: true, category: "Dibujo", min_age: 1 },
    ];
    withUser(<ProtocolsPage />);
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
    await userEvent.click(screen.getByRole("radio", { name: /Para niños/ }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Práctica de expresiones");
    await userEvent.click(screen.getByRole("button", { name: "Agregar ejercicio de práctica" }));
  }

  it("elige la expresión pedida, el sostén y el tiempo máximo, y lo envía al servidor", async () => {
    await openEditor();
    const options = within(screen.getByLabelText("Expresión pedida")).getAllByRole("option").map((option) => option.textContent);
    // Todo el catálogo: quien arma el protocolo elige, incluido desprecio.
    expect(options).toEqual(["Alegría", "Sorpresa", "Tristeza", "Enojo", "Miedo", "Asco", "Cara tranquila", "Desprecio"]);
    await userEvent.selectOptions(screen.getByLabelText("Expresión pedida"), "surprise");
    await userEvent.clear(screen.getByLabelText("Sostener (s)"));
    await userEvent.type(screen.getByLabelText("Sostener (s)"), "3");
    await userEvent.selectOptions(screen.getByLabelText("Ilustración (opcional)"), "a");
    vi.mocked(apiRequest).mockResolvedValue({ id: "p1", version: 1 } as never);
    await userEvent.click(screen.getByRole("button", { name: "Guardar protocolo" }));
    const [, init] = vi.mocked(apiRequest).mock.calls.find(([path]) => path === "/protocols")!;
    const body = JSON.parse(String(init?.body));
    expect(body.for_children).toBe(true);
    expect(body.steps).toEqual([{ kind: "practice", stimulus_id: "a", target_expression: "surprise", hold_seconds: 3,
      exposure_seconds: 20, capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false }]);
  });

  it("propone el sostén y el tiempo máximo que configura el servidor", async () => {
    data.value["/protocols/practice-defaults"] = { hold_seconds: 4, max_seconds: 30, targets: [] };
    await openEditor();
    expect(screen.getByLabelText("Sostener (s)")).toHaveValue(4);
    expect(screen.getByLabelText("Tiempo máximo (s)")).toHaveValue(30);
  });

  it("muestra las reglas del dominio en español y no deja guardar", async () => {
    await openEditor();
    const save = screen.getByRole("button", { name: "Guardar protocolo" });
    expect(save).toBeEnabled();
    await userEvent.clear(screen.getByLabelText("Sostener (s)"));
    await userEvent.type(screen.getByLabelText("Sostener (s)"), "12");
    expect(screen.getByRole("alert")).toHaveTextContent("La expresión se sostiene entre 1 y 10 segundos");
    expect(save).toBeDisabled();
    await userEvent.clear(screen.getByLabelText("Sostener (s)"));
    await userEvent.type(screen.getByLabelText("Sostener (s)"), "5");
    await userEvent.clear(screen.getByLabelText("Tiempo máximo (s)"));
    await userEvent.type(screen.getByLabelText("Tiempo máximo (s)"), "5");
    expect(screen.getByRole("alert")).toHaveTextContent("El tiempo máximo de la práctica es mayor que el tiempo de sostén");
    expect(save).toBeDisabled();
  });

  it("un ejercicio sin ilustración no necesita imagen", async () => {
    await openEditor();
    expect(screen.getByLabelText("Ilustración (opcional)")).toHaveValue("");
    expect(screen.queryByText(/Necesita una imagen/)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Guardar protocolo" })).toBeEnabled();
  });

  it("la lista cuenta imágenes y ejercicios", () => {
    data.value["/protocols"] = [{ id: "p1", family_id: "p1", version: 1, name: "Mixto", description: "", for_children: true,
      pre_questionnaire_id: null, post_questionnaire_id: null, created_at: "2026-10-30T10:00:00Z", owned_by_me: true, used: false, needs_image: false,
      steps: [
        { kind: "stimulus", stimulus_id: "a", exposure_seconds: 8, capture_after_seconds: 4, record_verbal_response: false, shown_before_analyzer: false },
        { kind: "practice", stimulus_id: null, target_expression: "happiness", hold_seconds: 2, exposure_seconds: 15, capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false },
        { kind: "practice", stimulus_id: null, target_expression: "sadness", hold_seconds: 2, exposure_seconds: 15, capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false },
      ] }];
    withUser(<ProtocolsPage />);
    expect(screen.getByText(/1 imagen · 2 ejercicios/)).toBeInTheDocument();
  });

  it("el resumen de pasos no llama imagen a un ejercicio", () => {
    expect(protocolStepParts([{ kind: "practice" }])).toEqual(["1 ejercicio de práctica"]);
    expect(protocolStepParts([{ kind: "stimulus" }, { kind: "stimulus" }, { kind: "practice" }]))
      .toEqual(["2 imágenes", "1 ejercicio de práctica"]);
  });
});

const practiceStep = { index: 0, stimulus_id: null, title: "", kind: "" as const, exposure_seconds: 15, capture_after_seconds: 0,
  record_verbal_response: false, shown_before_analyzer: false, step_kind: "practice" as const, target_expression: "happiness", hold_seconds: 2 };
const practiceState: GuidedState = {
  session_id: "s1", session_code: "S-4F7K2Q", phase: "stimuli", audience: "infantil", has_protocol: true, stop_reason: null,
  step_index: 0, step_count: 1, steps: [practiceStep], remaining_seconds: 12, steps_log: [],
  calibration: { state: "calibrated", progress: 1, notice: null }, capture_status: [], pre_questionnaire_id: null,
  post_questionnaire_id: null, abstract_notice: null, captures: [], markers: [], verbal_responses: [],
  practice_feedback: true, practice: { target_expression: "happiness", hold_seconds: 2, level: 0.4, achieved: false }, practice_results: [],
};

function conductor(state: GuidedState) {
  vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? state : {}) as never);
  return withUser(<GuidedConductorPage />, "/guided/s1");
}

describe("ejercicio de práctica para quien conduce", () => {
  it("muestra la expresión pedida, el nivel en vivo y los marcadores", async () => {
    conductor(practiceState);
    expect(await screen.findByRole("heading", { name: "Expresión pedida: Alegría" })).toBeInTheDocument();
    const meter = screen.getByLabelText("Nivel en vivo");
    expect(meter).toHaveAttribute("value", "0.4");
    expect(screen.getByText("Se registra como lograda cuando la sostiene 2 s.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Saltar este ejercicio" })).toBeInTheDocument();
    expect(screen.queryByText(/Captura automática/)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /Se rió/ }));
    expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/markers", expect.objectContaining({ body: JSON.stringify({ kind: "laughed" }) }));
  });

  it("indica cuando se logró", async () => {
    conductor({ ...practiceState, practice: { ...practiceState.practice!, level: 1, achieved: true } });
    expect(await screen.findByText(/Logró la expresión pedida\. El ejercicio avanza/)).toBeInTheDocument();
  });

  it("el interruptor apaga y enciende la señal de la persona", async () => {
    conductor(practiceState);
    const toggle = await screen.findByRole("checkbox", { name: /Mostrar la señal a la persona/ });
    expect(toggle).toBeChecked();
    await userEvent.click(toggle);
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/practice-feedback",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ visible: false }) })));
  });

  it("con la señal apagada lo dice", async () => {
    conductor({ ...practiceState, practice_feedback: false });
    expect(await screen.findByRole("checkbox", { name: /Mostrar la señal/ })).not.toBeChecked();
    expect(screen.getByText("La persona ve solo la instrucción, sin la señal.")).toBeInTheDocument();
  });

  it("resume los ejercicios describiendo lo ocurrido, sin valorar a la persona", async () => {
    conductor({ ...practiceState, phase: "finished", step_index: null, practice: null, practice_results: [
      { step_index: 0, target_expression: "happiness", outcome: "achieved", seconds_to_achieve: 3.5, peak_level: 0.9, relative_to_calibration: true, feedback_visible: true },
      { step_index: 1, target_expression: "sadness", outcome: "timed_out", seconds_to_achieve: null, peak_level: 0.3, relative_to_calibration: true, feedback_visible: false },
    ] });
    expect(await screen.findByText("Logró la expresión pedida en 1 de 2 ejercicios.")).toBeInTheDocument();
    expect(screen.getByText(/Paso 1 · Alegría · Logró la expresión pedida a los 3[.,]5 s/)).toBeInTheDocument();
    expect(screen.getByText(/Paso 2 · Tristeza · Terminó el tiempo · sin la señal visible/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/fracas|falló|mal\b|bien hecho|excelente|diagn/i);
  });

  it("los pasos de imagen no muestran el interruptor", async () => {
    conductor({ ...practiceState, steps: [{ ...practiceStep, stimulus_id: "e1", title: "Paisaje", kind: "emotional", step_kind: "stimulus",
      target_expression: null, hold_seconds: null, capture_after_seconds: 2 }], practice: null });
    expect(await screen.findByText("Paisaje")).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: /Mostrar la señal/ })).not.toBeInTheDocument();
  });
});
