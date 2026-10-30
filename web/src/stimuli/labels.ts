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

export function stimulusSummary(item: Stimulus): string {
  if (item.scope === "user") return `Imagen propia · ${audienceNames[item.audience]}`;
  const parts = [stimulusKindNames[item.kind], item.category, intensityNames[item.intensity], `desde ${item.min_age} años`];
  if (item.expected_expression) parts.splice(2, 0, `espera ${expectedExpressionNames[item.expected_expression] ?? item.expected_expression}`);
  return parts.join(" · ");
}
