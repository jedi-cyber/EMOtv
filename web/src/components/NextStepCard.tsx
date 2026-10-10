import type { ReactNode } from "react";

interface NextStepCardProps {
  title: string;
  children: ReactNode;
  /** Un único botón principal. */
  action: ReactNode;
}

/** Tarjeta de próximo paso: fondo navy, una por página y solo en Inicio. */
export function NextStepCard({ title, children, action }: NextStepCardProps) {
  return <section className="next-step-card" aria-labelledby="next-step-title">
    <h2 id="next-step-title">{title}</h2>
    <div className="next-step-body">{children}</div>
    <div className="next-step-action">{action}</div>
  </section>;
}
