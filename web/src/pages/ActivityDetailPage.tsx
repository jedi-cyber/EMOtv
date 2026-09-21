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
    <dl className="detail-grid"><div><dt>Pasos</dt><dd>{activity.steps?.length ?? 1}</dd></div><div><dt>Duración estimada</dt><dd>{(activity.steps?.reduce((total, step) => total + step.duration_seconds, 0) ?? activity.duration_seconds) * activity.repetitions} segundos</dd></div><div><dt>Repeticiones</dt><dd>{activity.repetitions}</dd></div></dl>
    <ol>{activity.steps?.map((step, index) => <li key={index}>{step.instruction} · {step.duration_seconds} s</li>)}</ol>
    <Link className="button primary action-link" to={paths.analysis}>Reconocer expresión primero</Link>
  </>}</section>;
}
