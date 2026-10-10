import { paths } from "../routes/paths";
import { ButtonLink } from "../components/Button";

export function UnauthorizedPage() {
  return <section><h1>No tienes acceso a esta página</h1><p className="lead">Esta sección no está disponible para tu cuenta. Vuelve al inicio para continuar.</p><ButtonLink variant="primary" to={paths.dashboard}>Volver al inicio</ButtonLink></section>;
}
