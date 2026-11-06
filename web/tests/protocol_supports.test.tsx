import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiBlob, apiRequest } from "../src/api/http";
import type { GuidedState, ParticipantViewState } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { GuidedConductorPage } from "../src/pages/GuidedConductorPage";
import { ParticipantViewPage } from "../src/pages/ParticipantViewPage";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";

// Bloque 2b: apoyos configurables por protocolo; «Modo accesible» es un preajuste.
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
      <Route path="/participant-view/:token" element={element} />
    </Routes></MemoryRouter>
  </AuthContext.Provider>);
}

function speech() {
  const speak = vi.fn();
  class Utterance { text: string; lang = ""; rate = 1; voice: unknown = null; constructor(text: string) { this.text = text; } }
  Object.defineProperty(window, "speechSynthesis", { configurable: true, value: { speak, cancel: vi.fn(), getVoices: () => [] } });
  Object.defineProperty(window, "SpeechSynthesisUtterance", { configurable: true, value: Utterance });
  return speak;
}

beforeEach(() => { data.value = {}; vi.mocked(apiRequest).mockReset(); vi.mocked(apiBlob).mockReset(); });
afterEach(() => {
  Reflect.deleteProperty(window, "speechSynthesis");
  Reflect.deleteProperty(window, "SpeechSynthesisUtterance");
});

describe("apoyos en el editor", () => {
  async function newProtocol() {
    data.value["/stimuli"] = [
      { id: "sad", title: "Niño triste", kind: "emotional", expected_expression: "sadness", intensity: "mild", audience: "children", scope: "group", approved: true, active: true, category: "Dibujo", min_age: 1 },
    ];
    withUser(<ProtocolsPage />);
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
    await userEvent.click(screen.getByRole("radio", { name: /Para niños/ }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Con apoyos");
    await userEvent.selectOptions(screen.getByLabelText("Imagen"), "sad");
    await userEvent.click(screen.getByRole("button", { name: "Agregar como «¿Qué emoción es?»" }));
  }
  async function saved() {
    vi.mocked(apiRequest).mockResolvedValue({ id: "p1", version: 1 } as never);
    await userEvent.click(screen.getByRole("button", { name: "Guardar protocolo" }));
    const [, init] = vi.mocked(apiRequest).mock.calls.find(([path]) => path === "/protocols")!;
    return JSON.parse(String(init?.body));
  }

  it("cada apoyo se elige por separado y se guarda con el protocolo", async () => {
    await newProtocol();
    const supports = screen.getByRole("group", { name: "Apoyos uno por uno" });
    await userEvent.click(within(supports).getByRole("checkbox", { name: /Leer la consigna en voz alta/ }));
    await userEvent.click(within(supports).getByRole("checkbox", { name: /Sin límite de tiempo/ }));
    await userEvent.selectOptions(within(supports).getByLabelText("Pausa tras cada paso"), "wait");
    expect(screen.getByRole("checkbox", { name: "Modo accesible" })).not.toBeChecked();
    const body = await saved();
    expect(body.supports).toEqual({ pictograms: false, large_controls: false, read_aloud: true, no_time_limit: true, pause: "wait" });
    expect(body.accessible).toBe(true);
  });

  it("«Modo accesible» marca el preajuste de siempre y se puede ajustar después", async () => {
    await newProtocol();
    await userEvent.click(screen.getByRole("checkbox", { name: "Modo accesible" }));
    const supports = screen.getByRole("group", { name: "Apoyos uno por uno" });
    expect(within(supports).getByRole("checkbox", { name: "Pictogramas junto a cada emoción" })).toBeChecked();
    expect(within(supports).getByRole("checkbox", { name: /Botones y letra grandes/ })).toBeChecked();
    expect(within(supports).getByLabelText("Pausa tras cada paso")).toHaveValue("long");
    await userEvent.click(within(supports).getByRole("checkbox", { name: /Leer la consigna en voz alta/ }));
    const body = await saved();
    expect(body.supports).toEqual({ pictograms: true, large_controls: true, read_aloud: true, no_time_limit: false, pause: "long" });
  });

  it("sin apoyos, el protocolo no es accesible", async () => {
    await newProtocol();
    const body = await saved();
    expect(body.accessible).toBe(false);
    expect(body.supports.pause).toBe("normal");
  });
});

describe("apoyos en la pantalla de la persona", () => {
  const view: ParticipantViewState = {
    phase: "stimuli", message: null, stimulus: { exposure: "0-1" }, remaining_seconds: null, capture_frames: false,
    frame_interval_ms: 500, abstract_notice: null,
    recognition: { question: "¿Qué emoción es?", chosen: null, message: null,
      options: [{ key: "sadness", label: "Tristeza" }, { key: "happiness", label: "Alegría" }] },
  };
  function participant(state: ParticipantViewState) {
    vi.mocked(apiBlob).mockResolvedValue(new Blob(["png"], { type: "image/png" }));
    URL.createObjectURL = vi.fn(() => "blob:imagen");
    URL.revokeObjectURL = vi.fn();
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/participant-view/tok" ? state : { received: true }) as never);
    return withUser(<ParticipantViewPage />, "/participant-view/tok");
  }

  it("pictogramas sin botones grandes: cada apoyo por separado", async () => {
    const { container } = participant({ ...view, supports: { pictograms: true, large_controls: false, read_aloud: false } });
    expect(await screen.findByRole("button", { name: "Tristeza" })).toHaveTextContent("😢");
    expect(container.querySelector("main")).not.toHaveClass("participant-view--accessible");
  });

  it("botones grandes sin pictogramas", async () => {
    const { container } = participant({ ...view, supports: { pictograms: false, large_controls: true, read_aloud: false } });
    expect(await screen.findByRole("button", { name: "Tristeza" })).not.toHaveTextContent("😢");
    expect(container.querySelector("main")).toHaveClass("participant-view--accessible");
  });

  it("con lectura en voz alta, la consigna se lee al empezar el paso, sin pulsar nada", async () => {
    const speak = speech();
    participant({ ...view, supports: { pictograms: false, large_controls: false, read_aloud: true } });
    await screen.findByRole("button", { name: "Tristeza" });
    expect(speak).toHaveBeenCalled();
    expect(speak.mock.calls[0][0].text).toBe("¿Qué emoción es?");
  });

  it("sin lectura en voz alta no se lee nada por sí solo", async () => {
    const speak = speech();
    participant(view);
    await screen.findByRole("button", { name: "Tristeza" });
    expect(speak).not.toHaveBeenCalled();
  });
});

describe("apoyos en la vista de quien conduce", () => {
  const state: GuidedState = {
    session_id: "s1", session_code: "S-4F7K2Q", phase: "stimuli", audience: "propia", has_protocol: true, stop_reason: null,
    step_index: 0, step_count: 2, remaining_seconds: null, steps_log: [],
    steps: [{ index: 0, stimulus_id: "sad", title: "Niño triste", kind: "emotional", exposure_seconds: 15, capture_after_seconds: 0,
      record_verbal_response: false, shown_before_analyzer: false, step_kind: "recognition", target_expression: "sadness",
      hold_seconds: null, option_count: 2 }],
    calibration: { state: "none", progress: 0, notice: null }, capture_status: [], pre_questionnaire_id: null,
    post_questionnaire_id: null, abstract_notice: null, captures: [], markers: [], verbal_responses: [],
    recognition: { target_expression: "sadness", situation: null, options: ["sadness", "happiness"], chosen_expression: "sadness", outcome: "answered" },
    recognition_results: [], accessible: true, waiting_for_conductor: true,
    supports: { pictograms: false, large_controls: false, read_aloud: false, no_time_limit: true, pause: "wait" },
  };

  it("sin límite de tiempo no hay cuenta regresiva y «Seguir» pasa al paso siguiente", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? state : {}) as never);
    withUser(<GuidedConductorPage />, "/guided/s1");
    expect(await screen.findByText("Sin límite de tiempo")).toBeInTheDocument();
    expect(screen.queryByRole("timer")).not.toBeInTheDocument();
    expect(screen.getByText(/apoyos: sin límite de tiempo, espera «Seguir»/)).toBeInTheDocument();
    expect(screen.getByText(/Eligió Tristeza. Pulsa «Seguir» cuando quieras pasar al siguiente./)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Seguir" }));
    expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/continue", expect.objectContaining({ method: "POST" }));
  });

  it("sin la pausa «esperar» no se ofrece «Seguir»", async () => {
    const plain = { ...state, waiting_for_conductor: false, remaining_seconds: 4, supports: null, accessible: false };
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? plain : {}) as never);
    withUser(<GuidedConductorPage />, "/guided/s1");
    expect(await screen.findByRole("timer")).toHaveTextContent("4 s");
    expect(screen.queryByRole("button", { name: "Seguir" })).not.toBeInTheDocument();
  });
});
