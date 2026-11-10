import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../src/api/http";
import type { SessionPractice } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { PracticeMetrics } from "../src/insights/StimulusMetrics";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";

const data = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === null ? null : data.value[path] ?? [], loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(),
}));

function withUser(element: React.ReactNode) {
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter>{element}</MemoryRouter>
  </AuthContext.Provider>);
}

beforeEach(() => { data.value = {}; vi.mocked(apiRequest).mockReset(); });

describe("Haz la misma cara", () => {
  it("el editor agrega la imagen como modelo y toma de ella la expresión pedida", async () => {
    data.value["/stimuli"] = [
      { id: "happy", title: "Cara alegre", kind: "emotional", expected_expression: "happiness", intensity: "mild", audience: "children", scope: "institution", approved: true, active: true, category: "Banco inicial EMOtv", min_age: 3 },
    ];
    withUser(<ProtocolsPage />);
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
    await userEvent.click(screen.getByRole("radio", { name: /Para niños/ }));
    await userEvent.type(screen.getByLabelText("Nombre"), "Imitar caras");
    expect(screen.getByRole("button", { name: "Agregar como «Haz la misma cara»" })).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Imagen"), "happy");
    await userEvent.click(screen.getByRole("button", { name: "Agregar como «Haz la misma cara»" }));
    expect(screen.getByText("1. Haz la misma cara: Cara alegre")).toBeInTheDocument();
    expect(screen.getByText(/Expresión pedida: Alegría \(la expresión esperada de la imagen\)/)).toBeInTheDocument();
    // No se elige la expresión: la pone la imagen.
    expect(screen.queryByLabelText("Expresión pedida")).not.toBeInTheDocument();
    vi.mocked(apiRequest).mockResolvedValue({ id: "p1", version: 1 } as never);
    await userEvent.click(screen.getByRole("button", { name: "Guardar protocolo" }));
    const [, init] = vi.mocked(apiRequest).mock.calls.find(([path]) => path === "/protocols")!;
    expect(JSON.parse(String(init?.body)).steps[0]).toMatchObject({
      kind: "practice", stimulus_id: "happy", imitate: true, target_expression: "happiness" });
  });

  it("las métricas dicen que el ejercicio imitó un modelo, sin valorar", () => {
    const practice: SessionPractice = {
      exercises: [{ step_index: 0, target_expression: "happiness", hold_seconds: 2, max_seconds: 20, imitate: true,
        outcome: "achieved", seconds_to_achieve: 3, peak_level: 0.9, relative_to_calibration: true, feedback_visible: true }],
      totals: { sentence: "Logró la expresión pedida en 1 de 1 ejercicio.", feedback_sentence: null, achieved: 1, not_achieved: 0,
        skipped: 0, stopped: 0, average_seconds_to_achieve: 3, exercises: 1, not_reached: 0 } as never,
      by_target: [], notice: "Aviso",
    };
    render(<PracticeMetrics practice={practice} />);
    expect(screen.getByText("Alegría (imitando un modelo)")).toBeInTheDocument();
  });
});
