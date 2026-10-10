import { paths } from "../routes/paths";
import { Button, ButtonLink } from "../components/Button";

export function ConnectionErrorPage() {
  return <section><h1>No podemos comunicarnos con EMOtv</h1><p className="lead">El servicio no responde en este momento. Comprueba tu conexión y vuelve a intentarlo. Si el problema continúa, avisa al equipo de soporte.</p><div className="inline-actions"><Button variant="primary" type="submit" onClick={() => window.location.reload()}>Reintentar conexión</Button><ButtonLink variant="secondary" to={paths.dashboard}>Volver al inicio</ButtonLink></div></section>;
}
