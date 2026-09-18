interface PageStateProps {
  loading: boolean;
  error: string;
  connectionError?: boolean;
  empty?: boolean;
  emptyMessage?: string;
  onRetry(): void;
}

export function PageState({ loading, error, connectionError, empty, emptyMessage, onRetry }: PageStateProps) {
  if (loading) return <div className="loading-state"><Spinner label="Cargando información" /><div className="loading-placeholder" aria-hidden="true"><span /><span /><span /></div></div>;
  if (error) return <div className="notice error" role="alert"><p>{error}</p><div className="inline-actions"><button className="button secondary" onClick={onRetry}>Reintentar</button>{connectionError && <Link to="/connection-error">Ayuda de conexión</Link>}</div></div>;
  if (empty) return <p className="notice">{emptyMessage ?? "No hay elementos para mostrar."}</p>;
  return null;
}
import { Link } from "react-router-dom";
import { Spinner } from "./Spinner";
