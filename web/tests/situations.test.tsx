import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiBlob, apiRequest } from "../src/api/http";
import type { GuidedState, ParticipantViewState } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { GuidedConductorPage } from "../src/pages/GuidedConductorPage";
import { ParticipantViewPage } from "../src/pages/ParticipantViewPage";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";

const data = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === null ? null : data.value[path] ?? [], loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(), apiBlob: vi.fn(),
}));

const STORY = "A Lucía se le cayó su helado al piso.";

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

describe("situaciones en el paso «¿Qué emoción es?»", () => {
  it("el editor agrega una historia corta al reconocimiento y la envía", async () => {
    data.value["/stimuli"] = [
      { id: "sad", title: "Niña con helado", kind: "emotional", expected_expression: "sadness", intensity: "mild", audience: "children", scope: "group", approved: true, active: true, category: "Dibujo", min_age: 1 },
    ];
    withUser(<ProtocolsPage />);
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
    await userEvent.click(screen.getByRole("radio", { name: /Para niños/ }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Situaciones");
    await userEvent.selectOptions(screen.getByLabelText("Imagen"), "sad");
    await userEvent.click(screen.getByRole("button", { name: "Agregar como «¿Qué emoción es?»" }));
    const field = screen.getByLabelText("Situación (opcional)");
    expect(field).toHaveAttribute("maxLength", "200");
    await userEvent.type(field, STORY);
    expect(screen.getByText(/1\. Situación Niña con helado/)).toBeInTheDocument();
    vi.mocked(apiRequest).mockResolvedValue({ id: "p1", version: 1 } as never);
    await userEvent.click(screen.getByRole("button", { name: "Guardar protocolo" }));
    const [, init] = vi.mocked(apiRequest).mock.calls.find(([path]) => path === "/protocols")!;
    expect(JSON.parse(String(init?.body)).steps[0]).toMatchObject({ kind: "recognition", stimulus_id: "sad", situation: STORY });
  });

  it("la persona lee la situación y la pregunta por la cara de la imagen", async () => {
    const view: ParticipantViewState = {
      phase: "stimuli", message: null, stimulus: { exposure: "0-1" }, remaining_seconds: 10, capture_frames: false,
      frame_interval_ms: 500, abstract_notice: null,
      recognition: { question: "¿Qué emoción muestra la cara?", situation: STORY, chosen: null, message: null,
        options: [{ key: "sadness", label: "Tristeza" }, { key: "happiness", label: "Alegría" }] },
    };
    vi.mocked(apiBlob).mockResolvedValue(new Blob(["png"], { type: "image/png" }));
    URL.createObjectURL = vi.fn(() => "blob:imagen");
    URL.revokeObjectURL = vi.fn();
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/participant-view/tok" ? view : { received: true }) as never);
    withUser(<ParticipantViewPage />, "/participant-view/tok");
    expect(await screen.findByText(STORY)).toBeInTheDocument();
    expect(screen.getByText("¿Qué emoción muestra la cara?")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Tristeza" }));
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/participant-view/tok/answer",
      expect.objectContaining({ body: JSON.stringify({ expression: "sadness" }) })));
  });

  it("quien conduce ve la situación del paso", async () => {
    const state: GuidedState = {
      session_id: "s1", session_code: "S-4F7K2Q", phase: "stimuli", audience: "infantil", has_protocol: true, stop_reason: null,
      step_index: 0, step_count: 1, remaining_seconds: 12, steps_log: [],
      steps: [{ index: 0, stimulus_id: "sad", title: "Niña con helado", kind: "emotional", exposure_seconds: 15, capture_after_seconds: 0,
        record_verbal_response: false, shown_before_analyzer: false, step_kind: "recognition", target_expression: "sadness",
        hold_seconds: null, option_count: 2 }],
      calibration: { state: "calibrated", progress: 1, notice: null }, capture_status: [], pre_questionnaire_id: null,
      post_questionnaire_id: null, abstract_notice: null, captures: [], markers: [], verbal_responses: [],
      recognition: { target_expression: "sadness", situation: STORY, options: ["sadness", "happiness"], chosen_expression: null, outcome: null },
      recognition_results: [],
    };
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? state : {}) as never);
    withUser(<GuidedConductorPage />, "/guided/s1");
    expect(await screen.findByRole("heading", { name: "¿Qué emoción muestra la cara? · Niña con helado" })).toBeInTheDocument();
    expect(screen.getByText(`Situación: ${STORY}`)).toBeInTheDocument();
  });
});
