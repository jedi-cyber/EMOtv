import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { GuidePage } from "../src/pages/GuidePage";
import { navigationByRole } from "../src/routes/navigation";

vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: () => ({
    data: { topics: [{ id: "conduct", title: "Conducir una sesión", note: "La cámara se abre en el navegador.",
      steps: ["En el «Analizador» elige un protocolo.", "Confirma la autorización."] }] },
    loading: false, error: "", reload: vi.fn(),
  }),
}));

describe("guía de uso", () => {
  it("muestra los temas que envía el servidor, con sus pasos en orden", () => {
    render(<MemoryRouter><GuidePage /></MemoryRouter>);
    expect(screen.getByRole("heading", { name: "Conducir una sesión" })).toBeInTheDocument();
    const steps = screen.getAllByRole("listitem").map((item) => item.textContent);
    expect(steps).toContain("Confirma la autorización.");
    expect(screen.getByText("La cámara se abre en el navegador.")).toBeInTheDocument();
    expect(screen.getByText(/no diagnostica/)).toBeInTheDocument();
  });

  it("todas las cuentas la tienen al final del menú", () => {
    for (const items of Object.values(navigationByRole)) {
      expect(items.find((item) => item.label === "Guía de uso")).toMatchObject({ to: "/guide", placement: "footer" });
    }
  });
});
