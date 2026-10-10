import { Button, ButtonLink } from "./Button";
import { Callout } from "./Callout";
import { Spinner } from "./Spinner";
import { paths } from "../routes/paths";

interface PageStateProps {
  loading: boolean;
  error: string;
  connectionError?: boolean;
  /** Código HTTP del error: 403 y 404 no se resuelven reintentando. */
  errorStatus?: number | null;
  empty?: boolean;
  emptyMessage?: string;
  onRetry(): void;
}

export function PageState({ loading, error, connectionError, errorStatus, empty, emptyMessage, onRetry }: PageStateProps) {
  if (!loading && error && (errorStatus === 403 || errorStatus === 404)) return <Callout variant="error">
    <p>{errorStatus === 403 ? "No tienes permiso para ver esta información con tu cuenta." : "No encontramos lo que buscas. Puede que se haya eliminado."}</p>
    <div className="inline-actions"><ButtonLink variant="secondary" to={paths.dashboard}>Volver al inicio</ButtonLink></div>
  </Callout>;
  if (loading) return <div className="loading-state"><Spinner label="Cargando información" /><div className="loading-placeholder" aria-hidden="true"><span /><span /><span /></div></div>;
  if (error) return <Callout variant="error"><p>{error}</p><div className="inline-actions"><Button variant="secondary" onClick={onRetry}>Reintentar</Button>{connectionError && <ButtonLink variant="ghost" to="/connection-error">Ayuda de conexión</ButtonLink>}</div></Callout>;
  if (empty) return <p className="empty-state">{emptyMessage ?? "No hay elementos para mostrar."}</p>;
  return null;
}
