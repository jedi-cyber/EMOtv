import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../src/api/http";
import type { Protocol } from "../src/api/types";
import type { UserRole } from "../src/auth/types";
import { AuthContext } from "../src/auth/AuthContext";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";

const data = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === null ? null : data.value[path] ?? [], loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(),
}));

const template: Protocol = {
  id: "p1", family_id: "p1", version: 1, name: "Emociones básicas 4 a 6 años", description: "", for_children: true,
  accessible: true, pre_questionnaire_id: null, post_questionnaire_id: null, steps: [], created_at: "2026-11-02T10:00:00Z",
  owned_by_me: false, shared_with_group: true, used: false, needs_image: false,
};

function page(role: UserRole, protocols: Protocol[]) {
  data.value["/protocols"] = protocols;
  vi.mocked(apiRequest).mockResolvedValue({} as never);
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role, is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter><ProtocolsPage /></MemoryRouter>
  </AuthContext.Provider>);
}

beforeEach(() => { data.value = {}; vi.mocked(apiRequest).mockReset(); });

describe("plantillas de protocolos", () => {
  it("el usuario ve la plantilla de su docente y la copia como protocolo propio", async () => {
    page("student", [template]);
    expect(screen.getByText("Plantilla de tu docente")).toBeInTheDocument();
    // Una plantilla no se edita ni se aplica sin copiarla.
    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Usar en el Analizador" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Compartir con mi grupo" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Copiar y modificar" }));
    expect(apiRequest).toHaveBeenCalledWith("/protocols/p1/copy", expect.objectContaining({ method: "POST" }));
    expect(await screen.findByText(/Se agregó una copia de «Emociones básicas 4 a 6 años»/)).toBeInTheDocument();
  });

  it("el docente comparte un protocolo suyo con su grupo y puede dejar de compartirlo", async () => {
    page("psychologist", [{ ...template, owned_by_me: true, shared_with_group: false }]);
    await userEvent.click(screen.getByRole("button", { name: "Compartir con mi grupo" }));
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/protocols/p1/share",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ shared: true }) })));
    expect(await screen.findByText("Tu grupo puede copiar este protocolo como plantilla.")).toBeInTheDocument();
  });

  it("el docente ve cuáles comparte y no copia los de los usuarios de su grupo", () => {
    page("psychologist", [{ ...template, owned_by_me: true }, { ...template, id: "p2", name: "De un usuario", shared_with_group: false }]);
    expect(screen.getByText("Compartido con tu grupo")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dejar de compartir" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /Duplicar|Copiar y modificar/ })).toHaveLength(1);
  });
});
