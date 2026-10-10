import type { SessionState } from "../api/types";

export const sessionStateNames: Record<SessionState, string> = {
  created: "Creada",
  in_progress: "En progreso",
  recognized: "Expresión registrada",
  completed: "Completada",
  cancelled: "Cancelada",
};

// Resultado de la actividad corporal (exercise_result), independiente de la expresión registrada.
const activityOutcomeNames: Record<string, string> = {
  completed: "Completada",
  skipped: "Omitida",
  cancelled: "Cancelada",
};

// Nombres legibles de los modelos; la clave técnica nunca se muestra.
const emotionModelNames: Record<string, string> = {
  ferplus_onnx: "FER+",
  hardlyhumans_vit: "HardlyHumans (experimental)",
};

export function activityOutcomeName(result: string | null | undefined): string {
  if (!result) return "—";
  return activityOutcomeNames[result] ?? "Sin resultado";
}

export function sessionStateName(state: string): string {
  return sessionStateNames[state as SessionState] ?? "Estado desconocido";
}

export function emotionModelName(modelId: string | null | undefined): string {
  if (!modelId) return "No registrado";
  return emotionModelNames[modelId] ?? "Otro modelo";
}
