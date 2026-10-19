import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdminModelsPage, type LocalModelSettings } from "../src/pages/AdminModelsPage";
import { AuthContext } from "../src/auth/AuthContext";
import { ApiError, apiRequest } from "../src/api/http";
import { navigationByRole } from "../src/routes/navigation";

const state = vi.hoisted(() => ({ settings: null as LocalModelSettings | null, reload: vi.fn() }));

vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: () => ({ data: state.settings, loading: false, error: "", reload: state.reload }),
}));
vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn() }));

function settings(overrides: Partial<LocalModelSettings> = {}): LocalModelSettings {
  return {
    default_model_id: "hsemotion_enet_b0_8_best_afew", changed_by: null, changed_at: null,
    fallback_model_id: null, fallback_at: null,
    models: [
      { model_id: "hsemotion_enet_b0_8_best_afew", name: "HSEmotion", version: "af833487321c3efd", state: "SUPPORTED", reasons: [],
        checks: { weights_verified: true, benchmark_current: true }, p95_ms: 42.4,
        concurrent_frame_p95_ms: { "4": 310.4, "1": 95.2, "2": 160 }, is_default: true },
      { model_id: "ferplus_onnx", name: "FER+", version: "1.0", state: "BLOCKED", reasons: ["Benchmark vencido o con fecha futura; repite la medición"],
        checks: { weights_verified: true, benchmark_current: false }, p95_ms: null, concurrent_frame_p95_ms: null, is_default: false },
    ],
    ...overrides,
  };
}

function page() {
  return render(<AuthContext.Provider value={{ user: { id: "a", email: "superadmin@example.com", role: "admin", is_active: true }, token: "token", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter><AdminModelsPage /></MemoryRouter>
  </AuthContext.Provider>);
}

beforeEach(() => {
  state.settings = settings();
  state.reload.mockReset();
  vi.mocked(apiRequest).mockReset().mockResolvedValue({} as never);
});

describe("página Modelos", () => {
  it("solo administración la tiene en su navegación", () => {
    expect(navigationByRole.admin.some((item) => item.to === "/admin/models")).toBe(true);
    expect(navigationByRole.student.some((item) => item.to === "/admin/models")).toBe(false);
    expect(navigationByRole.psychologist.some((item) => item.to === "/admin/models")).toBe(false);
  });

  it("muestra el estado real de cada modelo y no permite elegir uno sin admisión", () => {
    const view = page();
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[0]).getByText("Predeterminado")).toBeInTheDocument();
    expect(within(rows[0]).getByText("42 ms")).toBeInTheDocument();
    // p95 del cuadro completo con varias sesiones, ordenado por número de sesiones.
    expect(within(rows[0]).getByText("Cuadro completo: 1 sesión: 95 ms · 2 sesiones: 160 ms · 4 sesiones: 310 ms")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Sin admisión vigente")).toBeInTheDocument();
    expect(within(rows[1]).getByText(/Benchmark vencido/)).toBeInTheDocument();
    expect(within(rows[1]).getByRole("button", { name: "Usar FER+ como predeterminado" })).toBeDisabled();
    expect(screen.getByText("Rige el modelo predeterminado inicial; nadie lo ha cambiado todavía.")).toBeInTheDocument();
    expect(view.container.textContent).not.toMatch(/precis|exact|mejor/i);
  });

  it("cambia el predeterminado y muestra quién y cuándo lo cambió", async () => {
    state.settings = settings({
      models: settings().models.map((model) => ({ ...model, state: "SUPPORTED", reasons: [] })),
      changed_by: "superadmin@example.com", changed_at: "2026-10-19T15:00:00Z",
    });
    page();
    expect(screen.getByText(/Último cambio: superadmin@example.com/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Usar FER+ como predeterminado" }));
    expect(apiRequest).toHaveBeenCalledWith("/admin/models/default", expect.objectContaining({
      method: "PUT", body: JSON.stringify({ model_id: "ferplus_onnx" }),
    }));
    expect(await screen.findByText(/FER\+ es ahora el modelo predeterminado/)).toBeInTheDocument();
    expect(state.reload).toHaveBeenCalled();
  });

  it("informa el rechazo del servidor y el uso del respaldo", async () => {
    state.settings = settings({ fallback_model_id: "ferplus_onnx", fallback_at: "2026-10-19T15:00:00Z",
      models: settings().models.map((model) => ({ ...model, state: "SUPPORTED" })) });
    vi.mocked(apiRequest).mockRejectedValueOnce(new ApiError(409, "Modelo sin admisión vigente: Benchmark vencido"));
    page();
    expect(screen.getByText(/se usó FER\+ como respaldo/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Usar FER+ como predeterminado" }));
    expect(await screen.findByText("Modelo sin admisión vigente: Benchmark vencido")).toBeInTheDocument();
  });
});
