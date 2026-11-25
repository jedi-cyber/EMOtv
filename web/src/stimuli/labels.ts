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

// Nombre de cada emoción en las actividades (práctica, reconocimiento, dibujo y juegos).
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
// Las cinco expresiones que estima EMOtv con la cámara: las únicas que piden la
// práctica y «Haz la misma cara» (igual que CAMERA_PRACTICE_TARGETS del servidor).
export const cameraTargets = ["happiness", "surprise", "sadness", "anger", "neutral"];
export const CAMERA_TARGET_PROBLEM = "Los ejercicios con cámara piden una de las cinco expresiones que estima EMOtv: cara tranquila, alegría, sorpresa, tristeza o enojo";
export const isCameraTarget = (key: string | null | undefined) => key != null && cameraTargets.includes(key);
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
/** «Usar el analizador»: quien conduce lo termina; esto es solo su tiempo máximo. */
export const ANALYZER_SECONDS = 180;
export const MAX_ANALYZER_SECONDS = 600;
/** Juego de emparejar: pocas opciones al empezar; quien arma el protocolo sube la dificultad. */
export const DEFAULT_GAME = { rounds: 3, option_count: 2, exposure_seconds: 30 };
export const MIN_GAME_ROUNDS = 2;
export const MAX_GAME_ROUNDS = 6;

/** Nombre de cada juego, para títulos y listas. */
export const gameTypeNames: Record<string, string> = {
  matching: "Juego de emparejar",
  similar: "Juego: busca la misma emoción",
};

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
  if (!isCameraTarget(step.target_expression)) return CAMERA_TARGET_PROBLEM;
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
  const analyzers = steps.filter((step) => step.kind === "analyzer").length;
  const images = steps.length - practices - recognitions - drawings - games - analyzers;
  const parts = [];
  if (images > 0 || practices + recognitions + drawings + games + analyzers === 0) parts.push(`${images} ${images === 1 ? "imagen" : "imágenes"}`);
  if (practices > 0) parts.push(`${practices} ${practices === 1 ? "ejercicio de práctica" : "ejercicios de práctica"}`);
  if (recognitions > 0) parts.push(`${recognitions} ${recognitions === 1 ? "reconocimiento" : "reconocimientos"}`);
  if (drawings > 0) parts.push(`${drawings} ${drawings === 1 ? "dibujo" : "dibujos"}`);
  if (games > 0) parts.push(`${games} ${games === 1 ? "juego" : "juegos"}`);
  if (analyzers > 0) parts.push(`${analyzers} ${analyzers === 1 ? "paso con el analizador" : "pasos con el analizador"}`);
  return parts;
}

export function stimulusSummary(item: Stimulus): string {
  if (item.scope === "user") return `Imagen propia · ${audienceNames[item.audience]}`;
  const parts = [stimulusKindNames[item.kind], item.category, intensityNames[item.intensity], `desde ${item.min_age} años`];
  if (item.expected_expression) parts.splice(2, 0, `espera ${expectedExpressionNames[item.expected_expression] ?? item.expected_expression}`);
  return parts.join(" · ");
}

function seconds(value: number) { return `${value} s`; }

/** Una línea por paso para la vista previa de un protocolo: qué se aplica, sin
 * resultados. Las rondas seguidas del juego con cámara se cuentan como un solo juego. */
export function protocolStepLines(steps: ProtocolStep[], titleOf: (id: string) => string | undefined): string[] {
  const lines: string[] = [];
  const image = (id: string | null | undefined) => {
    const title = id ? titleOf(id) : undefined;
    return title ? `«${title}»` : "una imagen";
  };
  const target = (key: string | null | undefined) => (key ? practiceTargetNames[key] ?? key : "").toLowerCase();
  for (let index = 0; index < steps.length; index += 1) {
    const step = steps[index];
    if (step.kind === "practice" && step.game_round != null) {
      let rounds = 1;
      while (steps[index + 1]?.kind === "practice" && (steps[index + 1].game_round ?? 0) > 1) { rounds += 1; index += 1; }
      lines.push(`Juego con cámara «Muestra la emoción»: ${rounds} rondas`);
    } else if (step.kind === "practice" && step.conductor_rating) {
      lines.push(`Juego: imita la cara con ${image(step.stimulus_id)} · quien conduce valora de 1 a 5 estrellas`);
    } else if (step.kind === "practice" && step.imitate) {
      lines.push(`Haz la misma cara que ${image(step.stimulus_id)} · ${seconds(step.exposure_seconds)}`);
    } else if (step.kind === "practice") {
      lines.push(`Práctica: muestra ${target(step.target_expression)} · ${seconds(step.exposure_seconds)}`);
    } else if (step.kind === "recognition") {
      lines.push(`¿Qué emoción es? con ${image(step.stimulus_id)}${step.situation ? " y una historia" : ""} · ${step.option_count ?? DEFAULT_RECOGNITION.option_count} opciones`);
    } else if (step.kind === "drawing") {
      lines.push(`Dibujo${step.stimulus_id ? ` mirando ${image(step.stimulus_id)}` : ""} · ${seconds(step.exposure_seconds)}`);
    } else if (step.kind === "analyzer") {
      lines.push(`Usar el analizador: tú pides las expresiones · hasta ${seconds(step.exposure_seconds)}`);
    } else if (step.kind === "game") {
      lines.push(`${gameTypeNames[step.game_type ?? "matching"] ?? "Juego"}: ${step.rounds ?? DEFAULT_GAME.rounds} rondas${step.show_expression ? ", luego muestra la emoción" : ""}`);
    } else {
      lines.push(`Imagen ${image(step.stimulus_id)} · ${seconds(step.exposure_seconds)}`);
    }
  }
  return lines;
}
