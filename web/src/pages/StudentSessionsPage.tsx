import { useParams } from "react-router-dom";
import { Card } from "../components/Card";
import { StatusChip, toneForSession } from "../components/StatusChip";
import type { Activity, EmotionalSession, Student } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { PageState } from "../components/PageState";
import { paths } from "../routes/paths";
import { PageHeader } from "../components/PageHeader";
import { sessionStateName } from "../sessions/labels";
import { ButtonLink } from "../components/Button";


export function StudentSessionsPage() {
  const { studentId = "" } = useParams();
  const query = useApiQuery<EmotionalSession[]>(`/sessions?student_id=${encodeURIComponent(studentId)}`);
  const studentsQuery = useApiQuery<Student[]>("/students");
  const activitiesQuery = useApiQuery<Activity[]>("/activities");
  const sessions = query.data ?? [];
  const code = (studentsQuery.data ?? []).find((item) => item.id === studentId)?.student_code;
  const activityName = (id: string | null) => id
    ? (activitiesQuery.data ?? []).find((item) => item.id === id)?.name ?? "Actividad no disponible"
    : "Sin actividad";
  return <section><ButtonLink variant="ghost" className="back-link" to={paths.students}>← Volver a estudiantes</ButtonLink>
    <PageHeader title={code ? `Sesiones de ${code}` : "Sesiones del estudiante"} description="Abre una sesión para ver la expresión registrada y el resultado de la actividad." />
    <PageState {...query} empty={!query.loading && !query.error && sessions.length === 0}
      emptyMessage="Este estudiante todavía no tiene sesiones registradas." onRetry={query.reload} />
    {sessions.length > 0 && <div className="card-list">{sessions.map((session) => <Card as="article" className="row-card" key={session.id}><div><ButtonLink variant="ghost" className="row-card-link" to={paths.session(session.id)}>{new Date(session.started_at).toLocaleString("es-PE")}</ButtonLink><span>{activityName(session.activity_id)}</span></div><StatusChip tone={toneForSession(session.state)}>{sessionStateName(session.state)}</StatusChip></Card>)}</div>}
  </section>;
}
