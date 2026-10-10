import { useParams } from "react-router-dom";
import { Card } from "../components/Card";
import { StatusChip, toneForSession } from "../components/StatusChip";
import type { EmotionalSession } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { PageState } from "../components/PageState";
import { paths } from "../routes/paths";
import { PageHeader } from "../components/PageHeader";
import { sessionStateName } from "../sessions/labels";
import { ButtonLink } from "../components/Button";


export function StudentSessionsPage() {
  const { studentId = "" } = useParams();
  const query = useApiQuery<EmotionalSession[]>(`/sessions?student_id=${encodeURIComponent(studentId)}`);
  const sessions = query.data ?? [];
  return <section><ButtonLink variant="ghost" className="back-link" to={paths.students}>← Volver a estudiantes</ButtonLink><PageHeader title="Sesiones del estudiante" description={`Identificador: ${studentId}`} />
    <PageState {...query} empty={!query.loading && !query.error && sessions.length === 0} onRetry={query.reload} />
    {sessions.length > 0 && <div className="card-list">{sessions.map((session) => <Card as="article" className="row-card" key={session.id}><div><ButtonLink variant="ghost" className="row-card-link" to={paths.session(session.id)}>{new Date(session.started_at).toLocaleString("es-PE")}</ButtonLink><span>{session.activity_id ?? "Actividad sin completar"}</span></div><StatusChip tone={toneForSession(session.state)}>{sessionStateName(session.state)}</StatusChip></Card>)}</div>}
  </section>;
}
