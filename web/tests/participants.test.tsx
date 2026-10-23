import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiRequest } from "../src/api/http";
import { AuthContext } from "../src/auth/AuthContext";
import { ProtectedRoute } from "../src/auth/ProtectedRoute";
import type { UserRole } from "../src/auth/types";
import { ParticipantsPage } from "../src/pages/ParticipantsPage";
import { StimuliPage } from "../src/pages/StimuliPage";

const state = vi.hoisted(() => ({ participants: [] as unknown[], authorizations: [] as unknown[] }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({
    data: path === "/participants" ? state.participants : path?.endsWith("/authorizations") ? state.authorizations : [],
    loading: false, error: "", reload: vi.fn(),
  }),
}));

const adult = { id: "p1", code: "P-ABC234", kind: "adult", age_years: 30, created_at: "2026-10-01T00:00:00Z",
  expires_at: "2027-09-26T00:00:00Z", notes: null, registered_by_me: true, deletion_requested_at: null,
  authorization_status: "missing", authorization_revoked_at: null };
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
  state.authorizations = [];
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
    // Solo la edad: el código lo genera el sistema y la equivalencia queda en la ficha de papel.
    expect(screen.getByText(/ficha de papel que custodia el docente/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/nombre|dni|tutor/i)).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Edad en años"), "9");
    expect(screen.getByText("Se registrará como: niño o niña.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Registrar participante" }));
    expect(await screen.findByRole("dialog", { name: "Antes de registrar a un niño o una niña" })).toBeInTheDocument();
    expect(screen.getByText("más sensibles")).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: "Entendido, registrar" });
    expect(confirm).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(confirm);
    await waitFor(() => expect(apiRequest).toHaveBeenLastCalledWith("/participants", expect.objectContaining({
      body: JSON.stringify({ kind: "child", age_years: 9, notes: null, child_notice_version: "2026-10-provisional" }),
    })));
    expect(await screen.findByText(/código P-ABC234/)).toBeInTheDocument();
  });

  it("el usuario solicita la eliminación y el docente la ejecuta", async () => {
    state.participants = [adult];
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

  it("registra la autorización firmada con casillas que empiezan sin marcar", async () => {
    state.participants = [{ ...adult }];
    vi.mocked(apiRequest).mockResolvedValue({} as never);
    withUser("student", <ParticipantsPage />);
    expect(screen.getByText("Falta autorización")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Autorizaciones" }));
    const participation = screen.getByRole("checkbox", { name: /\(a\) Autoriza la participación/ });
    const camera = screen.getByRole("checkbox", { name: /\(b\) Autoriza el uso de la cámara/ });
    expect(participation).not.toBeChecked();
    expect(camera).not.toBeChecked();
    // En un adulto no hay asentimiento.
    expect(screen.queryByRole("checkbox", { name: /asentimiento/ })).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Versión del formato"), "F-2026-1");
    await userEvent.click(participation);
    await userEvent.click(camera);
    await userEvent.click(screen.getByRole("button", { name: "Registrar autorización" }));
    expect(apiRequest).toHaveBeenCalledWith("/participants/p1/authorizations", expect.objectContaining({ method: "POST" }));
    const body = JSON.parse(String(vi.mocked(apiRequest).mock.calls[0][1]?.body));
    expect(body).toMatchObject({ form_version: "F-2026-1", participation: true, camera: true });
    expect(body).not.toHaveProperty("child_assent");
  });

  it("con niños pide el asentimiento y el docente ve los retiros", async () => {
    state.participants = [{ ...adult, id: "p2", code: "P-NIN234", kind: "child", age_years: 8, registered_by_me: false,
      authorization_status: "revoked", authorization_revoked_at: "2026-10-20T00:00:00Z" }];
    withUser("psychologist", <ParticipantsPage />);
    expect(screen.getByText(/No pueden iniciar sesiones nuevas/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Autorizaciones" }));
    expect(screen.getByText(/no se pueden iniciar sesiones nuevas ni registrar otra autorización/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Registrar autorización" })).not.toBeInTheDocument();
  });

  it("los estímulos exigen origen, licencia y declarar que no son fotos de participantes", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ title: "Forma" } as never);
    withUser("psychologist", <StimuliPage />, "/stimuli");
    const submit = screen.getByRole("button", { name: "Agregar estímulo" });
    await userEvent.upload(screen.getByLabelText(/Imagen/), new File(["x"], "forma.png", { type: "image/png" }));
    await userEvent.type(screen.getByLabelText("Título"), "Forma");
    await userEvent.selectOptions(screen.getByLabelText("Tipo"), "abstract");
    expect(screen.queryByLabelText("Expresión que se espera provocar")).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Categoría"), "Manchas");
    await userEvent.type(screen.getByLabelText("Origen"), "Creación propia");
    await userEvent.type(screen.getByLabelText("Licencia"), "Uso docente");
    await userEvent.click(screen.getByRole("checkbox", { name: /no es una fotografía de un participante/ }));
    expect(submit).toBeDisabled();  // falta declarar que no es una lámina proyectiva
    await userEvent.click(screen.getByRole("checkbox", { name: /no es una lámina de una prueba proyectiva/ }));
    expect(submit).toBeEnabled();
    await userEvent.click(submit);
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/stimuli", expect.objectContaining({ method: "POST" })));
    const body = vi.mocked(apiRequest).mock.calls[0][1]?.body as FormData;
    expect(body.get("kind")).toBe("abstract");
    expect(body.get("expected_expression")).toBeNull();
    expect(body.get("not_a_projective_test")).toBe("true");
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
