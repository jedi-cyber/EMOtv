import { Link } from "react-router-dom";
import { paths } from "../routes/paths";

export function NotFoundPage() {
  return <section><p className="eyebrow">Navegación</p><h1>Página no encontrada</h1><p className="lead">No encontramos la página que buscas. Puedes volver al inicio y elegir una sección del menú.</p><Link className="button primary action-link" to={paths.dashboard}>Volver al inicio</Link></section>;
}
