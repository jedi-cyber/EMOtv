import type { ExamState, ExamStation } from "../api/types";
import type { StatusTone } from "../components/StatusChip";

export const examStateNames: Record<ExamState, string> = {
  open: "Abierto",
  in_progress: "En curso",
  closed: "Terminado",
};

export const examStateTone: Record<ExamState, StatusTone> = {
  open: "neutral",
  in_progress: "progress",
  closed: "success",
};

/** Estado de una estación en palabras: nunca su expresión. */
export function stationStatus(station: ExamStation): { text: string; tone: StatusTone } {
  if (!station.consent_confirmed && !station.finished) return { text: "Espera el consentimiento", tone: "neutral" };
  switch (station.phase) {
    case "waiting": return { text: "Espera el consentimiento", tone: "neutral" };
    case "calibration": return { text: "Calibrando", tone: "progress" };
    case "ready": return { text: "Lista", tone: "success" };
    case "exam": return { text: "Registrando", tone: "progress" };
    case "stopped": return { text: "Se detuvo", tone: "neutral" };
    default: return { text: station.finished ? "Terminó" : "Conectando", tone: station.finished ? "success" : "neutral" };
  }
}

export function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("es-PE", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}
