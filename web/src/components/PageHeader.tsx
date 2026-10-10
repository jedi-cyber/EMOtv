import type { ReactNode } from "react";

interface PageHeaderProps {
  title: ReactNode;
  description?: ReactNode;
  actions?: ReactNode;
}

/** Título y subtítulo de la página, sin etiqueta en mayúsculas encima (DESIGN.md). */
export function PageHeader({ title, description, actions }: PageHeaderProps) {
  return <div className="page-heading">
    <div><h1>{title}</h1>{description && <p className="lead">{description}</p>}</div>
    {actions && <div className="page-heading-actions">{actions}</div>}
  </div>;
}
