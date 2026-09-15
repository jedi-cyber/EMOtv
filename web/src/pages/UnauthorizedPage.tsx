import { Link } from "react-router-dom";

export function UnauthorizedPage() {
  return <section><p className="eyebrow">Acceso restringido</p><h1>No tienes permiso para ingresar</h1><p className="lead">Tu cuenta está autenticada, pero esta sección corresponde a otro rol.</p><Link className="button primary action-link" to="/dashboard">Volver al inicio</Link></section>;
}
