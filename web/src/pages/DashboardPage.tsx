import type { EmotionalSession } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { ButtonLink } from "../components/Button";
import { NextStepCard } from "../components/NextStepCard";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip, toneForSession } from "../components/StatusChip";
import { useConsentStatus } from "../consent/useConsentStatus";
import { useExpressionCatalog } from "../expressions/ExpressionCatalog";
import { paths } from "../routes/paths";
import { activityOutcomeName, sessionStateName } from "../sessions/labels";

const descriptions = {
  student: "Selecciona una actividad corporal o revisa tus sesiones.",
  psychologist: "Consulta el seguimiento de estudiantes y sus sesiones autorizadas.",
  admin: "Administra usuarios, actividades y el funcionamiento general de EMOtv.",
};

function formatDate(value: string) {
  return new Intl.DateTimeFormat("es-PE", { dateStyle: "long", timeStyle: "short" }).format(new Date(value));
}

/** La cuenta no guarda el nombre de la persona: el saludo va sin nombre y nunca usa el correo. */
export function DashboardPage() {
  const { user } = useAuth();
  return <section>
    <PageHeader title="Hola" description={user ? descriptions[user.role] : ""} />
    {user?.role === "student" && <StudentNextStep />}
    {user?.role === "psychologist" && <NextStepCard title="Seguimiento de estudiantes"
      action={<ButtonLink variant="primary" to={paths.students}>Ver estudiantes</ButtonLink>}>
      <p>Accede al seguimiento con los permisos correspondientes.</p>
    </NextStepCard>}
    {user?.role === "admin" && <NextStepCard title="Usuarios"
      action={<ButtonLink variant="primary" to={paths.users}>Ver usuarios</ButtonLink>}>
      <p>Supervisa las cuentas y sus roles de acceso.</p>
    </NextStepCard>}
  </section>;
}

function StudentNextStep() {
  const consent = useConsentStatus();
  const sessionsQuery = useApiQuery<EmotionalSession[]>("/sessions");
  const { label: expressionLabel } = useExpressionCatalog();
  if (consent.state === "loading" || sessionsQuery.loading) return <PageState loading error="" onRetry={() => undefined} />;

  if (consent.state === "missing" || consent.state === "outdated") {
    return <NextStepCard title={consent.state === "outdated" ? "Revisa la nueva versión del consentimiento" : "Revisa el consentimiento"}
      action={<ButtonLink variant="primary" to={paths.consent}>Revisar consentimiento</ButtonLink>}>
      <p>{consent.state === "outdated"
        ? "La política cambió. Para volver a usar el analizador, lee y acepta la versión vigente."
        : "Para usar el analizador necesitas aceptar la política de análisis facial. Puedes revocarla cuando quieras."}</p>
    </NextStepCard>;
  }

  if (sessionsQuery.error) return <PageState {...sessionsQuery} onRetry={sessionsQuery.reload} />;
  const sessions = [...(sessionsQuery.data ?? [])].sort((a, b) => b.started_at.localeCompare(a.started_at));
  const last = sessions[0];
  if (!last) {
    return <NextStepCard title="Cómo funciona un análisis"
      action={<ButtonLink variant="primary" to={paths.analysis}>Empezar análisis</ButtonLink>}>
      <ol className="next-step-steps">
        <li><strong>Encuadra tu rostro.</strong> Colócate de frente a la cámara, con buena luz.</li>
        <li><strong>Registra la expresión.</strong> Cuando la lectura sea estable, regístrala.</li>
        <li><strong>Practica la actividad.</strong> Sigue las posturas de la actividad sugerida.</li>
      </ol>
    </NextStepCard>;
  }
  return <NextStepCard title="Tu última sesión"
    action={<ButtonLink variant="primary" to={paths.analysis}>Nuevo análisis</ButtonLink>}>
    <dl className="next-step-summary">
      <div><dt>Expresión registrada</dt><dd>{last.initial_emotion ? expressionLabel(last.initial_emotion) : "Sin expresión registrada"}</dd></div>
      <div><dt>Fecha</dt><dd>{formatDate(last.started_at)}</dd></div>
      <div><dt>Actividad</dt><dd>{last.exercise_result
        ? <StatusChip tone={last.exercise_result === "completed" ? "success" : "neutral"}>{activityOutcomeName(last.exercise_result)}</StatusChip>
        :<StatusChip tone={toneForSession(last.state)}>{sessionStateName(last.state)}</StatusChip>}</dd></div>
    </dl>
  </NextStepCard>;
}
