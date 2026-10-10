import type { InputHTMLAttributes, ReactNode } from "react";

interface CheckboxProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  children: ReactNode;
}

/** Casilla nativa de 20 px con apariencia propia; todo el texto es parte de la etiqueta. */
export function Checkbox({ children, className, ...input }: CheckboxProps) {
  return <label className={["checkbox", className].filter(Boolean).join(" ")}>
    <input type="checkbox" {...input} />
    <span>{children}</span>
  </label>;
}
