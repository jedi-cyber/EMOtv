import { Link } from "react-router-dom";
import { paths } from "../routes/paths";

export function UnauthorizedPage() {
  return <section><p className="eyebrow">Acceso restringido</p><h1>No tienes acceso a esta página</h1><p className="lead">Esta sección no está disponible para tu cuenta. Vuelve al inicio para continuar.</p><Link className="button primary action-link" to={paths.dashboard}>Volver al inicio</Link></section>;
}
