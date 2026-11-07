import type { ImageAudience, ProtocolStep, Stimulus, StimulusIntensity, StimulusKind } from "../api/types";

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

// Expresiones que se pueden pedir en un ejercicio de práctica: todo el catálogo.
export const practiceTargetNames: Record<string, string> = {
  happiness: "Alegría",
  surprise: "Sorpresa",
  sadness: "Tristeza",
  anger: "Enojo",
  fear: "Miedo",
  disgust: "Asco",
  neutral: "Cara tranquila",
  contempt: "Desprecio",
};
// Lo que propone el editor si el servidor no responde (PRACTICE_HOLD_SECONDS y PRACTICE_MAX_SECONDS).
export const DEFAULT_PRACTICE = { hold_seconds: 2, max_seconds: 20 };
export const MAX_HOLD_SECONDS = 10;
export const MAX_STEP_SECONDS = 120;
// Reconocimiento («¿Qué emoción es?»): opciones y tiempo para responder que propone el editor.
export const RECOGNITION_OPTION_COUNTS = [2, 3, 4];
export const DEFAULT_RECOGNITION = { option_count: 3, max_seconds: 15 };
// Historia corta de una situación («A Lucía se le cayó su helado»); el servidor valida lo mismo.
export const MAX_SITUATION_CHARS = 200;
// Modo accesible: el editor propone menos opciones y más tiempo para cada paso nuevo.
export const ACCESSIBLE_RECOGNITION = { option_count: 2, max_seconds: 30 };
export const ACCESSIBLE_TIME_FACTOR = 2;
// Dibujo: tiempo para dibujar que propone el editor (el máximo en el modo accesible).
export const DRAWING_SECONDS = 90;
/** Juego de emparejar: pocas opciones al empezar; quien arma el protocolo sube la dificultad. */
export const DEFAULT_GAME = { rounds: 3, option_count: 2, exposure_seconds: 30 };
export const MIN_GAME_ROUNDS = 2;
export const MAX_GAME_ROUNDS = 6;

/** Lo que ocurrió en un juego, sin puntaje (igual que el servidor). */
export function gameSentence(item: { rounds_total: number; rounds_done: number; matched: number; first_try: number; help_used: number }) {
  const helped = item.help_used === 0 ? "no usó la ayuda" : `usó la ayuda ${item.help_used} ${item.help_used === 1 ? "vez" : "veces"}`;
  return `Jugó ${item.rounds_done} de ${item.rounds_total} ${item.rounds_total === 1 ? "ronda" : "rondas"}. Emparejó ${item.matched} ${item.matched === 1 ? "imagen" : "imágenes"}, ${item.first_try} a la primera; ${helped}.`;
}
// Pictograma que acompaña al nombre de cada emoción en el modo accesible. Es un
// apoyo visual del nombre, no una imagen de la persona ni de lo detectado.
export const emotionPictograms: Record<string, string> = {
  happiness: "😊",
  sadness: "😢",
  anger: "😠",
  fear: "😨",
  surprise: "😮",
  disgust: "🤢",
  neutral: "😐",
  contempt: "😒",
};

/** Un reconocimiento usa una imagen emocional con su expresión esperada: esa es la respuesta. */
export function recognizable(item: Stimulus | undefined): boolean {
  return item != null && item.kind === "emotional" && item.expected_expression != null;
}

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

/** Qué tiene un protocolo, sin llamar «imagen» a un ejercicio: ["1 imagen", "2 ejercicios de práctica"]. */
export function protocolStepParts(steps: Pick<ProtocolStep, "kind">[]): string[] {
  const practices = steps.filter((step) => step.kind === "practice").length;
  const recognitions = steps.filter((step) => step.kind === "recognition").length;
  const drawings = steps.filter((step) => step.kind === "drawing").length;
  const games = steps.filter((step) => step.kind === "game").length;
  const images = steps.length - practices - recognitions - drawings - games;
  const parts = [];
  if (images > 0 || practices + recognitions + drawings + games === 0) parts.push(`${images} ${images === 1 ? "imagen" : "imágenes"}`);
  if (practices > 0) parts.push(`${practices} ${practices === 1 ? "ejercicio de práctica" : "ejercicios de práctica"}`);
  if (recognitions > 0) parts.push(`${recognitions} ${recognitions === 1 ? "reconocimiento" : "reconocimientos"}`);
  if (drawings > 0) parts.push(`${drawings} ${drawings === 1 ? "dibujo" : "dibujos"}`);
  if (games > 0) parts.push(`${games} ${games === 1 ? "juego" : "juegos"}`);
  return parts;
}

export function stimulusSummary(item: Stimulus): string {
  if (item.scope === "user") return `Imagen propia · ${audienceNames[item.audience]}`;
  const parts = [stimulusKindNames[item.kind], item.category, intensityNames[item.intensity], `desde ${item.min_age} años`];
  if (item.expected_expression) parts.splice(2, 0, `espera ${expectedExpressionNames[item.expected_expression] ?? item.expected_expression}`);
  return parts.join(" · ");
}
