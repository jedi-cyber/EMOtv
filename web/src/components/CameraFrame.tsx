import type { ReactNode } from "react";

interface CameraFrameProps {
  /** La expresión se mantiene estable y puede registrarse: las marcas se cierran y pasan a trazo continuo. */
  stable?: boolean;
  /** dark: video o fondo oscuro (frame-on-dark); light: fondo claro (primary). */
  tone?: "dark" | "light";
  className?: string;
  children: ReactNode;
}

/** Encuadre de cámara: cuatro marcas en L que indican que EMOtv está observando o registrando. */
export function CameraFrame({ stable = false, tone = "dark", className, children }: CameraFrameProps) {
  return <div className={["camera-frame", `camera-frame-${tone}`, stable ? "is-stable" : "", className ?? ""].filter(Boolean).join(" ")}
    data-stable={stable ? "true" : "false"}>
    {children}
    <span className="frame-mark frame-mark-tl" aria-hidden="true" />
    <span className="frame-mark frame-mark-tr" aria-hidden="true" />
    <span className="frame-mark frame-mark-bl" aria-hidden="true" />
    <span className="frame-mark frame-mark-br" aria-hidden="true" />
  </div>;
}
