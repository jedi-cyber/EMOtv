/** Posición dentro de una secuencia de pasos × repeticiones (números desde 1). */
export type StepPosition = { step: number; steps: number; repetition: number; repetitions: number };

/** Convierte el índice global del servidor (0 .. pasos × repeticiones - 1)
 * en "Paso X de Y" dentro de la repetición y "Repetición R de N". */
export function stepPosition(stepIndex: number, stepCount: number, repetitionCount = 1): StepPosition {
  const repetitions = Math.max(1, Math.round(repetitionCount));
  const steps = Math.max(1, Math.round(stepCount / repetitions));
  const index = Math.min(Math.max(0, Math.round(stepIndex)), steps * repetitions - 1);
  return { step: (index % steps) + 1, steps, repetition: Math.floor(index / steps) + 1, repetitions };
}

/** Segundos restantes redondeados hacia arriba para no mostrar "0 s" antes de terminar. */
export function remainingSeconds(seconds: number | null | undefined): number {
  return Math.max(0, Math.ceil((seconds ?? 0) - 1e-6));
}
