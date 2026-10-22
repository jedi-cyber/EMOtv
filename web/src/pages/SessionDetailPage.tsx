import { useState } from "react";
import { useParams } from "react-router-dom";
import { StatusChip, toneForSession } from "../components/StatusChip";
import { ApiError, apiRequest } from "../api/http";
import type { Activity, EmotionalSession, QuestionnaireAnswers, Student } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { PageState } from "../components/PageState";
import { Callout } from "../components/Callout";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { useAuth } from "../auth/useAuth";
import { paths } from "../routes/paths";
import { PageHeader } from "../components/PageHeader";
import { activityOutcomeName, emotionModelName, sessionStateName, sessionTypeName } from "../sessions/labels";
import { useExpressionCatalog } from "../expressions/ExpressionCatalog";
import { Button, ButtonLink } from "../components/Button";
import { AnswerList, QuestionnaireNote } from "../questionnaires/QuestionnaireForm";

const dateTime = (value: string) => new Date(value).toLocaleString("es-PE", { dateStyle: "long", timeStyle: "short" });

export function SessionDetailPage() {
  const { sessionId = "" } = useParams();
  const { token, user } = useAuth();
  const isStudent = user?.role === "student";
  const { label: expressionLabel } = useExpressionCatalog();
  const query = useApiQuery<EmotionalSession>(`/sessions/${encodeURIComponent(sessionId)}`);
  const activitiesQuery = useApiQuery<Activity[]>("/activities");
  const studentsQuery = useApiQuery<Student[]>(isStudent ? null : "/students");
  const session = query.data;
  const hasQuestionnaires = Boolean(session?.pre_questionnaire_id || session?.post_questionnaire_id);
  const responsesQuery = useApiQuery<QuestionnaireAnswers[]>(hasQuestionnaires
    ? `/sessions/${encodeURIComponent(sessionId)}/questionnaire-responses` : null);
  const responses = responsesQuery.data ?? [];
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  // Solo quien conduce la sesión la cancela: el docente no interrumpe el análisis de otra cuenta.
  const conductedByMe = session?.owner_user_id ? session.owner_user_id === user?.id : isStudent;
  const canCancel = conductedByMe && (session?.state === "created" || session?.state === "in_progress" || session?.state === "recognized");
  // Con expresión registrada, cancelar conserva el registro y solo cancela la actividad.
  const recognitionKept = Boolean(session?.recognized_at);
  const activities = Array.isArray(activitiesQuery.data) ? activitiesQuery.data : [];
  const activityName = session?.activity_id
    ? activities.find((item) => item.id === session.activity_id)?.name ?? "Actividad no disponible"
    : "Sin actividad";
  const students = Array.isArray(studentsQuery.data) ? studentsQuery.data : [];
  const studentCode = students.find((item) => item.id === session?.student_id)?.student_code ?? "Sin código disponible";

  async function cancelSession() {
    if (!session) return;
    setCancelling(true); setError(""); setMessage("");
    try {
      await apiRequest<EmotionalSession>(`/sessions/${encodeURIComponent(session.id)}/cancel`, { method: "POST", token });
      setConfirming(false); setMessage(recognitionKept ? "Actividad cancelada. La expresión registrada se conserva." : "La sesión fue cancelada correctamente."); await query.reload();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "No se pudo cancelar la sesión"); setConfirming(false); }
    finally { setCancelling(false); }
  }
  return <section><ButtonLink variant="ghost" className="back-link" to={paths.sessions}>← Volver a sesiones</ButtonLink><PageState {...query} onRetry={query.reload} />{session && <>
    <PageHeader title="Detalle de sesión" description={`Sesión iniciada el ${dateTime(session.started_at)}.`}
      actions={canCancel ? <Button variant="danger" onClick={() => setConfirming(true)}>Cancelar sesión</Button>
        : isStudent ? <ButtonLink variant="secondary" to={paths.analysis}>Nuevo análisis</ButtonLink> : undefined} />
    {message && <Callout variant="success">{message}</Callout>}{error && <Callout variant="error">{error}</Callout>}
    <dl className="detail-grid">
      <div><dt>Estado</dt><dd><StatusChip tone={toneForSession(session.state)}>{sessionStateName(session.state)}</StatusChip></dd></div>
      <div><dt>Tipo de sesión</dt><dd>{sessionTypeName(session.session_type)}</dd></div>
      <div><dt>Inicio</dt><dd>{dateTime(session.started_at)}</dd></div>
      <div><dt>Finalización</dt><dd>{session.completed_at ? dateTime(session.completed_at) : "—"}</dd></div>
      {!isStudent && <div><dt>Conducida por</dt><dd>{session.student_id ? studentCode : "Tú"}</dd></div>}
      <div><dt>Actividad</dt><dd>{activityName}</dd></div>
      {!isStudent && <div><dt>Modelo facial</dt><dd>{emotionModelName(session.emotion_model_id)}{session.emotion_model_version ? ` · versión ${session.emotion_model_version}` : ""}</dd></div>}
      <div><dt>Expresión registrada</dt><dd>{expressionLabel(session.initial_emotion)}</dd></div>
      <div><dt>Expresión registrada el</dt><dd>{session.recognized_at ? dateTime(session.recognized_at) : "—"}</dd></div>
      <div><dt>Confianza del modelo</dt><dd>{session.emotion_confidence == null ? "—" : `${Math.round(session.emotion_confidence * 100)} %`}</dd></div>
      <div><dt>Resultado de la actividad</dt><dd>{activityOutcomeName(session.exercise_result)}</dd></div>
      <div><dt>Duración</dt><dd>{session.exercise_duration_seconds == null ? "—" : `${session.exercise_duration_seconds} s`}</dd></div>
      <div><dt>Pasos completados</dt><dd>{session.exercise_steps_total == null ? "—" : `${session.exercise_steps_completed ?? 0} de ${session.exercise_steps_total}${(session.exercise_repetitions ?? 1) > 1 ? ` (${session.exercise_repetitions} repeticiones)` : ""}`}</dd></div>
    </dl>
    <p className="muted">La expresión registrada es una estimación del modelo sobre el rostro visible; no indica lo que sentías.</p>
    {hasQuestionnaires && <section className="card">
      <h2>Cuestionarios</h2>
      <p className="muted">Las respuestas se muestran tal como se dieron; no se suman ni se interpretan.</p>
      {responses.map((item) => <div key={item.id} className="session-answers">
        <h3>{item.moment === "pre" ? "Antes del análisis" : "Después del análisis"}: {item.questionnaire.title} (versión {item.questionnaire.version})</h3>
        <p className="muted">{item.entry_mode === "participant" ? "Respondió quien participa" : "Registradas a mano por quien condujo la sesión"} · {dateTime(item.submitted_at)}</p>
        <AnswerList questionnaire={item.questionnaire} answers={item.answers} />
      </div>)}
      {conductedByMe && session.post_questionnaire_id && !responses.some((item) => item.moment === "post") &&
        <ButtonLink variant="secondary" to={paths.sessionQuestionnaire(session.id, "post")}>Responder el cuestionario posterior</ButtonLink>}
      {conductedByMe && session.pre_questionnaire_id && !responses.some((item) => item.moment === "pre") && session.state !== "cancelled" &&
        <ButtonLink variant="secondary" to={paths.sessionQuestionnaire(session.id, "pre")}>Responder el cuestionario previo</ButtonLink>}
      <QuestionnaireNote />
    </section>}
    <ConfirmDialog open={confirming} title="Cancelar sesión" message={recognitionKept ? "La expresión ya quedó registrada y se conserva; solo se cancelará la actividad." : "La sesión quedará cerrada y no podrá reanudarse."} confirming={cancelling} confirmLabel="Cancelar sesión" onCancel={() => setConfirming(false)} onConfirm={cancelSession} />
  </>}</section>;
}
