import { Link } from "react-router-dom";
import type { Activity } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { PageState } from "../components/PageState";

const postureNames: Record<string, string> = {
  arms_up: "Brazos arriba",
  arms_open: "Brazos abiertos",
  arms_forward: "Brazos al frente",
  hands_on_hips: "Manos en las caderas",
  squat: "Sentadilla",
};

export function ActivitiesPage() {
  const query = useApiQuery<Activity[]>("/activities");
  const activities = query.data ?? [];

  return (
    <section>
      <p className="eyebrow">Terapia mediante posturas</p>
      <div className="page-heading">
        <div><h1>Actividades</h1><p className="lead">Elige una actividad guiada y realiza la postura con calma.</p></div>
      </div>
      <PageState {...query} empty={!query.loading && !query.error && activities.length === 0} emptyMessage="Todavía no hay actividades disponibles." onRetry={query.reload} />
      {activities.length > 0 && <div className="card-grid">
        {activities.map((activity) => <article className="card activity-card" key={activity.id}>
          <span className="pill">{postureNames[activity.required_posture] ?? activity.required_posture}</span>
          <h2>{activity.name}</h2>
          <p>{activity.description}</p>
          <dl className="metadata"><div><dt>Duración</dt><dd>{activity.duration_seconds} s</dd></div><div><dt>Repeticiones</dt><dd>{activity.repetitions}</dd></div></dl>
          <Link className="button primary action-link" to={`/analysis?activity=${encodeURIComponent(activity.id)}`}>Preparar actividad</Link>
          <Link className="text-link" to={`/activities/${activity.id}`}>Ver detalles</Link>
        </article>)}
      </div>}
    </section>
  );
}
