import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AdminActivitiesPage } from "../src/pages/AdminActivitiesPage";
import { AuthContext } from "../src/auth/AuthContext";
import { ApiError, apiRequest } from "../src/api/http";

const step = (posture: string, instruction: string) => ({ posture, instruction, duration_seconds: 4 });
const activities = [
  { id: "morning_mobility", name: "Movilidad suave", description: "Varias posturas", required_posture: "arms_open", duration_seconds: 4, repetitions: 1, steps: [step("arms_open", "Abre"), step("arms_up", "Eleva")] },
  { id: "open_and_reach", name: "Abrir y alcanzar", description: "Varias posturas", required_posture: "arms_open", duration_seconds: 4, repetitions: 1, steps: [step("arms_open", "Abre"), step("arms_forward", "Al frente")] },
  { id: "full_body_flow", name: "Movimiento completo", description: "Varias posturas", required_posture: "arms_up", duration_seconds: 4, repetitions: 1, steps: [step("arms_up", "Eleva"), step("squat", "Flexiona")] },
  { id: "arms_up_5s", name: "Elevación de brazos", description: "Un paso", required_posture: "arms_up", duration_seconds: 5, repetitions: 1, steps: [step("arms_up", "Eleva")] },
];
const recommendations = [
  { expression_key: "sadness", activity_ids: ["morning_mobility", "open_and_reach"] },
  { expression_key: "fear", activity_ids: [] },
];
const reloads = vi.hoisted(() => ({ recommendations: vi.fn(), activities: vi.fn() }));

vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => path === "/recommendations"
    ? { data: recommendations, loading: false, error: "", reload: reloads.recommendations }
    : { data: activities, loading: false, error: "", reload: reloads.activities },
}));
vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn() }));

function page() {
  return render(<AuthContext.Provider value={{ user: { id: "a", email: "admin@example.com", role: "admin", is_active: true }, token: "token", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter><AdminActivitiesPage /></MemoryRouter>
  </AuthContext.Provider>);
}

beforeEach(() => {
  vi.mocked(apiRequest).mockReset().mockResolvedValue({} as never);
  reloads.recommendations.mockReset(); reloads.activities.mockReset();
});

describe("administración de recomendaciones", () => {
  it("muestra el 409 que nombra las expresiones afectadas al dejar una actividad recomendada con un paso", async () => {
    const detail = "La actividad morning_mobility se recomienda para: Tristeza, Miedo. Una actividad recomendada necesita al menos 2 pasos; quítala primero de esas recomendaciones o conserva sus pasos.";
    vi.mocked(apiRequest).mockRejectedValue(new ApiError(409, detail));
    page();
    const row = screen.getByText("Movilidad suave").closest("tr")!;
    await userEvent.click(within(row).getByRole("button", { name: "Editar" }));
    await userEvent.click(screen.getAllByRole("button", { name: "Quitar paso" })[1]);
    await userEvent.click(screen.getByRole("button", { name: "Guardar cambios" }));
    expect(screen.getByRole("alert")).toHaveTextContent("se recomienda para: Tristeza, Miedo");
    expect(vi.mocked(apiRequest).mock.calls[0][0]).toBe("/activities/morning_mobility");
  });

  it("lista las asociaciones por expresión en español y en orden", () => {
    page();
    const table = screen.getByRole("region", { name: "Actividades recomendadas por expresión" });
    expect(within(table).getByText("Movilidad suave → Abrir y alcanzar")).toBeInTheDocument();
    expect(within(table).getByText("Tristeza")).toBeInTheDocument();
    expect(within(table).getByText("Sin recomendación automática")).toBeInTheDocument();
  });

  it("reordena, quita y añade actividades y guarda en el orden elegido", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ expression_key: "sadness", activity_ids: [] } as never);
    page();
    await userEvent.click(screen.getByRole("button", { name: "Editar recomendaciones de Tristeza" }));
    const group = screen.getByRole("group", { name: "Recomendaciones de Tristeza" });
    await userEvent.click(within(group).getByRole("button", { name: "Bajar Movilidad suave" }));
    await userEvent.click(within(group).getByRole("button", { name: "Quitar Movilidad suave" }));
    const options = within(within(group).getByLabelText("Añadir actividad")).getAllByRole("option").map((option) => option.textContent);
    // Las actividades de un solo paso no se ofrecen.
    expect(options).toEqual(["Selecciona…", "Movilidad suave", "Movimiento completo"]);
    await userEvent.selectOptions(within(group).getByLabelText("Añadir actividad"), "full_body_flow");
    await userEvent.click(within(group).getByRole("button", { name: "Añadir" }));
    await userEvent.click(within(group).getByRole("button", { name: "Guardar recomendaciones" }));
    const [path, init] = vi.mocked(apiRequest).mock.calls.at(-1)!;
    expect(path).toBe("/recommendations/sadness");
    expect(JSON.parse(String(init?.body))).toEqual({ activity_ids: ["open_and_reach", "full_body_flow"] });
    expect(reloads.recommendations).toHaveBeenCalled();
    expect(screen.getByText("Recomendaciones de Tristeza guardadas.")).toBeInTheDocument();
  });

  it("muestra el motivo si la API rechaza la asociación", async () => {
    vi.mocked(apiRequest).mockRejectedValue(new ApiError(422, "La actividad x no existe"));
    page();
    await userEvent.click(screen.getByRole("button", { name: "Editar recomendaciones de Miedo" }));
    await userEvent.click(screen.getByRole("button", { name: "Guardar recomendaciones" }));
    expect(screen.getByRole("alert")).toHaveTextContent("La actividad x no existe");
  });
});
