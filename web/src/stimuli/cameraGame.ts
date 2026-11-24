import type { ProtocolStep } from "../api/types";
import { cameraTargets } from "./labels";

/**
 * Juego con cámara «Muestra la emoción» en el editor: un bloque de rondas
 * seguidas, cada una una práctica sin imagen con su número (game_round). El
 * editor lo muestra y lo mueve como un solo paso; el servidor valida el bloque.
 */

export const CAMERA_GAME = { rounds: 5, hold_seconds: 2, exposure_seconds: 20 };

/** Emociones al azar entre las cinco que estima EMOtv, sin repetir la de la ronda anterior. */
export function cameraGameTargets(rounds: number, random: () => number = Math.random): string[] {
  const targets: string[] = [];
  for (let index = 0; index < rounds; index += 1) {
    const options = cameraTargets.filter((key) => key !== targets.at(-1));
    targets.push(options[Math.floor(random() * options.length)]);
  }
  return targets;
}

export function cameraGameSteps(rounds: number, hold: number = CAMERA_GAME.hold_seconds,
  seconds: number = CAMERA_GAME.exposure_seconds, random: () => number = Math.random): ProtocolStep[] {
  return cameraGameTargets(rounds, random).map((target, index) => ({
    kind: "practice", stimulus_id: null, target_expression: target, hold_seconds: hold, exposure_seconds: seconds,
    game_round: index + 1, capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false,
  }));
}

/** El tramo [inicio, fin) del elemento que contiene el paso: el bloque entero de un juego con cámara, o el paso solo. */
export function itemRange(steps: ProtocolStep[], index: number): [number, number] {
  if (!steps[index]?.game_round) return [index, index + 1];
  let start = index;
  while (start > 0 && (steps[start].game_round ?? 0) > 1 && steps[start - 1].game_round === (steps[start].game_round ?? 0) - 1) start -= 1;
  let end = index + 1;
  while (end < steps.length && steps[end].game_round === (steps[end - 1].game_round ?? 0) + 1) end += 1;
  return [start, end];
}

/** Sube (offset −1) o baja (+1) el elemento entero, saltando el elemento vecino entero. */
export function moveItem(steps: ProtocolStep[], index: number, offset: -1 | 1): ProtocolStep[] {
  const [start, end] = itemRange(steps, index);
  if (offset < 0 ? start === 0 : end >= steps.length) return steps;
  const [otherStart, otherEnd] = itemRange(steps, offset < 0 ? start - 1 : end);
  const item = steps.slice(start, end);
  const other = steps.slice(otherStart, otherEnd);
  return offset < 0
    ? [...steps.slice(0, otherStart), ...item, ...other, ...steps.slice(end)]
    : [...steps.slice(0, start), ...other, ...item, ...steps.slice(otherEnd)];
}

export function removeItem(steps: ProtocolStep[], index: number): ProtocolStep[] {
  const [start, end] = itemRange(steps, index);
  return [...steps.slice(0, start), ...steps.slice(end)];
}

/** Reemplaza el bloque que empieza en index por otros pasos (por ejemplo, con otras rondas). */
export function replaceItem(steps: ProtocolStep[], index: number, next: ProtocolStep[]): ProtocolStep[] {
  const [start, end] = itemRange(steps, index);
  return [...steps.slice(0, start), ...next, ...steps.slice(end)];
}
