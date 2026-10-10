import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConsentPage } from "../src/pages/ConsentPage";
import { AuthContext } from "../src/auth/AuthContext";
import { apiRequest } from "../src/api/http";

vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn() }));

const policy = { id: "EMOTV-CONSENT-DEMO-002:v0.2", code: "EMOTV-CONSENT-DEMO-002", version: "v0.2",
  title: "Consentimiento de prueba para pruebas funcionales",
  content: "# Título interno\n\n## Uso de la cámara\n\nLa cámara se abre en tu navegador y la imagen se\nanaliza en memoria. **No se guardan fotografías.**\n\n- la expresión estimada;\n- la actividad realizada.",
  effective_at: "2026-10-06T15:00:00+00:00", is_demo: true, mode: "demo", url: null, available: true };
const current = { id: "c1", policy_version: policy.id, granted_at: "2026-10-06T16:00:00+00:00", revoked_at: null };
const older = { id: "c0", policy_version: "EMOTV-CONSENT-DEMO-001:v0.1", granted_at: "2026-10-01T16:00:00+00:00", revoked_at: "2026-10-05T10:00:00+00:00" };

function page(activeConsent: unknown, history: unknown[] = activeConsent ? [activeConsent] : []) {
  vi.mocked(apiRequest).mockReset().mockImplementation(async (path) => {
    if (path === "/consent-policy") return policy as never;
    if (path === "/students") return [{ id: "student-1", user_id: "u", student_code: "PRUEBA-07" }] as never;
    if (path.endsWith("/consents/active")) return activeConsent as never;
    if (path.endsWith("/consents")) return history as never;
    return {} as never;
  });
  const router = createMemoryRouter([{ path: "/consent", element: <ConsentPage /> }, { path: "/analysis", element: <p>Analizador</p> }],
    { initialEntries: ["/consent"] });
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "prueba-07@example.com", role: "student", is_active: true }, token: "test", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}><RouterProvider router={router} /></AuthContext.Provider>);
}

function card(title: string) {
  return screen.getByRole("heading", { name: title }).closest("article") as HTMLElement;
}

beforeEach(() => vi.clearAllMocks());

describe("página de consentimiento", () => {
  it("muestra la política aceptada y el consentimiento activo sin identificadores técnicos", async () => {
    page(current);
    await screen.findByRole("heading", { name: "Política de análisis facial" });
    const policyCard = card("Política de análisis facial");
    expect(policyCard).toHaveTextContent("Versión 0.2");
    expect(policyCard).toHaveTextContent(/Vigente desde el 6 de octubre de 2026/);
    expect(within(policyCard).getByText("Aceptada")).toBeInTheDocument();
    expect(within(policyCard).getByRole("button", { name: "Leer política" })).toBeInTheDocument();
    const consentCard = card("Tu consentimiento");
    expect(within(consentCard).getByText("Activo")).toBeInTheDocument();
    expect(consentCard).toHaveTextContent(/Aceptado el 6 de octubre de 2026/);
    expect(within(consentCard).getByRole("button", { name: "Revocar consentimiento" })).toBeInTheDocument();
    expect(screen.queryByText(/EMOTV-CONSENT/)).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Versiones anteriores" })).not.toBeInTheDocument();
  });

  it("avisa con un Callout cuando la política vigente cambió y muestra las versiones anteriores", async () => {
    page({ ...older, revoked_at: null }, [{ ...older, revoked_at: null }]);
    expect(await screen.findByText(/La política vigente cambió/)).toBeInTheDocument();
    expect(within(card("Tu consentimiento")).getByText("Desactualizado")).toBeInTheDocument();
    expect(within(card("Política de análisis facial")).getByText("Pendiente de aceptar")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Leer y aceptar" })).toHaveLength(2);
  });

  it("lista las versiones anteriores solo si el historial las tiene", async () => {
    page(current, [current, older]);
    const history = await screen.findByRole("heading", { name: "Versiones anteriores" });
    expect(history.closest("article")).toHaveTextContent(/Versión 0.1.*revocada el 5 de octubre de 2026/);
  });

  it("acepta la política desde el modal: documento renderizado, casilla obligatoria y aceptación", async () => {
    page(null);
    expect(await within(await screen.findByRole("heading", { name: "Tu consentimiento" }).then((h) => h.closest("article") as HTMLElement)).findByText("Sin aceptar")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Leer y aceptar" }));
    const dialog = screen.getByRole("dialog", { name: policy.title });
    expect(within(dialog).getByRole("heading", { level: 3, name: "Uso de la cámara" })).toBeInTheDocument();
    expect(within(dialog).queryByText("Título interno")).not.toBeInTheDocument();
    expect(within(dialog).getByText(/La cámara se abre en tu navegador y la imagen se analiza en memoria\./)).toBeInTheDocument();
    expect(within(dialog).getByText("No se guardan fotografías.").tagName).toBe("STRONG");
    expect(within(dialog).getAllByRole("listitem")).toHaveLength(2);
    expect(within(dialog).getByText(`Identificador: ${policy.id}`, { exact: false })).toBeInTheDocument();
    expect(within(dialog).getByText("Marca la casilla para continuar")).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Aceptar la política" })).toBeDisabled();
    expect(within(dialog).getByRole("button", { name: "Ahora no" })).toBeEnabled();
    await userEvent.click(within(dialog).getByRole("checkbox", { name: /He leído la política/ }));
    expect(within(dialog).queryByText("Marca la casilla para continuar")).not.toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Aceptar la política" }));
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/students/student-1/consents",
      expect.objectContaining({ method: "POST", body: JSON.stringify({ policy_version: policy.id }) })));
    expect(await screen.findByText("Analizador")).toBeInTheDocument();
  });

  it("confirma la revocación en un modal que explica qué deja de funcionar", async () => {
    page(current);
    await userEvent.click(await screen.findByRole("button", { name: "Revocar consentimiento" }));
    const dialog = screen.getByRole("alertdialog", { name: "Revocar consentimiento" });
    expect(dialog).toHaveTextContent("no podrás iniciar nuevos análisis faciales");
    expect(within(dialog).getByRole("button", { name: "Cancelar" })).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Revocar" }));
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/students/student-1/consents/revoke", expect.objectContaining({ method: "POST" })));
    expect(await screen.findByText(/Consentimiento revocado/)).toBeInTheDocument();
  });
});
