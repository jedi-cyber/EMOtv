import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { ApiError, apiRequest } from "../api/http";
import type { Activity, EmotionalSession } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button, ButtonLink } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip, toneForSession } from "../components/StatusChip";
import { useExpressionCatalog } from "../expressions/ExpressionCatalog";
import { paths } from "../routes/paths";
import { activityOutcomeName, sessionStateName } from "../sessions/labels";

function formatDate(value: string) {
  return new Intl.DateTimeFormat("es-PE", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

/** Sesión cancelada sin expresión registrada: no aporta resultado y se oculta por defecto. */
export function isWithoutResult(session: EmotionalSession): boolean {
  return session.state === "cancelled" && !session.initial_emotion;
}

const EMPTY = <span className="empty-cell">—</span>;

export function SessionsPage() {
  const { token, user } = useAuth();
  const navigate = useNavigate();
  const { label: expressionLabel } = useExpressionCatalog();
  const [studentFilter, setStudentFilter] = useState("");
  const [appliedFilter, setAppliedFilter] = useState("");
  const [showWithoutResult, setShowWithoutResult] = useState(false);
  const query = useApiQuery<EmotionalSession[]>(
    appliedFilter ? `/sessions?student_id=${encodeURIComponent(appliedFilter)}` : "/sessions",
  );
  const activitiesQuery = useApiQuery<Activity[]>("/activities");
  const activityNames = new Map((activitiesQuery.data ?? []).map((item) => [item.id, item.name]));
  const [actionError, setActionError] = useState("");
  const [starting, setStarting] = useState(false);
  const sessions = query.data ?? [];
  const hiddenCount = sessions.filter(isWithoutResult).length;
  const visible = showWithoutResult ? sessions : sessions.filter((session) => !isWithoutResult(session));
  const student = user?.role === "student";

  function activityName(id: string | null) {
    if (!id) return EMPTY;
    // Nunca se muestra el id interno: si la actividad ya no existe, se indica así.
    return activityNames.get(id) ?? (activitiesQuery.loading ? "…" : "Actividad no disponible");
  }

  async function startSession() {
    const targetStudent = student ? "" : appliedFilter;
    if (!student && !targetStudent) {
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
      <PageHeader title={student ? "Mis sesiones" : "Sesiones"} description="Revisa actividades realizadas y resultados registrados."
        actions={user?.role === "psychologist" ? undefined : <Button variant="secondary" disabled={starting} onClick={startSession}>{starting ? "Iniciando…" : "Nueva sesión"}</Button>} />
      {!student && <form className="filter-bar" onSubmit={(event) => { event.preventDefault(); setAppliedFilter(studentFilter.trim()); setActionError(""); }}><label>ID del estudiante<input value={studentFilter} placeholder="student-..." onChange={(event) => setStudentFilter(event.target.value)} /></label><Button variant="secondary" type="submit">Aplicar filtro</Button>{appliedFilter && <Button variant="secondary" onClick={() => { setStudentFilter(""); setAppliedFilter(""); }}>Mostrar todas</Button>}</form>}
      {appliedFilter && <p className="filter-summary">Mostrando sesiones del estudiante <strong>{appliedFilter}</strong>.</p>}
      {actionError && <Callout variant="error">{actionError}</Callout>}
      <PageState {...query} onRetry={query.reload} />
      {!query.loading && !query.error && sessions.length === 0 && <div className="empty-state">
        <p>{user?.role === "psychologist" ? "No hay sesiones de tus estudiantes asignados." : "Todavía no tienes sesiones registradas. Cada análisis que hagas aparecerá aquí."}</p>
        {student && <ButtonLink variant="primary" to={paths.analysis}>Nuevo análisis</ButtonLink>}
      </div>}
      {sessions.length > 0 && <>
        {hiddenCount > 0 && <div className="table-toolbar">
          <Checkbox checked={showWithoutResult} onChange={(event) => setShowWithoutResult(event.target.checked)}>Mostrar sesiones sin resultado</Checkbox>
          {!showWithoutResult && <span className="muted">{hiddenCount === 1 ? "1 sesión oculta" : `${hiddenCount} sesiones ocultas`}</span>}
        </div>}
        {visible.length === 0 ? <p className="empty-state">Todas las sesiones se cancelaron antes de registrar una expresión.</p>
          : <div className="table-wrap"><table className="data-table"><thead><tr><th>Fecha</th><th>Estado</th>{!student && <th>Estudiante</th>}<th>Actividad</th><th>Resultado de la actividad</th><th>Expresión registrada</th><th>Confianza</th><th>Duración</th></tr></thead><tbody>
            {visible.map((session) => <tr key={session.id} className="clickable-row" onClick={(event) => {
              if (!(event.target as HTMLElement).closest("a")) navigate(paths.session(session.id));
            }}>
              <td data-label="Fecha"><Link className="row-link" to={paths.session(session.id)}>{formatDate(session.started_at)}</Link></td>
              <td data-label="Estado"><StatusChip tone={toneForSession(session.state)}>{sessionStateName(session.state)}</StatusChip></td>
              {!student && <td data-label="Estudiante">{session.student_id ?? "Sin asociar"}</td>}
              <td data-label="Actividad">{activityName(session.activity_id)}</td>
              <td data-label="Resultado de la actividad">{session.exercise_result ? activityOutcomeName(session.exercise_result) : EMPTY}</td>
              <td data-label="Expresión registrada">{session.initial_emotion ? expressionLabel(session.initial_emotion) : EMPTY}</td>
              <td data-label="Confianza">{session.emotion_confidence == null ? EMPTY : `${Math.round(session.emotion_confidence * 100)} %`}</td>
              <td data-label="Duración">{session.exercise_duration_seconds == null ? EMPTY : `${session.exercise_duration_seconds.toFixed(1)} s`}</td>
            </tr>)}
          </tbody></table></div>}
      </>}
    </section>
  );
}
