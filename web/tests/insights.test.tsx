import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SessionMetrics, SessionTimeline as Timeline } from "../src/api/types";
import { SessionTimeline } from "../src/insights/SessionTimeline";
import { StimulusMetrics } from "../src/insights/StimulusMetrics";

const NOTICE = "Registro descriptivo. Una sesión breve no permite sacar conclusiones a partir de una imagen.";
const labels: Record<string, string> = { happiness: "Felicidad", sadness: "Tristeza", neutral: "Neutral" };
const label = (key: string | null) => (key ? labels[key] ?? key : "—");
const VALUATIONS = /anormal|mejor|peor|preocup|diagn|riesgo|patol/i;

const timeline: Timeline = {
  session_id: "s1", started_at: "2026-10-22T10:00:00Z", duration_seconds: 40,
  lanes: {
    questionnaires: [{ time: 2, moment: "pre", title: "Al llegar", answers: [{ question: "¿Cómo estás?", kind: "faces", answer: 4 }] }],
    stimuli: [{ step_index: 0, title: "Paisaje", kind: "emotional", start: 10, end: 16, skipped: false },
      { step_index: 1, title: "Forma", kind: "abstract", start: 16, end: 24, skipped: true }],
    captures: [{ time: 12, step_index: 0, emotion: "happiness", probability: 0.8, quality: "good" },
      { time: 18, step_index: 1, emotion: "neutral", probability: 0.5, quality: "flagged" }],
    said: [{ time: 19, step_index: 1, title: "Forma", text: "Una nube" }],
    markers: [{ time: 13, kind: "laughed", note: null }],
    heart_rate: [],
  },
};

const metrics: SessionMetrics = {
  session_id: "s1",
  emotional: [
    { step_index: 0, title: "Paisaje", category: "Naturaleza", skipped: false, expected_expression: "happiness", counted: true, matches_expected: true, excluded_captures: 0,
      captures: [{ id: "c1", captured_at: "", emotion: "happiness", probability: 0.8, seconds_since_stimulus: 2, quality: "good", quality_issues: [], counted: true, matches_expected: true }] },
    { step_index: 1, title: "Lluvia", category: "Naturaleza", skipped: false, expected_expression: "sadness", counted: false, matches_expected: null, excluded_captures: 1,
      captures: [{ id: "c2", captured_at: "", emotion: "sadness", probability: 0.4, seconds_since_stimulus: 2, quality: "flagged", quality_issues: ["too_dark"], counted: false, matches_expected: true }] },
  ],
  abstract: [{ step_index: 2, title: "Forma", category: "Manchas", skipped: false, said: "Una nube",
    captures: [{ id: "c3", captured_at: "", emotion: "neutral", probability: 0.6, seconds_since_stimulus: 3, quality: "good", quality_issues: [], counted: true }] }],
  totals: { emotional_stimuli: 2, counted: 1, matched: 1, excluded_captures: 1, sentence: "En 1 de 1 estímulo la expresión estimada coincidió con la esperada." },
  abstract_notice: NOTICE,
};

describe("línea de tiempo y métricas", () => {
  it("pone cada fuente en un solo eje y reserva el carril del ritmo cardíaco", () => {
    render(<SessionTimeline timeline={timeline} expressionLabel={label} />);
    for (const lane of ["Cuestionarios", "Estímulos", "Expresión estimada", "Lo que dijo ver", "Marcadores", "Ritmo cardíaco"]) {
      expect(screen.getByText(lane)).toBeInTheDocument();
    }
    expect(screen.getByText("Sin sensor conectado (reservado)")).toBeInTheDocument();
    const events = within(screen.getByRole("list")).getAllByRole("listitem").map((item) => item.textContent);
    expect(events).toEqual([
      "0:02 Cuestionario previo «Al llegar»: ¿Cómo estás? 4",
      "0:10 Aparece el estímulo «Paisaje»",
      "0:12 Captura: Felicidad (estimada)",
      "0:13 Se rió",
      "0:16 Aparece el estímulo «Forma» (se saltó)",
      "0:18 Captura: Neutral (estimada), marcada por calidad",
      "0:19 Dijo ver en «Forma»: Una nube",
    ]);
  });

  it("muestra las capturas marcadas sin contarlas y las abstractas sin coincidencia y con el aviso", () => {
    render(<StimulusMetrics metrics={metrics} expressionLabel={label} />);
    expect(screen.getByText("En 1 de 1 estímulo la expresión estimada coincidió con la esperada.")).toBeInTheDocument();
    expect(screen.getByText(/1 captura marcada por calidad se muestra/)).toBeInTheDocument();
    expect(screen.getByText("Marcada: poca luz")).toBeInTheDocument();
    expect(screen.getByText("(no cuenta)")).toBeInTheDocument();
    expect(screen.getByText(NOTICE)).toBeInTheDocument();
    const abstract = screen.getByText("Forma").closest("li") as HTMLElement;
    expect(abstract).toHaveTextContent("Dijo ver: «Una nube»");
    expect(abstract.textContent).not.toMatch(/coincid|esperada/i);
    expect(document.body.textContent).not.toMatch(VALUATIONS);
  });
});
