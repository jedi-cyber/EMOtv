import type { ReactNode } from "react";

interface PageHeaderProps {
  section: string;
  title: string;
  description: string;
  actions?: ReactNode;
}

export function PageHeader({ section, title, description, actions }: PageHeaderProps) {
  return <div className="page-heading">
    <div><p className="eyebrow">{section}</p><h1>{title}</h1><p className="lead">{description}</p></div>
    {actions && <div className="page-heading-actions">{actions}</div>}
  </div>;
}
