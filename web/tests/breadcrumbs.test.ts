import { describe, expect, it } from "vitest";
import { breadcrumbs } from "../src/layouts/AppLayout";

const last = (pathname: string, role: Parameters<typeof breadcrumbs>[1] = "student") =>
  breadcrumbs(pathname, role).at(-1)?.label;

describe("breadcrumbs", () => {
  it("el Analizador no pasa por las actividades de posturas, que están desactivadas", () => {
    expect(breadcrumbs("/analysis", "student").map((item) => item.label)).toEqual(["Inicio", "Analizador"]);
  });

  it("la sesión con protocolo cuelga de las sesiones", () => {
    expect(breadcrumbs("/guided/abc", "student").map((item) => item.label))
      .toEqual(["Inicio", "Mis sesiones", "Sesión con protocolo"]);
  });

  it("las páginas del menú tienen su nombre y no «Página no encontrada»", () => {
    expect(last("/protocols")).toBe("Protocolos");
    expect(last("/questionnaires")).toBe("Cuestionarios");
    expect(last("/guide")).toBe("Guía de uso");
    expect(last("/reviews", "psychologist")).toBe("Por revisar");
    expect(last("/stimuli", "psychologist")).toBe("Estímulos");
    expect(last("/stimuli", "admin")).toBe("Estímulos institucionales");
    expect(last("/no-existe")).toBe("Página no encontrada");
  });
});
