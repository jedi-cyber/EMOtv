import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiBlob, apiRequest } from "../src/api/http";
import type { ParticipantViewState } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { ParticipantViewPage } from "../src/pages/ParticipantViewPage";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";

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
      <Route path="/participant-view/:token" element={element} />
    </Routes></MemoryRouter>
  </AuthContext.Provider>);
}

beforeEach(() => { data.value = {}; vi.mocked(apiRequest).mockReset(); vi.mocked(apiBlob).mockReset(); });

describe("modo accesible", () => {
  it("el editor lo guarda y propone 2 opciones y 30 s en un reconocimiento nuevo", async () => {
    data.value["/stimuli"] = [
      { id: "sad", title: "Niño triste", kind: "emotional", expected_expression: "sadness", intensity: "mild", audience: "children", scope: "group", approved: true, active: true, category: "Dibujo", min_age: 1 },
    ];
    withUser(<ProtocolsPage />);
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
    await userEvent.click(screen.getByRole("radio", { name: /Para niños/ }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Modo accesible" }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Emociones con apoyo");
    await userEvent.selectOptions(screen.getByLabelText("Imagen"), "sad");
    await userEvent.click(screen.getByRole("button", { name: "Agregar como «¿Qué emoción es?»" }));
    vi.mocked(apiRequest).mockResolvedValue({ id: "p1", version: 1 } as never);
    await userEvent.click(screen.getByRole("button", { name: "Guardar protocolo" }));
    const [, init] = vi.mocked(apiRequest).mock.calls.find(([path]) => path === "/protocols")!;
    const body = JSON.parse(String(init?.body));
    expect(body.accessible).toBe(true);
    expect(body.steps[0]).toMatchObject({ kind: "recognition", option_count: 2, exposure_seconds: 30 });
  });

  const view: ParticipantViewState = {
    phase: "stimuli", message: null, stimulus: { exposure: "0-1" }, remaining_seconds: 10, capture_frames: false,
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

  it("la persona ve un pictograma junto a cada emoción; el nombre sigue siendo la etiqueta", async () => {
    const { container } = participant({ ...view, accessible: true });
    const button = await screen.findByRole("button", { name: "Tristeza" });
    expect(button).toHaveTextContent("😢");
    expect(container.querySelector("main")).toHaveClass("participant-view--accessible");
  });

  it("sin modo accesible no hay pictogramas", async () => {
    const { container } = participant(view);
    expect(await screen.findByRole("button", { name: "Tristeza" })).not.toHaveTextContent("😢");
    expect(container.querySelector("main")).not.toHaveClass("participant-view--accessible");
  });
});
