import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { ApiError, apiRequest } from "../api/http";
import type { EmotionalSession } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { PageState } from "../components/PageState";
import { Alert } from "../components/Alert";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { useAuth } from "../auth/useAuth";

const stateNames = { created: "Creada", in_progress: "En progreso", completed: "Completada", cancelled: "Cancelada" };

export function SessionDetailPage() {
  const { sessionId = "" } = useParams();
  const { token } = useAuth();
  const query = useApiQuery<EmotionalSession>(`/sessions/${encodeURIComponent(sessionId)}`);
  const session = query.data;
  const [confirming, setConfirming] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const canCancel = session?.state === "created" || session?.state === "in_progress";

  async function cancelSession() {
    if (!session) return;
    setCancelling(true); setError(""); setMessage("");
    try {
      await apiRequest<EmotionalSession>(`/sessions/${encodeURIComponent(session.id)}/cancel`, { method: "POST", token });
      setConfirming(false); setMessage("La sesión fue cancelada correctamente."); await query.reload();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "No se pudo cancelar la sesión"); setConfirming(false); }
    finally { setCancelling(false); }
  }
  return <section><Link className="back-link" to="/sessions">← Volver a sesiones</Link><PageState {...query} onRetry={query.reload} />{session && <>
    <div className="page-heading"><div><p className="eyebrow">Detalle de sesión</p><h1>{session.id}</h1></div>{canCancel && <button className="button danger" onClick={() => setConfirming(true)}>Cancelar sesión</button>}</div>
    {message && <Alert variant="success">{message}</Alert>}{error && <Alert variant="error">{error}</Alert>}
    <dl className="detail-grid"><div><dt>Estado</dt><dd><span className={`status status-${session.state}`}>{stateNames[session.state]}</span></dd></div><div><dt>Inicio</dt><dd>{new Date(session.started_at).toLocaleString("es-PE")}</dd></div><div><dt>Finalización</dt><dd>{session.completed_at ? new Date(session.completed_at).toLocaleString("es-PE") : "—"}</dd></div><div><dt>Estudiante</dt><dd>{session.student_id ?? "Sin asociación"}</dd></div><div><dt>Actividad</dt><dd>{session.activity_id ?? "—"}</dd></div><div><dt>Modelo facial</dt><dd>{session.emotion_model_id ?? "No registrado"}</dd></div><div><dt>Versión del modelo</dt><dd>{session.emotion_model_version ?? "—"}</dd></div><div><dt>Emoción inicial</dt><dd>{session.initial_emotion ?? "—"}</dd></div><div><dt>Confianza</dt><dd>{session.emotion_confidence == null ? "—" : `${Math.round(session.emotion_confidence * 100)} %`}</dd></div><div><dt>Resultado</dt><dd>{session.exercise_result ?? "—"}</dd></div><div><dt>Duración</dt><dd>{session.exercise_duration_seconds == null ? "—" : `${session.exercise_duration_seconds} s`}</dd></div></dl>
    <ConfirmDialog open={confirming} title="Cancelar sesión" message="La sesión quedará cerrada y no podrá reanudarse." confirming={cancelling} confirmLabel="Cancelar sesión" onCancel={() => setConfirming(false)} onConfirm={cancelSession} />
  </>}</section>;
}
