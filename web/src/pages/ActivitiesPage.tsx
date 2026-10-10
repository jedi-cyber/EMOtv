import { useState } from "react";
import type { Activity, ActivityStep } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button, ButtonLink } from "../components/Button";
import { CardWithHeader } from "../components/Card";
import { Modal } from "../components/Modal";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { PostureIcon, postureName } from "../components/PostureIcon";
import { paths } from "../routes/paths";

/** Una actividad sin pasos explícitos equivale a un paso con su postura y descripción. */
export function activitySteps(activity: Activity): ActivityStep[] {
  return activity.steps?.length ? activity.steps
    : [{ posture: activity.required_posture, instruction: activity.description, duration_seconds: activity.duration_seconds }];
}

export function approximateSeconds(activity: Activity): number {
  return Math.round(activitySteps(activity).reduce((total, step) => total + step.duration_seconds, 0) * activity.repetitions);
}

function stepsLabel(count: number) {
  return count === 1 ? "1 paso" : `${count} pasos`;
}

function repetitionsLabel(count: number) {
  return count === 1 ? "1 repetición" : `${count} repeticiones`;
}

export function ActivitiesPage() {
  const { user } = useAuth();
  const query = useApiQuery<Activity[]>("/activities");
  const activities = query.data ?? [];
  const [open, setOpen] = useState<Activity | null>(null);
  // El flujo de actividad directa existe (/analysis?activity=…) y es solo para estudiantes.
  const canStart = user?.role === "student";

  return <section>
    <PageHeader title="Actividades" description="Consulta las posturas disponibles. Para recibir una sugerencia, inicia primero el análisis facial."
      actions={canStart ? <ButtonLink variant="secondary" to={paths.analysis}>Ir al analizador</ButtonLink> : undefined} />
    <PageState {...query} empty={!query.loading && !query.error && activities.length === 0}
      emptyMessage="Todavía no hay actividades disponibles. Administración debe crearlas antes de que puedas practicarlas." onRetry={query.reload} />
    {activities.length > 0 && <div className="card-grid">
      {activities.map((activity) => {
        const steps = activitySteps(activity);
        return <CardWithHeader key={activity.id} icon={<PostureIcon posture={steps[0].posture} />}
          badge={stepsLabel(steps.length)} title={activity.name}
          meta={`${stepsLabel(steps.length)} · ${repetitionsLabel(activity.repetitions)} · unos ${approximateSeconds(activity)} s`}
          actions={<Button variant="secondary" onClick={() => setOpen(activity)} aria-label={`Ver pasos de ${activity.name}`}>Ver pasos</Button>}>
          <p>{activity.description}</p>
        </CardWithHeader>;
      })}
    </div>}
    <Modal open={open != null} title={open?.name ?? ""} onClose={() => setOpen(null)}
      footer={open && canStart && <ButtonLink variant="primary" to={paths.analysisForActivity(open.id)}>Empezar actividad</ButtonLink>}>
      {open && <>
        <p>{open.description}</p>
        <p className="muted">{repetitionsLabel(open.repetitions)} · unos {approximateSeconds(open)} s en total</p>
        <ol className="step-list">
          {activitySteps(open).map((step, index) => <li key={`${step.posture}-${index}`}>
            <span className="step-list-icon"><PostureIcon posture={step.posture} /></span>
            <div>
              <strong>{postureName(step.posture)}</strong>
              <p>{step.instruction}</p>
              <span className="muted">{step.duration_seconds} s</span>
            </div>
          </li>)}
        </ol>
      </>}
    </Modal>
  </section>;
}
