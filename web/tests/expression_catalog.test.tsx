import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../src/auth/AuthContext";
import { RoleRoute } from "../src/auth/RoleRoute";
import { apiRequest } from "../src/api/http";
import { ExpressionCatalogProvider, useExpressionCatalog } from "../src/expressions/ExpressionCatalog";
import { AdminExpressionsPage } from "../src/pages/AdminExpressionsPage";

const { catalogResult } = vi.hoisted(() => ({ catalogResult: { data: null as unknown, error: "" } }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({
    data: path === null ? null : catalogResult.data, loading: false, error: catalogResult.error, reload: vi.fn(),
  }),
}));
vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn() }));

const text = (subject: string) => `${subject} de prueba con longitud suficiente. Segunda oración.`;
const sadness = {
  expression_key: "sadness", label_es: "Tristeza revisada", what_it_is: text("Qué es"),
  why_it_occurs: text("Por qué"), facial_cues: text("Rostro"), practice_tip: text("Práctica"),
  limitation_note: text("Limitación"), common_limitation: "Limitación común.", review_status: "draft",
  reviewed_by_user_id: null, reviewed_at: null, updated_at: "2026-10-08T09:00:00Z",
};

function Labels() {
  const { label } = useExpressionCatalog();
  return <ul>{["sadness", "fear", "unknown_key"].map((key) => <li key={key}>{label(key)}</li>)}</ul>;
}

function renderAs(role: "student" | "psychologist" | "admin", element: React.ReactNode, path = "/") {
  const router = createMemoryRouter([
    { path, element },
    { path: "/unauthorized", element: <p>Acceso no autorizado</p> },
  ], { initialEntries: [path] });
  return render(<AuthContext.Provider value={{ user: { id: "admin-1", email: "a@example.com", role, is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <ExpressionCatalogProvider><RouterProvider router={router} /></ExpressionCatalogProvider>
  </AuthContext.Provider>);
}

beforeEach(() => {
  catalogResult.data = [sadness]; catalogResult.error = "";
  vi.mocked(apiRequest).mockReset();
});

describe("traducción centralizada de expresiones", () => {
  it("usa label_es del catálogo y respaldo local para el resto", () => {
    renderAs("student", <Labels />);
    const items = screen.getAllByRole("listitem").map((item) => item.textContent);
    expect(items).toEqual(["Tristeza revisada", "Miedo", "unknown_key"]);
  });

  it("si la API no responde, muestra etiquetas en español de respaldo", () => {
    catalogResult.data = null; catalogResult.error = "No pudimos cargar esta información";
    renderAs("student", <Labels />);
    expect(screen.getAllByRole("listitem").map((item) => item.textContent)).toEqual(["Tristeza", "Miedo", "unknown_key"]);
  });
});

describe("administración del catálogo", () => {
  it.each(["student", "psychologist"] as const)("%s no puede entrar a la página", (role) => {
    renderAs(role, <RoleRoute allowed={["admin"]}><AdminExpressionsPage /></RoleRoute>, "/admin/expressions");
    expect(screen.getByText("Acceso no autorizado")).toBeInTheDocument();
  });

  it("administración edita y marca como revisado", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ ...sadness, review_status: "reviewed", reviewed_at: "2026-10-08T10:00:00Z", reviewed_by_user_id: "admin-1" } as never);
    renderAs("admin", <RoleRoute allowed={["admin"]}><AdminExpressionsPage /></RoleRoute>, "/admin/expressions");
    const row = screen.getByRole("row", { name: /sadness/ });
    expect(within(row).getByText("Borrador")).toBeInTheDocument();
    await userEvent.click(within(row).getByRole("button", { name: "Editar Tristeza revisada" }));
    const form = screen.getByRole("form", { name: "Editar Tristeza revisada" });
    const why = within(form).getByLabelText("¿Por qué suele presentarse?");
    await userEvent.clear(why);
    await userEvent.type(why, "Texto general sobre las personas. Revisado por Psicología.");
    await userEvent.click(within(form).getByLabelText(/Marcar como revisado/));
    await userEvent.click(within(form).getByRole("button", { name: "Guardar" }));
    const [path, options] = vi.mocked(apiRequest).mock.calls[0];
    expect(path).toBe("/expressions/sadness");
    expect(options?.method).toBe("PUT");
    const body = JSON.parse(String(options?.body));
    expect(body.review_status).toBe("reviewed");
    expect(body.why_it_occurs).toBe("Texto general sobre las personas. Revisado por Psicología.");
    expect(await screen.findByText("Texto guardado y marcado como revisado.")).toBeInTheDocument();
  });

  it("valida la longitud antes de enviar", async () => {
    renderAs("admin", <RoleRoute allowed={["admin"]}><AdminExpressionsPage /></RoleRoute>, "/admin/expressions");
    await userEvent.click(screen.getByRole("button", { name: "Editar Tristeza revisada" }));
    const form = screen.getByRole("form", { name: "Editar Tristeza revisada" });
    const tip = within(form).getByLabelText("Para practicar");
    await userEvent.clear(tip);
    await userEvent.type(tip, "Corto.");
    await userEvent.click(within(form).getByRole("button", { name: "Guardar" }));
    expect(screen.getByRole("alert")).toHaveTextContent("«Para practicar» debe tener entre 20 y 1200 caracteres.");
    expect(apiRequest).not.toHaveBeenCalled();
  });
});
