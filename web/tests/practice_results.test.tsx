import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { SessionMetrics, SessionPractice, SessionTimeline as Timeline } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import type { UserRole } from "../src/auth/types";
import { SessionTimeline } from "../src/insights/SessionTimeline";
import { StimulusMetrics } from "../src/insights/StimulusMetrics";
import { StatisticsPage } from "../src/pages/StatisticsPage";

const data = vi.hoisted(() => ({ value: {} as Record<string, unknown> }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === null ? null : data.value[path.split("?")[0]] ?? null, loading: false, error: "", reload: vi.fn() }),
}));

const NOTICE = "Los modelos de expresión se entrenaron principalmente con rostros de adultos y su precisión con niños no está validada. El resultado describe el ejercicio, no el estado emocional de la persona.";
const VALUATIONS = /bien hecho|excelente|fracas|falló|mal\b|diagn|patol|preocup/i;
const label = (key: string | null) => key ?? "—";

const practice: SessionPractice = {
  exercises: [
    { step_index: 0, target_expression: "happiness", hold_seconds: 2, max_seconds: 20, outcome: "achieved", seconds_to_achieve: 3.5, peak_level: 0.9, relative_to_calibration: true, feedback_visible: true },
    { step_index: 1, target_expression: "surprise", hold_seconds: 2, max_seconds: 20, outcome: "skipped", seconds_to_achieve: null, peak_level: 0.2, relative_to_calibration: true, feedback_visible: true },
    { step_index: 2, target_expression: "sadness", hold_seconds: 2, max_seconds: 20, outcome: "stopped", seconds_to_achieve: null, peak_level: 0.1, relative_to_calibration: true, feedback_visible: true },
    { step_index: 3, target_expression: "fear", hold_seconds: 2, max_seconds: 20, outcome: null, seconds_to_achieve: null, peak_level: null, relative_to_calibration: null, feedback_visible: null },
  ],
  totals: { exercises: 4, applied: 1, achieved: 1, skipped: 1, stopped: 1, not_reached: 1, average_seconds_to_achieve: 3.5, feedback_visible: 1,
    sentence: "Logró la expresión pedida en 1 de 1 ejercicio.", average_sentence: "Tiempo promedio hasta lograrla: 3,5 s (solo los ejercicios logrados).",
    feedback_sentence: "La señal visual estuvo activa en todos los ejercicios." },
  by_target: [{ target_expression: "happiness", applied: 1, achieved: 1, skipped: 0, stopped: 0, average_seconds_to_achieve: 3.5 }],
  notice: NOTICE,
};
const metrics: SessionMetrics = {
  session_id: "s1", emotional: [], abstract: [], abstract_notice: null, practice,
  totals: { emotional_stimuli: 0, counted: 0, matched: 0, excluded_captures: 0, sentence: "Ningún estímulo emocional tuvo una captura de buena calidad para comparar." },
};

beforeEach(() => { data.value = {}; });

describe("práctica en las métricas de la sesión (detalle, reporte e impresión)", () => {
  it("muestra el aviso fijo, la frase, el promedio y si la señal estuvo activa", () => {
    render(<StimulusMetrics metrics={metrics} expressionLabel={label} />);
    const section = screen.getByRole("region", { name: "Ejercicios de práctica" });
    expect(within(section).getByRole("note")).toHaveTextContent(NOTICE);
    expect(within(section).getByText("Logró la expresión pedida en 1 de 1 ejercicio.")).toBeInTheDocument();
    expect(within(section).getByText(/Tiempo promedio hasta lograrla: 3,5 s/)).toBeInTheDocument();
    expect(within(section).getByText("La señal visual estuvo activa en todos los ejercicios.")).toBeInTheDocument();
    expect(within(section).getByText("No cuentan en el total: 1 se saltó, 1 quedó a medias al detener la sesión, 1 sin aplicar.")).toBeInTheDocument();
    const rows = within(section).getAllByRole("row").slice(1).map((row) => row.textContent);
    expect(rows).toEqual([
      expect.stringMatching(/^1Alegría.*Logró la expresión pedida3[.,]5 sActiva$/),
      expect.stringMatching(/^2SorpresaSe saltó—Activa$/),
      expect.stringMatching(/^3TristezaLa sesión se detuvo—Activa$/),
      expect.stringMatching(/^4MiedoSin aplicar——$/),
    ]);
    expect(document.body.textContent).not.toMatch(VALUATIONS);
    // La coincidencia de estímulos no aparece si no hubo imágenes emocionales.
    expect(screen.queryByText(/coincidió con la esperada/)).not.toBeInTheDocument();
  });

  it("sin ningún logro lo describe sin valorar", () => {
    render(<StimulusMetrics metrics={{ ...metrics, practice: { ...practice, by_target: [], totals: { ...practice.totals, applied: 0, achieved: 0,
      average_seconds_to_achieve: null, average_sentence: null, feedback_sentence: null, sentence: "Ningún ejercicio de práctica llegó a terminar." } } }} expressionLabel={label} />);
    expect(screen.getByText("Ningún ejercicio de práctica llegó a terminar.")).toBeInTheDocument();
    expect(screen.queryByText(/Tiempo promedio/)).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(VALUATIONS);
  });

  it("sin ejercicios no hay sección de práctica", () => {
    render(<StimulusMetrics metrics={{ ...metrics, practice: null }} expressionLabel={label} />);
    expect(screen.queryByRole("region", { name: "Ejercicios de práctica" })).not.toBeInTheDocument();
  });
});

describe("práctica en la línea de tiempo", () => {
  it("cada ejercicio aparece con su resultado", () => {
    const timeline: Timeline = { session_id: "s1", started_at: "2026-10-30T10:00:00Z", duration_seconds: 40, lanes: {
      questionnaires: [], captures: [], said: [], markers: [], heart_rate: [],
      stimuli: [
        { step_index: 0, title: "", kind: "practice", start: 5, end: 12, skipped: false, target_expression: "happiness", outcome: "achieved", seconds_to_achieve: 3 },
        { step_index: 1, title: "", kind: "practice", start: 12, end: 20, skipped: true, target_expression: "surprise", outcome: "skipped", seconds_to_achieve: null },
        { step_index: 2, title: "Paisaje", kind: "emotional", start: 20, end: 28, skipped: false },
      ] } };
    render(<SessionTimeline timeline={timeline} expressionLabel={label} eventsOpen />);
    expect(screen.getByText("Ejercicio de práctica: Alegría · logró la expresión pedida a los 3 s")).toBeInTheDocument();
    expect(screen.getByText("Ejercicio de práctica: Sorpresa · se saltó")).toBeInTheDocument();
    expect(screen.getByText("Aparece el estímulo «Paisaje»")).toBeInTheDocument();
  });
});

describe("práctica en las estadísticas", () => {
  function withUser(role: UserRole) {
    return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role, is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
      <MemoryRouter><StatisticsPage /></MemoryRouter>
    </AuthContext.Provider>);
  }
  const row = { applied: 3, achieved: 2, skipped: 1, stopped: 0, average_seconds_to_achieve: 3 };
  const stats = (practiceChanges: Record<string, unknown> = {}) => ({
    scope: "mine", notice: "", few_sessions: false, few_sessions_notice: null,
    sessions: { total: 3, completed: 3, interrupted: 0, average_duration_seconds: 120 },
    expressions: { counted_captures: 0, excluded_captures: 0, rows: [] },
    coincidence: { compared: 4, matched: 1 }, protocols: [], questionnaires: [], questionnaire: null,
    practice: { sessions: 3, notice: NOTICE,
      totals: { ...row, feedback_visible: 2, sentence: "Logró la expresión pedida en 2 de 3 ejercicios.",
        average_sentence: "Tiempo promedio hasta lograrla: 3 s (solo los ejercicios logrados).", feedback_sentence: "La señal visual estuvo activa en 2 de 3 ejercicios." },
      by_protocol: [{ ...row, family_id: "f1", name: "Alegría y sorpresa", sessions: 2 }],
      by_target: [{ ...row, target_expression: "happiness" }], ...practiceChanges },
  });

  it("muestra las métricas de práctica aparte de la coincidencia de estímulos", () => {
    data.value["/statistics"] = stats();
    withUser("student");
    const section = screen.getByRole("region", { name: "Ejercicios de práctica" });
    expect(within(section).getByRole("note")).toHaveTextContent(NOTICE);
    expect(within(section).getByText("Logró la expresión pedida en 2 de 3 ejercicios. En 3 sesiones.")).toBeInTheDocument();
    expect(within(section).getByText("La señal visual estuvo activa en 2 de 3 ejercicios.")).toBeInTheDocument();
    expect(within(section).getByRole("cell", { name: "Alegría" })).toBeInTheDocument();
    expect(within(section).getByRole("cell", { name: "Alegría y sorpresa" })).toBeInTheDocument();
    expect(within(section).queryByText(/coincidió/)).not.toBeInTheDocument();
    expect(within(section).queryByText("Por usuario del grupo")).not.toBeInTheDocument();
    expect(screen.getByText("En 1 de 4 estímulos emocionales la expresión estimada coincidió con la esperada.")).toBeInTheDocument();
  });

  it("el docente ve los ejercicios por usuario de su grupo", () => {
    data.value["/statistics"] = { ...stats({ by_user: [{ ...row, email: "usuario1@example.com" }] }), scope: "group", by_user: [] };
    withUser("psychologist");
    const section = screen.getByRole("region", { name: "Ejercicios de práctica" });
    expect(within(section).getByText("Por usuario del grupo")).toBeInTheDocument();
    expect(within(section).getByRole("cell", { name: "usuario1@example.com" })).toBeInTheDocument();
  });

  it("sin ejercicios no hay sección de práctica", () => {
    data.value["/statistics"] = { ...stats(), practice: null };
    withUser("student");
    expect(screen.queryByRole("region", { name: "Ejercicios de práctica" })).not.toBeInTheDocument();
  });
});
