import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiBlob, apiRequest } from "../src/api/http";
import type { GuidedState, ParticipantViewState, ProtocolStep } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { GuidedConductorPage } from "../src/pages/GuidedConductorPage";
import { ParticipantViewPage } from "../src/pages/ParticipantViewPage";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";

// «Juego: imita la cara» (valora quien conduce), dibujo con imagen e imágenes elegidas en «Empareja la emoción».
const data = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === null ? null : data.value[path] ?? [], loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(), apiBlob: vi.fn(),
}));

const stimuli = [
  { id: "happy", title: "Foto alegre", kind: "emotional", expected_expression: "happiness", intensity: "mild", audience: "children", scope: "group", approved: true, active: true, category: "Foto", min_age: 1 },
  { id: "sad", title: "Foto triste", kind: "emotional", expected_expression: "sadness", intensity: "mild", audience: "children", scope: "group", approved: true, active: true, category: "Foto", min_age: 1 },
];

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

async function newProtocol() {
  data.value["/stimuli"] = stimuli;
  withUser(<ProtocolsPage />);
  await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
  await userEvent.click(screen.getByRole("radio", { name: /Para niños/ }));
  await userEvent.type(screen.getByLabelText("Nombre"), "Juegos");
}

async function saved() {
  vi.mocked(apiRequest).mockResolvedValue({ id: "p1", version: 1 } as never);
  await userEvent.click(screen.getByRole("button", { name: "Guardar protocolo" }));
  const [, init] = vi.mocked(apiRequest).mock.calls.find(([path]) => path === "/protocols")!;
  return JSON.parse(String(init?.body)).steps as ProtocolStep[];
}

describe("en el editor", () => {
  it("«Juego: imita la cara» es una imitación que valora quien conduce", async () => {
    await newProtocol();
    await userEvent.click(screen.getByRole("button", { name: "Juego: imita la cara" }));
    await userEvent.selectOptions(screen.getByLabelText(/^Imagen para/), "happy");
    await userEvent.click(screen.getByRole("button", { name: "Agregar paso" }));
    expect(screen.getByText(/1\. Juego: imita la cara: Foto alegre/)).toBeInTheDocument();
    expect(screen.getByText(/el paso espera tu valoración/)).toBeInTheDocument();
    const [step] = await saved();
    expect(step).toMatchObject({ kind: "practice", imitate: true, conductor_rating: true, stimulus_id: "happy" });
  });

  it("el dibujo puede llevar una imagen para mirar", async () => {
    await newProtocol();
    await userEvent.click(screen.getByRole("button", { name: "Dibujo" }));
    await userEvent.selectOptions(screen.getByLabelText("Imagen para mirar (opcional)"), "sad");
    expect(screen.getByText(/la emoción que siente al ver «Foto triste»/)).toBeInTheDocument();
    const [step] = await saved();
    expect(step).toMatchObject({ kind: "drawing", stimulus_id: "sad" });
  });

  it("en «Empareja la emoción» se elige la imagen de cada ronda; las demás las completa EMOtv", async () => {
    await newProtocol();
    await userEvent.click(screen.getByRole("button", { name: "Juego: empareja la emoción" }));
    await userEvent.selectOptions(screen.getByLabelText("Imagen de la ronda 2"), "sad");
    expect(screen.getByLabelText("Imagen de la ronda 1")).toHaveValue("");
    const [step] = await saved();
    expect(step.game_stimulus_ids).toEqual(["sad"]);
  });
});

const rated = { index: 0, stimulus_id: "happy", title: "Foto alegre", kind: "emotional" as const, exposure_seconds: 20, capture_after_seconds: 0,
  record_verbal_response: false, shown_before_analyzer: false, step_kind: "practice" as const, target_expression: "happiness",
  hold_seconds: 2, imitate: true, conductor_rating: true };
const ratedState: GuidedState = {
  session_id: "s1", session_code: "S-4F7K2Q", phase: "stimuli", audience: "infantil", has_protocol: true, stop_reason: null,
  step_index: 0, step_count: 1, steps: [rated], remaining_seconds: 0, steps_log: [],
  calibration: { state: "idle", progress: 0, notice: null }, capture_status: [], pre_questionnaire_id: null,
  post_questionnaire_id: null, abstract_notice: null, captures: [], markers: [], verbal_responses: [],
  practice_feedback: true, practice: { target_expression: "happiness", hold_seconds: 2, imitate: true, level: 1, achieved: true,
    rating: { stars: null, can_rate: true } }, practice_results: [],
} as GuidedState;

describe("quien conduce valora", () => {
  it("marca de 1 a 5 estrellas al terminar la imitación", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? ratedState : {}) as never);
    withUser(<GuidedConductorPage />, "/guided/s1");
    expect(await screen.findByRole("heading", { name: "Imita la cara: Alegría" })).toBeInTheDocument();
    expect(screen.getByText("Tu valoración de la imitación (la persona no la ve)")).toBeInTheDocument();
    expect(screen.getByText("Marca de 1 a 5 estrellas para seguir con el paso siguiente.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "4 estrellas" }));
    expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/rating", expect.objectContaining({ body: JSON.stringify({ stars: 4 }) }));
  });

  it("no deja valorar mientras la persona imita", async () => {
    const running = { ...ratedState, practice: { ...ratedState.practice!, achieved: false, level: 0.3, rating: { stars: null, can_rate: false } } };
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/guided-sessions/s1" ? running : {}) as never);
    withUser(<GuidedConductorPage />, "/guided/s1");
    expect(await screen.findByRole("button", { name: "3 estrellas" })).toBeDisabled();
    expect(screen.getByText("Podrás valorar cuando termine la imitación.")).toBeInTheDocument();
  });
});

describe("dibujo con imagen en la pantalla de la persona", () => {
  it("muestra la imagen junto al lienzo", async () => {
    vi.mocked(apiBlob).mockResolvedValue(new Blob(["png"], { type: "image/png" }));
    URL.createObjectURL = vi.fn(() => "blob:imagen");
    URL.revokeObjectURL = vi.fn();
    const view: ParticipantViewState = {
      phase: "stimuli", message: null, stimulus: { exposure: "0-1" }, remaining_seconds: 30, capture_frames: false,
      frame_interval_ms: 500, abstract_notice: null, practice: null,
      drawing: { instruction: "Mira la imagen y dibuja una cara con la emoción que sientes.", question: "¿Qué emoción quisiste dibujar?",
        options: [{ key: "happiness", label: "Alegría" }], round: "0-1", finished: false, chosen: null, message: null },
    } as ParticipantViewState;
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/participant-view/tok" ? view : {}) as never);
    withUser(<ParticipantViewPage />, "/participant-view/tok");
    expect(await screen.findByRole("img", { name: "Imagen para mirar antes de dibujar" })).toHaveAttribute("src", "blob:imagen");
    expect(screen.getByText("Mira la imagen y dibuja una cara con la emoción que sientes.")).toBeInTheDocument();
  });
});
