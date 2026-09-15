interface PageStateProps {
  loading: boolean;
  error: string;
  empty?: boolean;
  emptyMessage?: string;
  onRetry(): void;
}

export function PageState({ loading, error, empty, emptyMessage, onRetry }: PageStateProps) {
  if (loading) return <p className="notice"><Spinner label="Cargando información" /></p>;
  if (error) return <div className="notice error" role="alert"><p>{error}</p><div className="inline-actions"><button className="button secondary" onClick={onRetry}>Reintentar</button><Link to="/connection-error">Ayuda de conexión</Link></div></div>;
  if (empty) return <p className="notice">{emptyMessage ?? "No hay elementos para mostrar."}</p>;
  return null;
}
import { Link } from "react-router-dom";
import { Spinner } from "./Spinner";
