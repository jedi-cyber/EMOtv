import { paths } from "../routes/paths";
import { ButtonLink } from "../components/Button";

export function NotFoundPage() {
  return <section><h1>Página no encontrada</h1><p className="lead">No encontramos la página que buscas. Puedes volver al inicio y elegir una sección del menú.</p><ButtonLink variant="primary" to={paths.dashboard}>Volver al inicio</ButtonLink></section>;
}
