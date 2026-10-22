import { useParams } from "react-router-dom";
import type { ParticipantTrends } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { ButtonLink } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { TrendChart } from "../insights/TrendChart";
import { paths } from "../routes/paths";

/** Cómo cambian las coincidencias de un participante entre sesiones con el mismo protocolo. */
export function ParticipantTrendsPage() {
  const { participantId = "" } = useParams();
  const query = useApiQuery<ParticipantTrends>(`/participants/${encodeURIComponent(participantId)}/trends`);
  const data = query.data;
  return <section>
    <ButtonLink variant="ghost" className="back-link" to={paths.participants}>← Volver a participantes</ButtonLink>
    <PageHeader title={data ? `Tendencias de ${data.code}` : "Tendencias"}
      description="Coincidencias entre la expresión estimada y la esperada en los estímulos emocionales, por protocolo. Describe lo registrado; no lo interpreta." />
    <PageState {...query} empty={Boolean(data) && data!.protocols.length === 0}
      emptyMessage="Este participante todavía no tiene sesiones guiadas con protocolo." onRetry={query.reload} />
    {data?.protocols.map((group) => <section key={group.protocol_family_id} className="card">
      <h2>{group.protocol_name}</h2>
      <TrendChart group={group} />
    </section>)}
    <p className="muted">Las capturas marcadas por calidad no cuentan. Las expresiones son estimaciones del modelo; no indican lo que la persona sentía.</p>
  </section>;
}
