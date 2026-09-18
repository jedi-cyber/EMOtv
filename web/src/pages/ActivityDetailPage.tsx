import { Link, useParams } from "react-router-dom";
import type { Activity } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { PageState } from "../components/PageState";
import { paths } from "../routes/paths";
import { PageHeader } from "../components/PageHeader";

export function ActivityDetailPage() {
  const { activityId = "" } = useParams();
  const query = useApiQuery<Activity>(`/activities/${encodeURIComponent(activityId)}`);
  const activity = query.data;
  return <section><Link className="back-link" to={paths.activities}>← Volver a actividades</Link><PageState {...query} onRetry={query.reload} />{activity && <>
    <PageHeader section="Actividad corporal" title={activity.name} description={activity.description} />
    <dl className="detail-grid"><div><dt>Postura</dt><dd>{activity.required_posture}</dd></div><div><dt>Duración</dt><dd>{activity.duration_seconds} segundos</dd></div><div><dt>Repeticiones</dt><dd>{activity.repetitions}</dd></div></dl>
    <Link className="button primary action-link" to={paths.analysis}>Reconocer expresión primero</Link>
  </>}</section>;
}
