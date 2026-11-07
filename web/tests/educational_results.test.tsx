import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionEducational, SessionMetrics } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { StimulusMetrics } from "../src/insights/StimulusMetrics";
import { StatisticsPage } from "../src/pages/StatisticsPage";

// Bloque 7: resultados educativos en el reporte y en las estadísticas. Solo
// cuentan y nombran lo ocurrido; no son un puntaje ni una conclusión.

const data = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === null ? null : data.value[path.split("?")[0]] ?? null, loading: false, error: "", reload: vi.fn() }),
}));

const VALUATIONS = /bien hecho|excelente|fracas|falló|mal\b|diagn|patol|preocup|puntos/i;
const NOTICE = "Resume lo que ocurrió en cada actividad de esta sesión. No es un puntaje, no compara con otras sesiones y no permite sacar conclusiones sobre la persona.";

const educational: SessionEducational = {
  recognition: { exercises: 1, applied: 1, matched: 1, timed_out: 0, sentence: "Eligió la emoción de la imagen en 1 de 1 ejercicio." },
  drawing: { exercises: 3, completed: 1, timed_out: 0, indicated: [{ expression: "happiness", count: 1 }],
    sentence: "Completó 1 de 3 dibujos señalando una emoción: alegría (1)." },
  games: { games: 2, played: 2, attempts: 3, rounds_total: 4, rounds_done: 2, matched: 2, first_try: 2, help_used: 0,
    sentence: "Jugó 2 de 4 rondas. Emparejó 2 imágenes, 2 a la primera. Se repitió 1 vez (cuenta el primer intento)." },
  practice: { exercises: 1, applied: 1, achieved: 1, sentence: "Logró la expresión pedida en 1 de 1 ejercicio." },
  not_completed: {
    items: [
      { step_index: 4, kind: "drawing", activity: "Dibujo", status: "skipped", label: "Se omitió" },
      { step_index: 5, kind: "game", activity: "Juego de emparejar", status: "stopped", label: "Quedó interrumpida" },
      { step_index: 6, kind: "drawing", activity: "Dibujo", status: "not_reached", label: "No llegó a aplicarse" },
    ],
    skipped: 1, stopped: 1, not_reached: 1, sentence: "1 actividad se omitió, 1 quedó interrumpida y 1 no llegó a aplicarse." },
  notice: NOTICE,
};

const metrics: SessionMetrics = {
  session_id: "s1", emotional: [], abstract: [], abstract_notice: null, educational,
  totals: { emotional_stimuli: 0, counted: 0, matched: 0, excluded_captures: 0, sentence: "" },
};

beforeEach(() => { data.value = {}; });

describe("resultados educativos de una sesión (detalle, reporte e impresión)", () => {
  it("distingue cada actividad y las que no llegaron a su final", () => {
    render(<StimulusMetrics metrics={metrics} expressionLabel={(key) => key ?? "—"} />);
    const section = screen.getByRole("region", { name: "Resultados educativos" });
    expect(within(section).getByRole("note")).toHaveTextContent(NOTICE);
    const pairs = within(section).getAllByRole("term").map((term) => [term.textContent, term.nextElementSibling?.textContent]);
    expect(pairs).toEqual([
      ["Reconocimiento", educational.recognition!.sentence],
      ["Dibujo", educational.drawing!.sentence],
      ["Juegos", educational.games!.sentence],
      ["Práctica facial", educational.practice!.sentence],
      ["Omitidas o interrumpidas", educational.not_completed.sentence],
    ]);
    const list = within(section).getByRole("list", { name: "Actividades que no llegaron a su final" });
    expect(within(list).getAllByRole("listitem").map((item) => item.textContent)).toEqual([
      "Paso 5 · Dibujo: se omitió.", "Paso 6 · Juego de emparejar: quedó interrumpida.", "Paso 7 · Dibujo: no llegó a aplicarse."]);
    expect(section.textContent!.replace(NOTICE, "")).not.toMatch(VALUATIONS);
  });

  it("solo nombra las actividades que tuvo la sesión y sin pendientes no hay lista", () => {
    render(<StimulusMetrics metrics={{ ...metrics, educational: { ...educational, recognition: null, games: null, practice: null,
      not_completed: { items: [], skipped: 0, stopped: 0, not_reached: 0, sentence: "Todas las actividades llegaron a su final." } } }}
      expressionLabel={(key) => key ?? "—"} />);
    const section = screen.getByRole("region", { name: "Resultados educativos" });
    expect(within(section).getAllByRole("term").map((term) => term.textContent)).toEqual(["Dibujo", "Omitidas o interrumpidas"]);
    expect(within(section).getByText("Todas las actividades llegaron a su final.")).toBeInTheDocument();
    expect(within(section).queryByRole("list")).not.toBeInTheDocument();
  });

  it("una sesión antigua sin actividades no muestra el resumen", () => {
    render(<StimulusMetrics metrics={{ ...metrics, educational: null }} expressionLabel={(key) => key ?? "—"} />);
    expect(screen.queryByRole("region", { name: "Resultados educativos" })).not.toBeInTheDocument();
    render(<StimulusMetrics metrics={{ ...metrics, educational: undefined }} expressionLabel={(key) => key ?? "—"} />);
    expect(screen.queryByRole("region", { name: "Resultados educativos" })).not.toBeInTheDocument();
  });
});

describe("dibujos y juegos en las estadísticas", () => {
  const gameRow = { games: 2, attempts: 3, completed: 1, timed_out: 0, skipped: 0, stopped: 1, rounds_total: 4, rounds_done: 2,
    matched: 2, first_try: 2, help_used: 0, sentence: "Jugó 2 de 4 rondas. Emparejó 2 imágenes, 2 a la primera." };
  const stats = (changes: Record<string, unknown> = {}) => ({
    scope: "mine", notice: "", few_sessions: false, few_sessions_notice: null,
    sessions: { total: 1, completed: 0, interrupted: 1, average_duration_seconds: 120 },
    expressions: { counted_captures: 0, excluded_captures: 0, rows: [] },
    coincidence: { compared: 0, matched: 0 }, protocols: [], questionnaires: [], questionnaire: null, practice: null,
    drawing: { sessions: 1, notice: "Cuenta la emoción que se señaló al terminar cada dibujo. El dibujo no se guarda ni se interpreta.",
      totals: { exercises: 2, answered: 1, timed_out: 0, skipped: 1, stopped: 0, sentence: "Se señaló una emoción en 1 de 2 dibujos." },
      by_expression: [{ expression: "happiness", count: 1 }] },
    games: { sessions: 1, notice: "Describe lo que ocurrió en los juegos.", totals: gameRow,
      by_type: [{ ...gameRow, game_type: "matching" }] },
    ...changes,
  });

  function page() {
    return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
      <MemoryRouter><StatisticsPage /></MemoryRouter>
    </AuthContext.Provider>);
  }

  it("cuentan sesiones, no personas, con su aviso", () => {
    data.value["/statistics"] = stats();
    page();
    const drawing = screen.getByRole("region", { name: "Dibujos" });
    expect(within(drawing).getByRole("note")).toHaveTextContent("El dibujo no se guarda ni se interpreta.");
    expect(within(drawing).getByText(/Se señaló una emoción en 1 de 2 dibujos\. En 1 sesión\./)).toBeInTheDocument();
    expect(within(drawing).getByRole("cell", { name: "Alegría" })).toBeInTheDocument();
    const games = screen.getByRole("region", { name: "Juegos" });
    expect(within(games).getByText(/Jugó 2 de 4 rondas.*En 1 sesión\./)).toBeInTheDocument();
    expect(within(games).getByRole("cell", { name: "Juego de emparejar" })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/por persona|participante/i);
  });

  it("sin dibujos ni juegos (o con un servidor anterior) no hay secciones", () => {
    data.value["/statistics"] = stats({ drawing: null, games: undefined });
    page();
    expect(screen.queryByRole("region", { name: "Dibujos" })).not.toBeInTheDocument();
    expect(screen.queryByRole("region", { name: "Juegos" })).not.toBeInTheDocument();
  });
});
