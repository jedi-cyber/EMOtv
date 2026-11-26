import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiBlob, apiRequest } from "../src/api/http";
import type { ParticipantPractice, ParticipantViewState, ProtocolStep } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { ParticipantViewPage } from "../src/pages/ParticipantViewPage";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";
import { cameraGameSteps, cameraGameTargets, itemRange, moveItem, removeItem } from "../src/stimuli/cameraGame";

// Juego con cámara «Muestra la emoción»: rondas, estrellas y «Lograste X de Y caras», sin puntos.
const data = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === null ? null : data.value[path] ?? [], loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(), apiBlob: vi.fn(),
}));

beforeEach(() => { data.value = {}; vi.mocked(apiRequest).mockReset(); vi.mocked(apiBlob).mockReset(); });

const drawing: ProtocolStep = { kind: "drawing", stimulus_id: null, exposure_seconds: 60, capture_after_seconds: 0,
  record_verbal_response: false, shown_before_analyzer: false };

describe("bloque del juego en el editor", () => {
  it("elige emociones de las cinco, sin repetir la de la ronda anterior", () => {
    const targets = cameraGameTargets(6, () => 0);
    expect(targets).toHaveLength(6);
    targets.slice(1).forEach((target, index) => expect(target).not.toBe(targets[index]));
    expect(cameraGameSteps(3).map((step) => step.game_round)).toEqual([1, 2, 3]);
  });

  it("se mueve y se quita entero, sin partir sus rondas", () => {
    const steps = [drawing, ...cameraGameSteps(3), { ...drawing, exposure_seconds: 30 }];
    expect(itemRange(steps, 2)).toEqual([1, 4]);
    const up = moveItem(steps, 2, -1);
    expect(up.map((step) => step.game_round ?? null)).toEqual([1, 2, 3, null, null]);
    const down = moveItem(steps, 1, 1);
    expect(down.map((step) => step.game_round ?? null)).toEqual([null, null, 1, 2, 3]);
    expect(down[1].exposure_seconds).toBe(30);
    expect(removeItem(steps, 3)).toEqual([drawing, steps[4]]);
  });

  it("se agrega desde el catálogo y se guarda como rondas seguidas", async () => {
    render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
      <MemoryRouter><ProtocolsPage /></MemoryRouter>
    </AuthContext.Provider>);
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
    await userEvent.click(screen.getByRole("radio", { name: /Para niños/ }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Juego");
    await userEvent.click(screen.getByRole("button", { name: "Juego con cámara: muestra la emoción" }));
    expect(screen.getByText(/1–5\. Juego con cámara/)).toBeInTheDocument();
    expect(document.body.textContent).toMatch(/Sin puntos/);
    await userEvent.selectOptions(screen.getByLabelText("Rondas"), "3");
    expect(screen.getByText(/1–3\. Juego con cámara/)).toBeInTheDocument();
    vi.mocked(apiRequest).mockResolvedValue({ id: "p1", version: 1 } as never);
    await userEvent.click(screen.getByRole("button", { name: "Guardar protocolo" }));
    const [, init] = vi.mocked(apiRequest).mock.calls.find(([path]) => path === "/protocols")!;
    const body = JSON.parse(String(init?.body));
    expect(body.steps.map((step: ProtocolStep) => [step.kind, step.game_round, step.stimulus_id])).toEqual([
      ["practice", 1, null], ["practice", 2, null], ["practice", 3, null]]);
  });
});

describe("estrellas en la pantalla de la persona", () => {
  const practice: ParticipantPractice = {
    instruction: "Muestra alegría", level: 0.4, achieved: false, message: null, frame_interval_ms: 500,
    camera_game: { round: 3, rounds: 3, stars: [true, false, null], summary: null },
  };
  const base: ParticipantViewState = {
    phase: "stimuli", message: null, stimulus: null, remaining_seconds: 12, capture_frames: false,
    frame_interval_ms: 500, abstract_notice: null, practice,
  };
  function participant(view: ParticipantViewState) {
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/participant-view/tok" ? view : { stopped: true }) as never);
    return render(<MemoryRouter initialEntries={["/participant-view/tok"]}>
      <Routes><Route path="/participant-view/:token" element={<ParticipantViewPage />} /></Routes>
    </MemoryRouter>);
  }

  it("muestra la ronda y una estrella por cara lograda, sin puntos", async () => {
    participant(base);
    expect(await screen.findByText("Ronda 3 de 3")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "1 cara lograda de 3" })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/punto|puntaje/i);
  });

  it("al terminar la última ronda dice cuántas caras logró", async () => {
    participant({ ...base, practice: { ...practice, achieved: true, message: "¡Lo lograste!",
      camera_game: { round: 3, rounds: 3, stars: [true, false, true], summary: "Lograste 2 de 3 caras." } } });
    expect(await screen.findByRole("status")).toHaveTextContent("Lograste 2 de 3 caras.");
    expect(screen.getByRole("img", { name: "2 caras logradas de 3" })).toBeInTheDocument();
  });
});
