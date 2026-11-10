import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../src/auth/AuthContext";
import { ReviewsPage, type PendingReview } from "../src/pages/ReviewsPage";
import { navigationByRole } from "../src/routes/navigation";

const data = vi.hoisted(() => ({ value: [] as unknown[] }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: () => ({ data: data.value, loading: false, error: "", reload: vi.fn() }),
}));

const day = 86_400_000;
const report: PendingReview = { kind: "report", session_id: "s1", session_code: "S-4F7K2Q", user_code: "U-001",
  waiting_since: new Date(Date.now() - 3 * day).toISOString(), report_id: "r1" };
const deletion: PendingReview = { kind: "deletion", session_id: "s2", session_code: "S-9PX2LM", user_code: "U-002",
  waiting_since: new Date().toISOString(), report_id: null };

function page() {
  return render(<AuthContext.Provider value={{ user: { id: "d", email: "d@example.com", role: "psychologist", is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter><ReviewsPage /></MemoryRouter>
  </AuthContext.Provider>);
}

beforeEach(() => { data.value = []; });

describe("Por revisar del docente", () => {
  it("muestra lo que espera, cuánto lleva esperando y adónde ir", () => {
    data.value = [report, deletion];
    page();
    expect(screen.getByText("Reporte enviado a revisión")).toBeInTheDocument();
    expect(screen.getByText("Sesión S-4F7K2Q · Usuario U-001")).toBeInTheDocument();
    expect(screen.getByText("Hace 3 días")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Revisar reporte" })).toHaveAttribute("href", "/sessions/s1/report");
    expect(screen.getByText("Pedido de eliminación")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ver la sesión" })).toHaveAttribute("href", "/sessions/s2");
  });

  it("sin pendientes lo dice y remite a las imágenes", () => {
    page();
    expect(screen.getByText(/No hay nada por revisar/)).toBeInTheDocument();
  });

  it("solo el docente tiene «Por revisar» en el menú, con su contador", () => {
    expect(navigationByRole.psychologist.find((item) => item.to === "/reviews")?.counter).toBe("reviews");
    expect([...navigationByRole.student, ...navigationByRole.admin, ...navigationByRole.superadmin]
      .some((item) => item.to === "/reviews")).toBe(false);
  });
});
