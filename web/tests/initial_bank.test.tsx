import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../src/api/http";
import type { Stimulus } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import type { UserRole } from "../src/auth/types";
import { INITIAL_BANK_CATEGORY, StimuliPage } from "../src/pages/StimuliPage";

const data = vi.hoisted(() => ({ stimuli: [] as unknown[] }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: () => ({ data: data.stimuli, loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(),
}));
vi.mock("../src/components/StimulusImage", () => ({ StimulusImage: () => null }));

const drawing: Stimulus = {
  id: "s1", title: "Alegría 1", kind: "emotional", category: INITIAL_BANK_CATEGORY, expected_expression: "happiness",
  intensity: "mild", min_age: 3, origin: "Creación propia", license: "Uso libre", scope: "institution",
  audience: "children", created_at: "2026-11-04T10:00:00Z", approved: true, active: true, can_manage: true,
};

function page(role: UserRole, stimuli: Stimulus[]) {
  data.stimuli = stimuli;
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role, is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter><StimuliPage /></MemoryRouter>
  </AuthContext.Provider>);
}

beforeEach(() => { vi.mocked(apiRequest).mockReset(); });

describe("banco inicial de dibujos", () => {
  it("el administrador lo agrega mientras no esté en el banco", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ added: 18, total: 18 } as never);
    page("admin", []);
    await userEvent.click(screen.getByRole("button", { name: "Agregar el banco inicial" }));
    expect(apiRequest).toHaveBeenCalledWith("/stimuli/initial-bank", expect.objectContaining({ method: "POST" }));
    expect(await screen.findByText(/Se agregaron 18 dibujos del banco inicial/)).toBeInTheDocument();
  });

  it("no se ofrece si ya está o si no es el administrador", () => {
    page("admin", [drawing]);
    expect(screen.queryByRole("button", { name: "Agregar el banco inicial" })).not.toBeInTheDocument();
    page("psychologist", []);
    expect(screen.queryByRole("button", { name: "Agregar el banco inicial" })).not.toBeInTheDocument();
  });
});
