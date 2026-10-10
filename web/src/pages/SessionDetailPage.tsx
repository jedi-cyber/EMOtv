import { useState } from "react";
import { useParams } from "react-router-dom";
import { StatusChip, toneForSession } from "../components/StatusChip";
import { ApiError, apiRequest } from "../api/http";
import type { EmotionalSession } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { PageState } from "../components/PageState";
import { Callout } from "../components/Callout";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { useAuth } from "../auth/useAuth";
import { paths } from "../routes/paths";
import { PageHeader } from "../components/PageHeader";
import { activityOutcomeName, sessionStateName } from "../sessions/labels";
import { useExpressionCatalog } from "../expressions/ExpressionCatalog";
import { Button, ButtonLink } from "../components/Button";


export function SessionDetailPage() {
  const { sessionId = "" } = useParams();
  const { token, user } = useAuth();
  const { label: expressionLabel } = useExpressionCatalog();
  const query = useApiQuery<EmotionalSession>(`/sessions/${encodeURIComponent(sessionId)}`);
  const session = query.data;
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  // Psicología solo consulta: cancelar interrumpiría el análisis de un estudiante.
  const canCancel = user?.role !== "psychologist" && (session?.state === "created" || session?.state === "in_progress" || session?.state === "recognized");
  // Con expresión registrada, cancelar conserva el registro y solo cancela la actividad.
  const recognitionKept = Boolean(session?.recognized_at);

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
    <PageHeader title="Detalle de sesión" description={`Identificador: ${session.id}`} actions={canCancel ? <Button variant="danger" type="submit" onClick={() => setConfirming(true)}>Cancelar sesión</Button> : undefined} />
    {message && <Callout variant="success">{message}</Callout>}{error && <Callout variant="error">{error}</Callout>}
    <dl className="detail-grid"><div><dt>Estado</dt><dd><StatusChip tone={toneForSession(session.state)}>{sessionStateName(session.state)}</StatusChip></dd></div><div><dt>Inicio</dt><dd>{new Date(session.started_at).toLocaleString("es-PE")}</dd></div><div><dt>Finalización</dt><dd>{session.completed_at ? new Date(session.completed_at).toLocaleString("es-PE") : "—"}</dd></div><div><dt>Estudiante</dt><dd>{session.student_id ?? "Sin asociación"}</dd></div><div><dt>Actividad</dt><dd>{session.activity_id ?? "—"}</dd></div><div><dt>Modelo facial</dt><dd>{session.emotion_model_id ?? "No registrado"}</dd></div><div><dt>Versión del modelo</dt><dd>{session.emotion_model_version ?? "—"}</dd></div><div><dt>Expresión registrada</dt><dd>{expressionLabel(session.initial_emotion)}</dd></div><div><dt>Expresión registrada el</dt><dd>{session.recognized_at ? new Date(session.recognized_at).toLocaleString("es-PE") : "—"}</dd></div><div><dt>Confianza</dt><dd>{session.emotion_confidence == null ? "—" : `${Math.round(session.emotion_confidence * 100)} %`}</dd></div><div><dt>Resultado de la actividad</dt><dd>{activityOutcomeName(session.exercise_result)}</dd></div><div><dt>Duración</dt><dd>{session.exercise_duration_seconds == null ? "—" : `${session.exercise_duration_seconds} s`}</dd></div><div><dt>Pasos completados</dt><dd>{session.exercise_steps_total == null ? "—" : `${session.exercise_steps_completed ?? 0} de ${session.exercise_steps_total}${(session.exercise_repetitions ?? 1) > 1 ? ` (${session.exercise_repetitions} repeticiones)` : ""}`}</dd></div></dl>
    <ConfirmDialog open={confirming} title="Cancelar sesión" message={recognitionKept ? "La expresión ya quedó registrada y se conserva; solo se cancelará la actividad." : "La sesión quedará cerrada y no podrá reanudarse."} confirming={cancelling} confirmLabel="Cancelar sesión" onCancel={() => setConfirming(false)} onConfirm={cancelSession} />
  </>}</section>;
}
