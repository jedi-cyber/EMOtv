import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiRequest } from "../src/api/http";
import { AuthContext } from "../src/auth/AuthContext";
import { ProtectedRoute } from "../src/auth/ProtectedRoute";
import type { UserRole } from "../src/auth/types";
import { ParticipantsPage } from "../src/pages/ParticipantsPage";

const state = vi.hoisted(() => ({ participants: [] as unknown[] }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === "/participants" ? state.participants : [], loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn() }));

const notice = { kind: "child_notice", version: "2026-10-provisional", provisional: true, required: false, accepted: false,
  content: "# Aviso\n\nLos datos de menores son **más sensibles**." };

function withUser(role: UserRole, element: React.ReactNode, path = "/participants") {
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role, is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={[path]}>{element}</MemoryRouter>
  </AuthContext.Provider>);
}

beforeEach(() => {
  state.participants = [];
  vi.mocked(apiRequest).mockReset();
});

describe("participantes", () => {
  it("antes del primer niño muestra el aviso reforzado y lo envía con su versión", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path, options) => {
      if (path === "/commitment/child-notice") return notice as never;
      const body = JSON.parse(String(options?.body ?? "{}"));
      if (path === "/participants" && !body.child_notice_version) throw new ApiError(428, "Lee y acepta el aviso");
      return { id: "p1", code: "P-ABC234", kind: "child" } as never;
    });
    withUser("student", <ParticipantsPage />);
    expect(document.body.textContent).not.toMatch(/estudiante/i);
    await userEvent.selectOptions(screen.getByLabelText("Tipo de participante"), "child");
    await userEvent.click(screen.getByRole("button", { name: "Registrar participante" }));
    expect(await screen.findByRole("dialog", { name: "Antes de registrar a un niño o una niña" })).toBeInTheDocument();
    expect(screen.getByText("más sensibles")).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: "Entendido, registrar" });
    expect(confirm).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(confirm);
    await waitFor(() => expect(apiRequest).toHaveBeenLastCalledWith("/participants", expect.objectContaining({
      body: JSON.stringify({ kind: "child", notes: null, child_notice_version: "2026-10-provisional" }),
    })));
    expect(await screen.findByText(/código P-ABC234/)).toBeInTheDocument();
  });

  it("el usuario solicita la eliminación y el docente la ejecuta", async () => {
    state.participants = [{ id: "p1", code: "P-ABC234", kind: "adult", created_at: "2026-10-01T00:00:00Z",
      expires_at: "2027-09-26T00:00:00Z", notes: null, registered_by_me: true, deletion_requested_at: null }];
    vi.mocked(apiRequest).mockResolvedValue({} as never);
    const view = withUser("student", <ParticipantsPage />);
    expect(screen.queryByRole("button", { name: "Eliminar" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Solicitar eliminación" }));
    expect(apiRequest).toHaveBeenCalledWith("/participants/p1/deletion-request", expect.objectContaining({ method: "POST" }));
    view.unmount();
    vi.mocked(apiRequest).mockResolvedValue({ id: "c1", participant_code: "P-ABC234", deleted_at: "2026-10-21T00:00:00Z", counts: { participants: 1 }, verified: true } as never);
    withUser("psychologist", <ParticipantsPage />);
    await userEvent.click(screen.getByRole("button", { name: "Eliminar" }));
    await userEvent.click(screen.getByRole("button", { name: "Eliminar definitivamente" }));
    expect(await screen.findByRole("link", { name: "Ver e imprimir el acta" })).toHaveAttribute("href", "/participants/deletions/c1");
  });

  it("sin el compromiso aceptado lleva a la página de aceptación", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ kind: "commitment", version: "v1", provisional: true, content: "", required: true, accepted: false } as never);
    withUser("psychologist", <Routes>
      <Route element={<ProtectedRoute />}>
        <Route path="/participants" element={<p>Participantes</p>} />
        <Route path="/commitment" element={<p>Página del compromiso</p>} />
      </Route>
    </Routes>);
    expect(await screen.findByText("Página del compromiso")).toBeInTheDocument();
  });
});
