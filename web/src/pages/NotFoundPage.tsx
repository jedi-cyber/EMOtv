import { Link } from "react-router-dom";

export function NotFoundPage() {
  return <main className="centered"><div><h1>Página no encontrada</h1><Link to="/dashboard">Volver al inicio</Link></div></main>;
}
