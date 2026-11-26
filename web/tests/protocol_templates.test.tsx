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

/** Abre el menú de tres puntos de un protocolo. */
async function openMenu(name: string) {
  await userEvent.click(screen.getByRole("button", { name: `Más acciones para «${name}»` }));
}

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
    // Una plantilla no se edita, no se elimina ni se aplica sin copiarla.
    expect(screen.queryByRole("link", { name: "Usar en el Analizador" })).not.toBeInTheDocument();
    await openMenu(template.name);
    expect(screen.getAllByRole("menuitem").map((item) => item.textContent)).toEqual(["Vista previa", "Copiar y modificar"]);
    await userEvent.click(screen.getByRole("menuitem", { name: "Copiar y modificar" }));
    expect(apiRequest).toHaveBeenCalledWith("/protocols/p1/copy", expect.objectContaining({ method: "POST" }));
    expect(await screen.findByText(/Se agregó una copia de «Emociones básicas 4 a 6 años»/)).toBeInTheDocument();
  });

  it("el docente comparte un protocolo suyo con su grupo y puede dejar de compartirlo", async () => {
    page("psychologist", [{ ...template, owned_by_me: true, shared_with_group: false }]);
    await openMenu(template.name);
    await userEvent.click(screen.getByRole("menuitem", { name: "Compartir con mi grupo" }));
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/protocols/p1/share",
      expect.objectContaining({ method: "PUT", body: JSON.stringify({ shared: true }) })));
    expect(await screen.findByText("Tu grupo puede copiar este protocolo como plantilla.")).toBeInTheDocument();
  });

  it("el docente ve cuáles comparte y no copia los de los usuarios de su grupo", async () => {
    page("psychologist", [{ ...template, owned_by_me: true }, { ...template, id: "p2", name: "De un usuario", shared_with_group: false }]);
    expect(screen.getByText("Compartido con tu grupo")).toBeInTheDocument();
    await openMenu(template.name);
    expect(screen.getAllByRole("menuitem").map((item) => item.textContent))
      .toEqual(["Vista previa", "Editar", "Duplicar", "Dejar de compartir", "Eliminar"]);
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("menu")).not.toBeInTheDocument();
    await openMenu("De un usuario");
    expect(screen.getAllByRole("menuitem").map((item) => item.textContent)).toEqual(["Vista previa"]);
  });
});

describe("menú de tres puntos de un protocolo", () => {
  const own: Protocol = {
    ...template, owned_by_me: true, shared_with_group: false, name: "Mi protocolo", pre_questionnaire_id: null,
    steps: [
      { kind: "practice", stimulus_id: null, target_expression: "happiness", hold_seconds: 2, exposure_seconds: 20,
        capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false },
      { kind: "drawing", stimulus_id: null, exposure_seconds: 90, capture_after_seconds: 0,
        record_verbal_response: false, shown_before_analyzer: false },
    ],
  };

  it("la vista previa muestra los pasos sin editarlos", async () => {
    page("student", [own]);
    await openMenu(own.name);
    await userEvent.click(screen.getByRole("menuitem", { name: "Vista previa" }));
    const dialog = screen.getByRole("dialog", { name: "Vista previa: Mi protocolo" });
    expect(dialog).toHaveTextContent("Práctica: muestra alegría · 20 s");
    expect(dialog).toHaveTextContent("Dibujo · 90 s");
    expect(screen.queryByRole("button", { name: "Guardar protocolo" })).not.toBeInTheDocument();
  });

  it("eliminar pide confirmación y avisa que las sesiones conservan su registro", async () => {
    page("student", [own]);
    await openMenu(own.name);
    await userEvent.click(screen.getByRole("menuitem", { name: "Eliminar" }));
    const confirm = screen.getByRole("alertdialog", { name: "Eliminar protocolo" });
    expect(confirm).toHaveTextContent("Las sesiones que lo usaron conservan su registro");
    expect(apiRequest).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Eliminar" }));
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/protocols/p1", expect.objectContaining({ method: "DELETE" })));
    expect(await screen.findByText(/Se eliminó «Mi protocolo»/)).toBeInTheDocument();
  });
});

describe("plantilla inicial de protocolos", () => {
  it("copia «Emociones básicas 4 a 6 años» a los protocolos propios", async () => {
    page("student", []);
    await userEvent.click(screen.getByRole("button", { name: "Usar la plantilla inicial" }));
    expect(apiRequest).toHaveBeenCalledWith("/protocols/starter", expect.objectContaining({ method: "POST" }));
    expect(await screen.findByText(/Se agregó «Emociones básicas 4 a 6 años» a tus protocolos/)).toBeInTheDocument();
  });
});
