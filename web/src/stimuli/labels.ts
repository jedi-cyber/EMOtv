import type { ImageAudience, Stimulus, StimulusIntensity, StimulusKind } from "../api/types";

export const stimulusKindNames: Record<StimulusKind, string> = { emotional: "Emocional", abstract: "Abstracta" };
export const intensityNames: Record<StimulusIntensity, string> = { mild: "Leve", moderate: "Moderada" };
export const audienceNames: Record<ImageAudience, string> = { children: "Para niños", adults: "Para adultos" };

// Expresión que un estímulo emocional espera provocar; se nombra, nunca se colorea.
export const expectedExpressionNames: Record<string, string> = {
  neutral: "Neutral",
  happiness: "Felicidad",
  surprise: "Sorpresa",
  sadness: "Tristeza",
  anger: "Enojo",
  disgust: "Desagrado",
  fear: "Miedo",
  contempt: "Desprecio",
};

// Expresiones que se pueden pedir en un ejercicio de práctica (todas menos desprecio).
export const practiceTargetNames: Record<string, string> = {
  happiness: "Alegría",
  surprise: "Sorpresa",
  sadness: "Tristeza",
  anger: "Enojo",
  fear: "Miedo",
  disgust: "Asco",
  neutral: "Cara tranquila",
};
export const MAX_HOLD_SECONDS = 10;
export const MAX_STEP_SECONDS = 120;

/** Las mismas reglas que valida el servidor, con sus mensajes. */
export function practiceProblem(step: { exposure_seconds: number; hold_seconds?: number | null; target_expression?: string | null }): string | null {
  const hold = step.hold_seconds ?? 0;
  if (!step.target_expression || !(step.target_expression in practiceTargetNames)) return "Una práctica indica la expresión que se pide";
  if (!Number.isInteger(hold) || hold < 1 || hold > MAX_HOLD_SECONDS) return `La expresión se sostiene entre 1 y ${MAX_HOLD_SECONDS} segundos`;
  if (!Number.isInteger(step.exposure_seconds) || step.exposure_seconds < 1 || step.exposure_seconds > MAX_STEP_SECONDS)
    return `La exposición dura entre 1 y ${MAX_STEP_SECONDS} segundos`;
  if (hold >= step.exposure_seconds) return "El tiempo máximo de la práctica es mayor que el tiempo de sostén";
  return null;
}

export function stimulusSummary(item: Stimulus): string {
  if (item.scope === "user") return `Imagen propia · ${audienceNames[item.audience]}`;
  const parts = [stimulusKindNames[item.kind], item.category, intensityNames[item.intensity], `desde ${item.min_age} años`];
  if (item.expected_expression) parts.splice(2, 0, `espera ${expectedExpressionNames[item.expected_expression] ?? item.expected_expression}`);
  return parts.join(" · ");
}
