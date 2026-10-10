import type { AnchorHTMLAttributes, ButtonHTMLAttributes } from "react";
import { Link, type LinkProps } from "react-router-dom";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";
type ButtonSize = "md" | "sm";

interface Look {
  variant?: ButtonVariant;
  size?: ButtonSize;
}

function buttonClass({ variant = "secondary", size = "md" }: Look, extra?: string) {
  return ["button", variant, size === "sm" ? "small" : "", extra ?? ""].filter(Boolean).join(" ");
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, Look {
  /** Mantiene el texto y añade un indicador; el botón queda deshabilitado sin cambiar de tamaño. */
  loading?: boolean;
}

/** Acción en la página (DESIGN.md: primary, secondary, ghost, danger). */
export function Button({ variant, size, loading = false, disabled, className, children, type = "button", ...rest }: ButtonProps) {
  return <button {...rest} type={type} className={buttonClass({ variant, size }, className)}
    disabled={disabled || loading} aria-busy={loading || undefined}>
    {loading && <span className="button-spinner" aria-hidden="true" />}
    {children}
  </button>;
}

/** Navegación con apariencia de botón: sigue siendo un enlace para el lector de pantalla. */
export function ButtonLink({ variant, size, className, ...rest }: LinkProps & Look) {
  return <Link {...rest} className={buttonClass({ variant, size }, className)} />;
}

/** Igual que ButtonLink para anclas dentro de la página o documentos externos. */
export function ButtonAnchor({ variant, size, className, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement> & Look) {
  return <a {...rest} className={buttonClass({ variant, size }, className)} />;
}
