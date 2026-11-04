import { useApiQuery } from "../api/useApiQuery";
import { ButtonLink } from "../components/Button";
import { Callout } from "../components/Callout";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip } from "../components/StatusChip";
import { paths } from "../routes/paths";

export interface PendingReview {
  kind: "report" | "deletion";
  session_id: string;
  session_code: string | null;
  user_code: string | null;
  waiting_since: string;
  report_id: string | null;
}

const kindNames: Record<PendingReview["kind"], string> = {
  report: "Reporte enviado a revisión",
  deletion: "Pedido de eliminación",
};

function waitingText(since: string) {
  const days = Math.floor((Date.now() - new Date(since).getTime()) / 86_400_000);
  return days <= 0 ? "Desde hoy" : days === 1 ? "Desde ayer" : `Hace ${days} días`;
}

/** Por revisar del docente: supervisa después de cada sesión, cuando tiene tiempo. */
export function ReviewsPage() {
  const query = useApiQuery<PendingReview[]>("/reviews");
  const items = query.data ?? [];
  return <section>
    <PageHeader title="Por revisar"
      description="Lo que tu grupo dejó esperando tu revisión, del más antiguo al más nuevo. Revísalo cuando tengas tiempo: los usuarios conducen sus sesiones sin que estés presente." />
    <PageState {...query} empty={!query.loading && !query.error && items.length === 0}
      emptyMessage="No hay nada por revisar. Las imágenes que suben los usuarios están en «Imágenes por revisar»." onRetry={query.reload} />
    {items.length > 0 && <ul className="card-list">{items.map((item) => <li key={`${item.kind}-${item.session_id}`} className="card row-card">
      <div>
        <strong>{kindNames[item.kind]}</strong>
        <span>Sesión {item.session_code ?? "sin código"}{item.user_code ? ` · Usuario ${item.user_code}` : ""}</span>
      </div>
      <span className="inline-actions">
        <StatusChip tone="progress">{waitingText(item.waiting_since)}</StatusChip>
        <ButtonLink variant="secondary" to={item.kind === "report" ? paths.sessionReport(item.session_id) : paths.session(item.session_id)}>
          {item.kind === "report" ? "Revisar reporte" : "Ver la sesión"}
        </ButtonLink>
      </span>
    </li>)}</ul>}
    <Callout variant="info" role="note">Revisas resultados y textos, nunca imágenes de las personas evaluadas: el sistema no las guarda.</Callout>
  </section>;
}
