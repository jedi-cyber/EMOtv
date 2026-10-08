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

export function activityOutcomeName(result: string | null | undefined): string {
  if (!result) return "—";
  return activityOutcomeNames[result] ?? result;
}

export function sessionStateName(state: string): string {
  return sessionStateNames[state as SessionState] ?? state;
}
