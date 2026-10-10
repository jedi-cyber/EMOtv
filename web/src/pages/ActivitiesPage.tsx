import type { Activity } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { PageState } from "../components/PageState";
import { paths } from "../routes/paths";
import { PageHeader } from "../components/PageHeader";
import { ButtonLink } from "../components/Button";
import { CardWithHeader } from "../components/Card";
import { NavIcon } from "../components/NavIcon";

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
      <PageHeader title="Actividades" description="Consulta las posturas disponibles. Para recibir una sugerencia, inicia primero el análisis facial." actions={<ButtonLink variant="primary" to={paths.analysis}>Ir al analizador</ButtonLink>} />
      <PageState {...query} empty={!query.loading && !query.error && activities.length === 0} emptyMessage="Todavía no hay actividades disponibles." onRetry={query.reload} />
      {activities.length > 0 && <div className="card-grid">
        {activities.map((activity) => <CardWithHeader key={activity.id} icon={<NavIcon name="activity" />}
          badge={(activity.steps?.length ?? 1) > 1 ? `${activity.steps?.length} posturas en secuencia` : postureNames[activity.required_posture] ?? activity.required_posture}
          title={activity.name}
          actions={<ButtonLink variant="secondary" to={paths.activity(activity.id)}>Ver detalles</ButtonLink>}>
          <p>{activity.description}</p>
          <dl className="metadata"><div><dt>Duración estimada</dt><dd>{(activity.steps?.reduce((total, step) => total + step.duration_seconds, 0) ?? activity.duration_seconds) * activity.repetitions} s</dd></div><div><dt>Repeticiones</dt><dd>{activity.repetitions}</dd></div></dl>
        </CardWithHeader>)}
      </div>}
    </section>
  );
}
