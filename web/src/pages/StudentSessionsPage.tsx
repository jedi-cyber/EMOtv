import { Link, useParams } from "react-router-dom";
import type { EmotionalSession } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { PageState } from "../components/PageState";

const stateNames = { created: "Creada", in_progress: "En progreso", completed: "Completada", cancelled: "Cancelada" };

export function StudentSessionsPage() {
  const { studentId = "" } = useParams();
  const query = useApiQuery<EmotionalSession[]>(`/sessions?student_id=${encodeURIComponent(studentId)}`);
  const sessions = query.data ?? [];
  return <section><Link className="back-link" to="/students">← Volver a estudiantes</Link><p className="eyebrow">Seguimiento</p><h1>Sesiones del estudiante</h1><p className="lead">Identificador: {studentId}</p>
    <PageState {...query} empty={!query.loading && !query.error && sessions.length === 0} onRetry={query.reload} />
    {sessions.length > 0 && <div className="card-list">{sessions.map((session) => <Link className="card row-card" to={`/sessions/${session.id}`} key={session.id}><div><strong>{new Date(session.started_at).toLocaleString("es-PE")}</strong><span>{session.activity_id ?? "Actividad sin completar"}</span></div><span className={`status status-${session.state}`}>{stateNames[session.state]}</span></Link>)}</div>}
  </section>;
}
