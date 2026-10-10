import { Button, ButtonLink } from "./Button";
import { Callout } from "./Callout";
import { Spinner } from "./Spinner";

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
  if (error) return <Callout variant="error"><p>{error}</p><div className="inline-actions"><Button variant="secondary" onClick={onRetry}>Reintentar</Button>{connectionError && <ButtonLink variant="ghost" to="/connection-error">Ayuda de conexión</ButtonLink>}</div></Callout>;
  if (empty) return <p className="empty-state">{emptyMessage ?? "No hay elementos para mostrar."}</p>;
  return null;
}
