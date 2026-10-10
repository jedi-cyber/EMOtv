import type { HTMLAttributes, ReactNode } from "react";

type CardElement = "div" | "section" | "article" | "li" | "form";

interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: CardElement;
}

/** Agrupa información relacionada. La tarjeta no es clicable; su acción va como botón al final. */
export function Card({ as: Element = "div", className, ...rest }: CardProps) {
  return <Element {...(rest as HTMLAttributes<HTMLElement>)} className={["card", className].filter(Boolean).join(" ")} />;
}

interface CardWithHeaderProps {
  icon: ReactNode;
  /** Chip opcional a la derecha de la banda (versión o cantidad). */
  badge?: ReactNode;
  title: ReactNode;
  titleLevel?: 2 | 3;
  meta?: ReactNode;
  status?: ReactNode;
  actions?: ReactNode;
  children?: ReactNode;
  className?: string;
}

/** Elemento que se elige o revisa uno por uno: banda navy de 104 px, título, metadatos, estado y acciones. */
export function CardWithHeader({ icon, badge, title, titleLevel = 2, meta, status, actions, children, className }: CardWithHeaderProps) {
  const Heading = titleLevel === 2 ? "h2" : "h3";
  return <article className={["card-with-header", className].filter(Boolean).join(" ")}>
    <div className="card-with-header-band">
      <span className="card-with-header-icon" aria-hidden="true">{icon}</span>
      {badge && <span className="card-with-header-badge">{badge}</span>}
    </div>
    <div className="card-with-header-body">
      <Heading className="card-title">{title}</Heading>
      {meta && <div className="card-meta">{meta}</div>}
      {status && <div className="card-status">{status}</div>}
      {children}
      {actions && <div className="card-actions">{actions}</div>}
    </div>
  </article>;
}
