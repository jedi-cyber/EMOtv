import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { Activity, EmotionalSession, Student } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button, ButtonLink } from "../components/Button";
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
  const { user } = useAuth();
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
  const studentsQuery = useApiQuery<Student[]>(user?.role === "student" ? null : "/students");
  const studentCodes = new Map((studentsQuery.data ?? []).map((item) => [item.id, item.student_code]));
  const sessions = query.data ?? [];
  const hiddenCount = sessions.filter(isWithoutResult).length;
  const visible = showWithoutResult ? sessions : sessions.filter((session) => !isWithoutResult(session));
  const student = user?.role === "student";

  function activityName(id: string | null) {
    if (!id) return EMPTY;
    // Nunca se muestra el id interno: si la actividad ya no existe, se indica así.
    return activityNames.get(id) ?? (activitiesQuery.loading ? "…" : "Actividad no disponible");
  }

  return (
    <section>
      <PageHeader title={student ? "Mis sesiones" : "Sesiones"}
        description={student ? "Revisa actividades realizadas y resultados registrados." : "Tus sesiones y las de los usuarios de tu grupo."}
        actions={<ButtonLink variant="secondary" to={paths.analysis}>Nuevo análisis</ButtonLink>} />
      {!student && <form className="filter-bar" onSubmit={(event) => { event.preventDefault(); setAppliedFilter(studentFilter); }}><label>Usuario<select value={studentFilter} onChange={(event) => setStudentFilter(event.target.value)}>
        <option value="">Todas las sesiones</option>
        {(studentsQuery.data ?? []).map((item) => <option key={item.id} value={item.id}>{item.student_code}</option>)}
      </select></label><Button variant="secondary" type="submit">Aplicar filtro</Button>{appliedFilter && <Button variant="secondary" onClick={() => { setStudentFilter(""); setAppliedFilter(""); }}>Mostrar todas</Button>}</form>}
      {appliedFilter && <p className="filter-summary" role="status">Mostrando sesiones de <strong>{studentCodes.get(appliedFilter) ?? "el usuario elegido"}</strong>.</p>}
      <PageState {...query} onRetry={query.reload} />
      {!query.loading && !query.error && sessions.length === 0 && <div className="empty-state">
        <p>{student ? "Todavía no tienes sesiones registradas. Cada análisis que hagas aparecerá aquí." : "Todavía no hay sesiones tuyas ni de tu grupo."}</p>
        <ButtonLink variant="primary" to={paths.analysis}>Nuevo análisis</ButtonLink>
      </div>}
      {sessions.length > 0 && <>
        {hiddenCount > 0 && <div className="table-toolbar">
          <Checkbox checked={showWithoutResult} onChange={(event) => setShowWithoutResult(event.target.checked)}>Mostrar sesiones sin resultado</Checkbox>
          {!showWithoutResult && <span className="muted">{hiddenCount === 1 ? "1 sesión oculta" : `${hiddenCount} sesiones ocultas`}</span>}
        </div>}
        {visible.length === 0 ? <p className="empty-state">Todas las sesiones se cancelaron antes de registrar una expresión.</p>
          : <div className="table-wrap"><table className="data-table"><thead><tr><th>Fecha</th><th>Estado</th>{!student && <th>Conducida por</th>}<th>Actividad</th><th>Resultado de la actividad</th><th>Expresión registrada</th><th>Confianza</th><th>Duración</th></tr></thead><tbody>
            {visible.map((session) => <tr key={session.id} className="clickable-row" onClick={(event) => {
              if (!(event.target as HTMLElement).closest("a")) navigate(paths.session(session.id));
            }}>
              <td data-label="Fecha"><Link className="row-link" to={paths.session(session.id)}>{formatDate(session.started_at)}</Link></td>
              <td data-label="Estado"><StatusChip tone={toneForSession(session.state)}>{sessionStateName(session.state)}</StatusChip></td>
              {!student && <td data-label="Conducida por">{session.student_id ? studentCodes.get(session.student_id) ?? "Usuario de tu grupo" : "Tú"}</td>}
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
