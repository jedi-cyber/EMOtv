import { Link, useParams } from "react-router-dom";
import type { Activity } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { PageState } from "../components/PageState";

export function ActivityDetailPage() {
  const { activityId = "" } = useParams();
  const query = useApiQuery<Activity>(`/activities/${encodeURIComponent(activityId)}`);
  const activity = query.data;
  return <section><Link className="back-link" to="/activities">← Volver a actividades</Link><PageState {...query} onRetry={query.reload} />{activity && <>
    <p className="eyebrow">Actividad corporal</p><h1>{activity.name}</h1><p className="lead">{activity.description}</p>
    <dl className="detail-grid"><div><dt>Postura</dt><dd>{activity.required_posture}</dd></div><div><dt>Duración</dt><dd>{activity.duration_seconds} segundos</dd></div><div><dt>Repeticiones</dt><dd>{activity.repetitions}</dd></div></dl>
    <Link className="button primary action-link" to={`/analysis?activity=${encodeURIComponent(activity.id)}`}>Preparar actividad</Link>
  </>}</section>;
}
