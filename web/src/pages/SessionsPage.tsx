import { useState } from "react";
import { StatusChip, toneForSession } from "../components/StatusChip";
import { ApiError, apiRequest } from "../api/http";
import type { EmotionalSession } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { PageState } from "../components/PageState";
import { Callout } from "../components/Callout";
import { PageHeader } from "../components/PageHeader";
import { activityOutcomeName, sessionStateName } from "../sessions/labels";
import { useExpressionCatalog } from "../expressions/ExpressionCatalog";
import { Button, ButtonLink } from "../components/Button";


function formatDate(value: string) {
  return new Intl.DateTimeFormat("es-PE", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

export function SessionsPage() {
  const { token, user } = useAuth();
  const { label: expressionLabel } = useExpressionCatalog();
  const [studentFilter, setStudentFilter] = useState("");
  const [appliedFilter, setAppliedFilter] = useState("");
  const query = useApiQuery<EmotionalSession[]>(
    appliedFilter
      ? `/sessions?student_id=${encodeURIComponent(appliedFilter)}`
      : "/sessions",
  );
  const [actionError, setActionError] = useState("");
  const [starting, setStarting] = useState(false);
  const sessions = query.data ?? [];

  async function startSession() {
    const targetStudent = user?.role === "student" ? "" : appliedFilter;
    if (user?.role !== "student" && !targetStudent) {
      setActionError("Aplica primero el ID del estudiante para iniciar una sesión asociada.");
      return;
    }
    setStarting(true);
    setActionError("");
    try {
      await apiRequest<EmotionalSession>("/sessions", {
        method: "POST",
        body: JSON.stringify(targetStudent ? { student_id: targetStudent } : {}),
        token,
      });
      await query.reload();
    } catch (reason) {
      setActionError(reason instanceof ApiError ? reason.message : "No se pudo iniciar la sesión");
    } finally { setStarting(false); }
  }

  return (
    <section>
      <PageHeader title="Sesiones" description="Revisa actividades realizadas y resultados registrados." actions={user?.role === "psychologist" ? undefined : <Button variant="primary" type="submit" disabled={starting} onClick={startSession}>{starting ? "Iniciando…" : "Nueva sesión"}</Button>} />
      {user?.role !== "student" && <form className="filter-bar" onSubmit={(event) => { event.preventDefault(); setAppliedFilter(studentFilter.trim()); setActionError(""); }}><label>ID del estudiante<input value={studentFilter} placeholder="student-..." onChange={(event) => setStudentFilter(event.target.value)} /></label><Button variant="secondary" type="submit">Aplicar filtro</Button>{appliedFilter && <Button variant="secondary" type="button" onClick={() => { setStudentFilter(""); setAppliedFilter(""); }}>Mostrar todas</Button>}</form>}
      {appliedFilter && <p className="filter-summary">Mostrando sesiones del estudiante <strong>{appliedFilter}</strong>.</p>}
      {actionError && <Callout variant="error">{actionError}</Callout>}
      <PageState {...query} empty={!query.loading && !query.error && sessions.length === 0} emptyMessage={user?.role === "psychologist" ? "No hay sesiones de tus estudiantes asignados." : "Todavía no tienes sesiones registradas."} onRetry={query.reload} />
      {sessions.length > 0 && <div className="table-wrap"><table><thead><tr><th>Fecha</th><th>Estado</th>{user?.role !== "student" && <th>Estudiante</th>}<th>Actividad</th><th>Resultado de la actividad</th><th>Expresión registrada</th><th>Confianza</th><th>Duración</th></tr></thead><tbody>
        {sessions.map((session) => <tr key={session.id}><td><ButtonLink variant="ghost" size="sm" className="table-link" to={`/sessions/${session.id}`}>{formatDate(session.started_at)}</ButtonLink></td><td><StatusChip tone={toneForSession(session.state)}>{sessionStateName(session.state)}</StatusChip></td>{user?.role !== "student" && <td>{session.student_id ?? "Sin asociar"}</td>}<td>{session.activity_id ?? "—"}</td><td>{activityOutcomeName(session.exercise_result)}</td><td>{expressionLabel(session.initial_emotion)}</td><td>{session.emotion_confidence == null ? "—" : `${Math.round(session.emotion_confidence * 100)} %`}</td><td>{session.exercise_duration_seconds == null ? "—" : `${session.exercise_duration_seconds.toFixed(1)} s`}</td></tr>)}
      </tbody></table></div>}
    </section>
  );
}
