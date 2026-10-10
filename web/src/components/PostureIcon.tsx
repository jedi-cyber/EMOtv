import type { ReactNode } from "react";

/** Silueta simple de cada postura (SVG propio, sin librerías de iconos). */
const figures: Record<string, ReactNode> = {
  arms_up: <><path d="M12 8v6M12 14l-3 7M12 14l3 7M12 9 8 3M12 9l4-6" /></>,
  arms_open: <><path d="M12 8v6M12 14l-3 7M12 14l3 7M4 9h16" /></>,
  arms_forward: <><path d="M12 8v6M12 14l-3 7M12 14l3 7M12 9h8M12 11h8" /></>,
  hands_on_hips: <><path d="M12 8v6M12 14l-3 7M12 14l3 7M12 9l-4 2 3 3M12 9l4 2-3 3" /></>,
  squat: <><path d="M11 7l1 6M12 13l4 1-1 6M12 13l-1 7M11 9h8" /></>,
};

export const postureNames: Record<string, string> = {
  arms_up: "Brazos arriba",
  arms_open: "Brazos abiertos",
  arms_forward: "Brazos al frente",
  hands_on_hips: "Manos en las caderas",
  squat: "Sentadilla",
};

export function postureName(posture: string): string {
  return postureNames[posture] ?? "Postura";
}

export function PostureIcon({ posture }: { posture: string }) {
  return <svg className="nav-icon posture-icon" aria-hidden="true" focusable="false" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <circle cx={posture === "squat" ? 11 : 12} cy={posture === "squat" ? 4.5 : 5} r="2" />
    {figures[posture] ?? figures.arms_open}
  </svg>;
}
