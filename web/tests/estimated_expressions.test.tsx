import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { SessionMetrics } from "../src/api/types";
import { StimulusMetrics } from "../src/insights/StimulusMetrics";
import { cameraTargets, practiceProblem } from "../src/stimuli/labels";

// EMOtv estima cinco expresiones con la cámara: neutral, felicidad, sorpresa,
// tristeza y enojo. Asco, miedo y desprecio quedan para los pasos sin cámara.

describe("cinco expresiones estimadas", () => {
  it("la práctica solo pide las cinco expresiones que estima EMOtv", () => {
    expect(cameraTargets).toEqual(["happiness", "surprise", "sadness", "anger", "neutral"]);
    const step = { exposure_seconds: 20, hold_seconds: 2 };
    expect(practiceProblem({ ...step, target_expression: "anger" })).toBeNull();
    for (const target of ["fear", "disgust", "contempt"])
      expect(practiceProblem({ ...step, target_expression: target })).toMatch(/cinco expresiones que estima EMOtv/);
  });

  it("una imagen de miedo se muestra, pero no se compara", () => {
    const capture = { id: "c1", captured_at: "2026-11-23T10:00:00Z", emotion: "surprise", probability: 0.8,
      seconds_since_stimulus: 2, quality: "good", quality_issues: [], counted: true };
    const metrics = {
      session_id: "s1", abstract: [], abstract_notice: null,
      emotional: [{ step_index: 0, stimulus_id: "e1", title: "Cara de miedo", category: "c", skipped: false,
        expected_expression: "fear", comparable: false, captures: [capture], counted: false, matches_expected: null,
        excluded_captures: 0 }],
      totals: { emotional_stimuli: 1, not_comparable: 1, counted: 0, matched: 0, excluded_captures: 0,
        sentence: "Ningún estímulo emocional tuvo una captura de buena calidad para comparar." },
    } as unknown as SessionMetrics;
    render(<StimulusMetrics metrics={metrics} expressionLabel={(key) => key ?? "—"} />);
    expect(screen.getByText(/no se comparan: EMOtv solo estima neutral, felicidad, sorpresa, tristeza y enojo/)).toBeInTheDocument();
    expect(screen.getByText("No se compara")).toBeInTheDocument();
  });
});
