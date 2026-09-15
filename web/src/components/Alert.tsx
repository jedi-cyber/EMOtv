import type { PropsWithChildren } from "react";

interface AlertProps extends PropsWithChildren {
  variant?: "info" | "success" | "error";
}

export function Alert({ variant = "info", children }: AlertProps) {
  return <div className={`alert alert-${variant}`} role={variant === "error" ? "alert" : "status"}>{children}</div>;
}
