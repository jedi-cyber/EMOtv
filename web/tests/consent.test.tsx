import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ConsentPage } from "../src/pages/ConsentPage";
import { AuthContext } from "../src/auth/AuthContext";
import { apiRequest } from "../src/api/http";

vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn() }));

const policy = { id: "EMOTV-CONSENT-DEMO-002:v0.2", code: "EMOTV-CONSENT-DEMO-002", version: "v0.2",
  title: "Consentimiento de prueba para pruebas funcionales", content: "Texto de la política v0.2",
  effective_at: "2026-10-06T15:00:00+00:00", is_demo: true, mode: "demo", url: null, available: true };

function page(activeConsent: unknown) {
  vi.mocked(apiRequest).mockReset().mockImplementation(async (path) => {
    if (path === "/consent-policy") return policy as never;
    if (path === "/students") return [{ id: "student-1", user_id: "u", student_code: "PRUEBA-07" }] as never;
    if (path.endsWith("/consents/active")) return activeConsent as never;
    return {} as never;
  });
  const router = createMemoryRouter([{ path: "/consent", element: <ConsentPage /> }], { initialEntries: ["/consent"] });
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "prueba-07@example.com", role: "student", is_active: true }, token: "test", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}><RouterProvider router={router} /></AuthContext.Provider>);
}

beforeEach(() => vi.clearAllMocks());

describe("página de consentimiento", () => {
  it("muestra versión y fecha de la política vigente y un enlace para revocar", async () => {
    page({ id: "c1", policy_version: policy.id, granted_at: "2026-10-06T16:00:00+00:00" });
    const summary = await screen.findByLabelText("Política vigente");
    expect(summary).toHaveTextContent("EMOTV-CONSENT-DEMO-002 · versión v0.2");
    expect(summary).toHaveTextContent(/vigente desde el \d{2} de octubre de 2026/);
    expect(await screen.findByRole("link", { name: "Revocar mi consentimiento" })).toHaveAttribute("href", "#revocar");
    expect(screen.getByRole("button", { name: "Revocar consentimiento" }).closest("#revocar")).not.toBeNull();
  });

  it("pide aceptar la v0.2 a quien aceptó la v0.1 sin ocultar la revocación", async () => {
    page({ id: "c0", policy_version: "EMOTV-CONSENT-DEMO-001:v0.1", granted_at: "2026-10-01T16:00:00+00:00" });
    expect(await screen.findByText(/La política vigente cambió/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Acepto la nueva versión" })).toBeDisabled();
    expect(screen.getByRole("link", { name: "Revocar mi consentimiento" })).toBeInTheDocument();
  });
});
