import { fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { GuidePage } from "../src/pages/GuidePage";
import { navigationByRole } from "../src/routes/navigation";

const mocks = vi.hoisted(() => ({
  role: "student" as string,
  askAssistant: vi.fn(),
}));

vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: () => ({
    data: { topics: [
      { id: "conduct", title: "Conducir una sesión", note: "La cámara se abre en el navegador.",
        steps: ["En el «Analizador» elige un protocolo.", "Confirma la autorización."] },
      { id: "after", title: "Después de la sesión", note: null,
        steps: ["Abre la sesión en «Mis sesiones».", "Usa «Redactar el reporte»."] },
    ] },
    loading: false, error: "", reload: vi.fn(),
  }),
}));
vi.mock("../src/auth/useAuth", () => ({ useAuth: () => ({ user: { id: "u1", role: mocks.role } }) }));
vi.mock("../src/components/AssistantContext", () => ({ useAssistant: () => ({ askAssistant: mocks.askAssistant }) }));

function renderGuide() {
  return render(<MemoryRouter><GuidePage /></MemoryRouter>);
}

function topic(title: string) {
  return screen.getByRole("heading", { name: title }).closest("li") as HTMLElement;
}

describe("guía de uso", () => {
  beforeEach(() => {
    mocks.role = "student";
    mocks.askAssistant.mockReset();
    window.localStorage.clear();
  });

  it("muestra los temas que envía el servidor, con sus pasos en orden", () => {
    renderGuide();
    expect(screen.getByRole("heading", { name: "Conducir una sesión" })).toBeInTheDocument();
    const steps = within(topic("Conducir una sesión")).getAllByRole("checkbox").map((box) => box.closest("label")?.textContent);
    expect(steps).toEqual(["En el «Analizador» elige un protocolo.", "Confirma la autorización."]);
    expect(screen.getByText("La cámara se abre en el navegador.")).toBeInTheDocument();
    expect(screen.getByText(/no diagnostica/)).toBeInTheDocument();
  });

  it("la búsqueda deja solo los temas que coinciden, sin importar las tildes", () => {
    renderGuide();
    fireEvent.change(screen.getByLabelText("Buscar en la guía"), { target: { value: "reporte" } });
    expect(screen.queryByRole("heading", { name: "Conducir una sesión" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Después de la sesión" })).toBeInTheDocument();
    expect(screen.getByRole("status")).toHaveTextContent("1 tema coincide");
    fireEvent.change(screen.getByLabelText("Buscar en la guía"), { target: { value: "autorizacion" } });
    expect(screen.getByRole("heading", { name: "Conducir una sesión" })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Buscar en la guía"), { target: { value: "cocina" } });
    expect(screen.getByRole("status")).toHaveTextContent("Ningún tema coincide");
  });

  it("marca los pasos hechos y los recuerda en este navegador", () => {
    const { unmount } = renderGuide();
    const box = within(topic("Conducir una sesión")).getByRole("checkbox", { name: "Confirma la autorización." });
    fireEvent.click(box);
    expect(within(topic("Conducir una sesión")).getByText("1 de 2 pasos")).toBeInTheDocument();
    expect(screen.getByText("1 de 4")).toBeInTheDocument();
    unmount();
    renderGuide();
    expect(within(topic("Conducir una sesión")).getByRole("checkbox", { name: "Confirma la autorización." })).toBeChecked();
    fireEvent.click(within(topic("Conducir una sesión")).getByRole("button", { name: "Desmarcar los pasos" }));
    expect(within(topic("Conducir una sesión")).getByText("0 de 2 pasos")).toBeInTheDocument();
  });

  it("lleva a la pantalla del tema y abre a Emi con una pregunta editable", () => {
    renderGuide();
    const conduct = within(topic("Conducir una sesión"));
    expect(conduct.getByRole("link", { name: "Ir a Analizador" })).toHaveAttribute("href", "/analysis");
    fireEvent.click(conduct.getByRole("button", { name: "Preguntar a Emi" }));
    expect(mocks.askAssistant).toHaveBeenCalledWith("¿Cómo hago esto en EMOtv: conducir una sesión?");
  });

  it("la administración no ve el botón de Emi", () => {
    mocks.role = "admin";
    renderGuide();
    expect(screen.queryByRole("button", { name: "Preguntar a Emi" })).not.toBeInTheDocument();
  });

  it("todas las cuentas la tienen al final del menú", () => {
    for (const items of Object.values(navigationByRole)) {
      expect(items.find((item) => item.label === "Guía de uso")).toMatchObject({ to: "/guide", placement: "footer" });
    }
  });
});
