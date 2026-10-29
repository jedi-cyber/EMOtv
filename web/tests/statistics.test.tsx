import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../src/auth/AuthContext";
import type { UserRole } from "../src/auth/types";
import { StatisticsPage } from "../src/pages/StatisticsPage";

const state = vi.hoisted(() => ({ data: {} as Record<string, unknown>, paths: [] as string[] }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => {
    if (path) state.paths.push(path);
    return { data: path === null ? null : state.data[path.split("?")[0]] ?? null, loading: false, error: "", reload: vi.fn() };
  },
}));

function withUser(role: UserRole) {
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role, is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter><StatisticsPage /></MemoryRouter>
  </AuthContext.Provider>);
}

const keys = ["neutral", "happiness", "surprise", "sadness", "anger", "disgust", "fear", "contempt"];
const stats = (changes: Record<string, unknown> = {}) => ({
  scope: "mine", notice: "", few_sessions: false, few_sessions_notice: null,
  sessions: { total: 6, completed: 4, interrupted: 2, average_duration_seconds: 750 },
  expressions: { counted_captures: 4, excluded_captures: 1, rows: keys.map((expression) => ({
    expression, captures: expression === "happiness" ? 3 : expression === "neutral" ? 1 : 0,
    percent: expression === "happiness" ? 75 : expression === "neutral" ? 25 : 0, sessions: expression === "happiness" ? 2 : 0 })) },
  coincidence: { compared: 4, matched: 3 },
  protocols: [{ family_id: "f1", name: "Secuencia" }],
  questionnaires: [{ id: "q1", title: "Antes de empezar", version: 2, responses: 3 }],
  questionnaire: { id: "q1", title: "Antes de empezar", version: 2, responses: 3, questions: [
    { text: "¿Dormiste bien?", kind: "single_choice", answered: 3, unanswered: 0, counts: [{ label: "Sí", count: 2 }, { label: "No", count: 1 }] },
    { text: "Cuéntanos algo", kind: "short_text", answered: 2, unanswered: 1, counts: null },
  ] },
  ...changes,
});

beforeEach(() => {
  state.data = {};
  state.paths = [];
});

describe("estadísticas", () => {
  it("muestra el aviso fijo, el resumen y las expresiones con sus conteos", () => {
    state.data["/statistics"] = stats();
    withUser("student");
    expect(screen.getByText(/cuentan sesiones, no personas, y son estimaciones\. No permiten sacar conclusiones sobre ninguna persona/)).toBeInTheDocument();
    expect(screen.queryByText("Hay pocas sesiones para sacar conclusiones.")).not.toBeInTheDocument();
    expect(screen.getByText("12 min 30 s")).toBeInTheDocument();
    // Gráfico de una sola serie, ordenado de mayor a menor; la tabla queda como vista accesible.
    const chart = screen.getByRole("list", { name: "Porcentaje de capturas por expresión estimada" });
    const bars = within(chart).getAllByRole("listitem");
    expect(bars[0]).toHaveAccessibleName("Felicidad: 75 %, 3 capturas en 2 sesiones");
    expect(bars[1]).toHaveAccessibleName("Neutral: 25 %, 1 captura en 0 sesiones");
    expect(screen.getByRole("list", { name: "Sesiones completadas e interrumpidas" })).toBeInTheDocument();
    expect(screen.getByRole("table")).toHaveTextContent("75 %");
    expect(screen.getByText(/En 3 de 4 estímulos emocionales/)).toBeInTheDocument();
    // El usuario no elige el grupo ni ve totales por usuario.
    expect(screen.queryByRole("radio", { name: "Mi grupo" })).not.toBeInTheDocument();
  });

  it("sin capturas de buena calidad no dibuja el gráfico de expresiones", () => {
    state.data["/statistics"] = stats({ expressions: { counted_captures: 0, excluded_captures: 2, rows: [] }, coincidence: { compared: 0, matched: 0 } });
    withUser("student");
    expect(screen.queryByRole("list", { name: "Porcentaje de capturas por expresión estimada" })).not.toBeInTheDocument();
    expect(screen.getByText(/Ningún estímulo emocional tuvo una captura/)).toBeInTheDocument();
  });

  it("con menos de 5 sesiones avisa que son pocas", () => {
    state.data["/statistics"] = stats({ few_sessions: true, sessions: { total: 2, completed: 2, interrupted: 0, average_duration_seconds: null } });
    withUser("student");
    expect(screen.getByText("Hay pocas sesiones para sacar conclusiones.")).toBeInTheDocument();
  });

  it("las respuestas de texto solo se cuentan", () => {
    state.data["/statistics"] = stats();
    withUser("student");
    expect(screen.getByText(/Hubo 2 respuestas de texto; su contenido no se muestra/)).toBeInTheDocument();
    const answers = screen.getByRole("list", { name: "Respuestas a «¿Dormiste bien?»" });
    expect(within(answers).getAllByRole("listitem").map((item) => item.getAttribute("aria-label"))).toEqual(["Sí: 2", "No: 1"]);
  });

  it("el docente elige su grupo y ve los totales por usuario", async () => {
    state.data["/statistics"] = stats({ scope: "group", by_user: [{ email: "usuario1@example.com", sessions: 6, completed: 4, interrupted: 2 }] });
    withUser("psychologist");
    await userEvent.click(screen.getByRole("radio", { name: "Mi grupo" }));
    expect(state.paths.at(-1)).toContain("scope=group");
    expect(screen.getByText("usuario1@example.com")).toBeInTheDocument();
  });

  it("los filtros se envían al servidor", async () => {
    state.data["/statistics"] = stats();
    withUser("student");
    await userEvent.selectOptions(screen.getByLabelText("Protocolo"), "none");
    await userEvent.selectOptions(screen.getByLabelText("Público"), "infantil");
    await userEvent.click(screen.getByRole("button", { name: "Aplicar filtros" }));
    expect(state.paths.at(-1)).toMatch(/protocol=none/);
    expect(state.paths.at(-1)).toMatch(/audience=infantil/);
  });

  it("«Copiar tabla» copia los datos visibles separados por tabulaciones, sin crear archivos", async () => {
    state.data["/statistics"] = stats();
    const user = userEvent.setup();
    const writeText = vi.spyOn(navigator.clipboard, "writeText").mockResolvedValue();
    withUser("student");
    await user.click(screen.getByRole("button", { name: "Copiar tabla" }));
    const text = writeText.mock.calls[0][0];
    expect(text).toContain("Sesiones\tCompletadas\tInterrumpidas");
    expect(text).toContain("6\t4\t2\t750");
    expect(text).toContain("Felicidad\t75\t3\t2");
    expect(text).toContain("\tSí\t2");
    expect(await screen.findByText(/Tabla copiada/)).toBeInTheDocument();
  });
});
