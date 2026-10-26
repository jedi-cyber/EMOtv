import type { SessionState, SessionType } from "../api/types";

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
  hsemotion_enet_b0_8_best_afew: "HSEmotion",
  hardlyhumans_vit: "HardlyHumans (experimental)",
};

const sessionTypeNames: Record<SessionType, string> = {
  propia: "Conmigo",
  adulto: "Un adulto",
  infantil: "Un niño o niña",
};

/** La única confirmación de cada sesión, según con quién es. */
export const confirmationTexts: Record<SessionType, string> = {
  propia: "Es una sesión mía o cuento con la autorización firmada de la persona adulta",
  adulto: "Es una sesión mía o cuento con la autorización firmada de la persona adulta",
  infantil: "Su tutor autorizó por escrito, está presente y el niño aceptó participar",
};

export function sessionTypeName(type: string | null | undefined): string {
  return sessionTypeNames[(type ?? "propia") as SessionType] ?? "Tipo desconocido";
}

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
