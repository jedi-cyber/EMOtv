import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiBlob, apiRequest } from "../src/api/http";
import { AuthContext } from "../src/auth/AuthContext";
import { AdminModelsPage } from "../src/pages/AdminModelsPage";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";

const data = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === null ? null : data.value[path] ?? [], loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(), apiBlob: vi.fn(),
}));

function withUser(element: React.ReactNode, role: "student" | "superadmin" = "student") {
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role, is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter>{element}</MemoryRouter>
  </AuthContext.Provider>);
}

const ADD = "Agregar «Validación con adultos»";

beforeEach(() => {
  data.value = {};
  vi.mocked(apiRequest).mockReset().mockResolvedValue({} as never);
  vi.mocked(apiBlob).mockReset();
});
afterEach(() => { vi.restoreAllMocks(); });

describe("protocolo «Validación con adultos»", () => {
  it("una cuenta de voluntario en modo demo lo agrega con un botón", async () => {
    data.value["/practice-validation/protocol"] = { available: true, protocol_id: null };
    withUser(<ProtocolsPage />);
    expect(screen.getByText(/No se guardan imágenes/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: ADD }));
    expect(apiRequest).toHaveBeenCalledWith("/practice-validation/protocol", expect.objectContaining({ method: "POST" }));
    expect(await screen.findByText(/Se agregó el protocolo «Validación con adultos»/)).toBeInTheDocument();
  });

  it.each([
    ["sin cuenta de voluntario o fuera de demo", { available: false, protocol_id: null }],
    ["cuando ya lo tiene", { available: true, protocol_id: "p1" }],
  ])("no se ofrece %s", (_, status) => {
    data.value["/practice-validation/protocol"] = status;
    withUser(<ProtocolsPage />);
    expect(screen.queryByRole("button", { name: ADD })).not.toBeInTheDocument();
  });
});

describe("exportación agregada de la validación", () => {
  it("administración descarga el resumen CSV", async () => {
    data.value["/admin/models"] = { default_model_id: "ferplus_onnx", changed_by: null, changed_at: null,
      fallback_model_id: null, fallback_at: null, models: [] };
    vi.mocked(apiBlob).mockResolvedValue(new Blob(["modelo\n"], { type: "text/csv" }));
    const createUrl = vi.fn(() => "blob:resumen");
    Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: vi.fn() });
    const click = vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => undefined);
    const view = withUser(<AdminModelsPage />, "superadmin");
    expect(view.container.textContent).toMatch(/No incluye códigos de sesión/);
    await userEvent.click(screen.getByRole("button", { name: "Descargar resumen (CSV)" }));
    expect(apiBlob).toHaveBeenCalledWith("/practice-validation/export.csv", "t");
    expect(createUrl).toHaveBeenCalled();
    expect(click).toHaveBeenCalled();
  });
});
