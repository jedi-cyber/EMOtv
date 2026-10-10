import type { PropsWithChildren } from "react";

export type CalloutVariant = "info" | "success" | "warning" | "error";

interface CalloutProps extends PropsWithChildren {
  variant?: CalloutVariant;
  /** Por defecto: alert para errores y status para el resto. */
  role?: "alert" | "status" | "note";
  className?: string;
}

/** Aviso con borde izquierdo de 3 px y fondo -soft del estado. */
export function Callout({ variant = "info", role, className, children }: CalloutProps) {
  return <div className={["callout", `callout-${variant}`, className].filter(Boolean).join(" ")}
    role={role ?? (variant === "error" ? "alert" : "status")}>{children}</div>;
}
