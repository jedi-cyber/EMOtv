import { Link } from "react-router-dom";
import { paths } from "../routes/paths";

export function ConnectionErrorPage() {
  return <section><p className="eyebrow">Conexión</p><h1>No podemos comunicarnos con EMOtv</h1><p className="lead">El servicio no responde en este momento. Comprueba tu conexión y vuelve a intentarlo. Si el problema continúa, avisa al equipo de soporte.</p><div className="inline-actions"><button className="button primary" onClick={() => window.location.reload()}>Reintentar conexión</button><Link to={paths.dashboard}>Volver al inicio</Link></div></section>;
}
