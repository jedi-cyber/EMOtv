import type { ReactNode } from "react";
import type { SessionState } from "../api/types";

export type StatusTone = "success" | "progress" | "neutral" | "error";

/** Estado del sistema: punto de 6 px más texto. Nunca solo color. */
export function StatusChip({ tone, children }: { tone: StatusTone; children: ReactNode }) {
  return <span className={`status-chip status-chip-${tone}`}><span className="status-chip-dot" aria-hidden="true" />{children}</span>;
}

/** Una sesión cancelada no es un error: usa el chip neutro. */
export const sessionStateTone: Record<SessionState, StatusTone> = {
  created: "neutral",
  in_progress: "progress",
  recognized: "progress",
  completed: "success",
  cancelled: "neutral",
};

export function toneForSession(state: string): StatusTone {
  return sessionStateTone[state as SessionState] ?? "neutral";
}
