import { Link } from "react-router-dom";

export function ConnectionErrorPage() {
  return <section><p className="eyebrow">Conexión</p><h1>No podemos comunicarnos con EMOtv</h1><p className="lead">Comprueba que FastAPI esté ejecutándose y que la dirección configurada en <code>VITE_API_URL</code> sea correcta.</p><div className="inline-actions"><button className="button primary" onClick={() => window.location.reload()}>Reintentar</button><Link to="/dashboard">Volver al inicio</Link></div></section>;
}
