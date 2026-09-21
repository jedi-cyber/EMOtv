import { useEffect, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { ApiError, apiRequest, apiWebSocketUrl } from "../api/http";
import type { Activity, ActivityStep, EmotionalSession } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Alert } from "../components/Alert";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { PageState } from "../components/PageState";
import { useActiveSession } from "../analysis/ActiveSessionContext";
import { AnalysisNavigationGuard } from "../analysis/AnalysisNavigationGuard";
import { drawPoseOverlay } from "../analysis/drawPoseOverlay";
import type { PoseLandmarks } from "../analysis/drawPoseOverlay";
import { speakExercise, speakStep, speechAvailable, stopExerciseSpeech } from "../analysis/exerciseSpeech";
import { PageHeader } from "../components/PageHeader";
import { AdaptiveAnalysisPage } from "./AdaptiveAnalysisPage";

interface ModelAdmission {
  model_id: string;
  state: "SUPPORTED" | "WARNING" | "BLOCKED";
  reasons: string[];
}
interface AnalysisMessage {
  type: "ready" | "status" | "completed" | "cancelled" | "error";
  state?: string;
  message?: string;
  progress?: number;
  emotion?: string | null;
  emotion_confidence?: number | null;
  landmarks?: PoseLandmarks | null;
  admission?: ModelAdmission | null;
  step?: ActivityStep; step_index?: number; step_count?: number;
}

const postureNames: Record<string, string> = {
  arms_up: "Brazos arriba", arms_open: "Brazos abiertos",
  arms_forward: "Brazos al frente", hands_on_hips: "Manos en las caderas",
  squat: "Sentadilla",
};
const stateNames: Record<string, string> = {
  analyzing_emotion: "Analizando emoción", waiting_for_posture: "Postura incorrecta",
  performing_exercise: "Manteniendo postura", completed: "Actividad completada",
};
const analysisSteps = ["Reconocer expresión", "Preparar postura", "Realizar actividad"];

export function AnalysisPage() {
  const [params] = useSearchParams();
  return params.has("activity") ? <ManualActivityAnalysisPage /> : <AdaptiveAnalysisPage />;
}

function ManualActivityAnalysisPage() {
  const [params] = useSearchParams();
  const { token } = useAuth();
  const { setActiveSession } = useActiveSession();
  const activityId = params.get("activity") ?? "";
  const query = useApiQuery<Activity>(activityId ? `/activities/${encodeURIComponent(activityId)}` : null);
  const modelsQuery = useApiQuery<ModelAdmission[]>("/analysis/models");
  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const captureRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const socketRef = useRef<WebSocket | null>(null);
  const timerRef = useRef<number | null>(null);
  const awaitingFrame = useRef(false);
  const sessionRef = useRef<EmotionalSession | null>(null);
  const completedRef = useRef(false);
  const lifecycleRef = useRef(0);
  const announcedStepRef = useRef(-1);
  const [session, setSession] = useState<EmotionalSession | null>(null);
  const [starting, setStarting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [includeLandmarks, setIncludeLandmarks] = useState(true);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [emotionModelId, setEmotionModelId] = useState("ferplus_onnx");
  const selectedAdmission = modelsQuery.data?.find((item) => item.model_id === emotionModelId);
  const modelBlocked = !selectedAdmission || selectedAdmission.state === "BLOCKED" || modelsQuery.loading || Boolean(modelsQuery.error);
  const [status, setStatus] = useState<AnalysisMessage>({ type: "ready", state: "analyzing_emotion", message: "Preparado", progress: 0 });
  const [error, setError] = useState("");
  useEffect(() => {
    setActiveSession(session && status.type !== "completed" ? { id: session.id, activityId } : null);
    return () => setActiveSession(null);
  }, [session?.id, status.type, activityId, setActiveSession]);
  useEffect(() => {
    if (session || starting) return;
    const timer = window.setInterval(() => { void modelsQuery.reload(); }, 10000);
    return () => window.clearInterval(timer);
  }, [session, starting, modelsQuery.reload]);

  function releaseMedia() {
    stopExerciseSpeech();
    if (timerRef.current !== null) window.clearInterval(timerRef.current);
    timerRef.current = null;
    if (socketRef.current) {
      socketRef.current.onclose = null; socketRef.current.onerror = null;
      socketRef.current.onmessage = null; socketRef.current.onopen = null;
      socketRef.current.close(); socketRef.current = null;
    }
    awaitingFrame.current = false;
    streamRef.current?.getTracks().forEach((track) => track.stop()); streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }

  useEffect(() => {
    sessionRef.current = null; setSession(null); setStarting(false);
    return () => {
    lifecycleRef.current += 1;
    const current = sessionRef.current;
    if (current && !completedRef.current && token) {
      void apiRequest(`/sessions/${current.id}/cancel`, { method: "POST", token, keepalive: true }).catch(() => undefined);
    }
    releaseMedia();
    };
  }, [token, activityId]);

  function failAnalysis(message: string) {
    setError(message);
    const current = sessionRef.current;
    releaseMedia();
    if (current && token && !completedRef.current) {
      void apiRequest(`/sessions/${current.id}/cancel`, { method: "POST", token }).catch(() => undefined);
    }
    sessionRef.current = null; setSession(null);
  }

  function drawLandmarks(landmarks: PoseLandmarks | null | undefined) {
    drawPoseOverlay(overlayRef.current, landmarks, includeLandmarks);
  }

  function sendFrame() {
    const video = videoRef.current; const canvas = captureRef.current; const socket = socketRef.current;
    if (!video || !canvas || !socket || socket.readyState !== WebSocket.OPEN || awaitingFrame.current || video.readyState < 2) return;
    canvas.width = 640; canvas.height = Math.round(640 * video.videoHeight / video.videoWidth) || 480;
    if (overlayRef.current && (overlayRef.current.width !== canvas.width || overlayRef.current.height !== canvas.height)) {
      overlayRef.current.width = canvas.width;
      overlayRef.current.height = canvas.height;
    }
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
    awaitingFrame.current = true;
    canvas.toBlob((blob) => {
      if (blob && socket.readyState === WebSocket.OPEN) socket.send(blob);
      else awaitingFrame.current = false;
    }, "image/jpeg", .72);
  }

  async function start() {
    if (!query.data || !token) return;
    if (modelBlocked) { setError("El modelo seleccionado no está autorizado para iniciar. Actualiza la evaluación."); return; }
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("La cámara no está disponible. Usa un navegador compatible y HTTPS o localhost.");
      return;
    }
    const lifecycle = lifecycleRef.current;
    setStarting(true); setError(""); completedRef.current = false;
    setStatus({ type: "ready", state: "analyzing_emotion", message: "Preparado", progress: 0 });
    announcedStepRef.current = -1;
    let created: EmotionalSession | null = null;
    try {
      created = await apiRequest<EmotionalSession>("/sessions", { method: "POST", body: JSON.stringify({ activity_id: activityId }), token });
      if (lifecycle !== lifecycleRef.current) {
        await apiRequest(`/sessions/${created.id}/cancel`, { method: "POST", token }).catch(() => undefined);
        return;
      }
      sessionRef.current = created; setSession(created);
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 960 }, height: { ideal: 720 } }, audio: false });
      if (lifecycle !== lifecycleRef.current) { stream.getTracks().forEach((track) => track.stop()); return; }
      streamRef.current = stream;
      if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play(); }
      if (lifecycle !== lifecycleRef.current) return;
      const socket = new WebSocket(apiWebSocketUrl("/ws/activity")); socket.binaryType = "arraybuffer"; socketRef.current = socket;
      socket.onopen = () => {
        setStatus({ type: "ready", state: "analyzing_emotion", message: "Cargando modelo facial en el servidor…", progress: 0 });
        socket.send(JSON.stringify({ type: "authenticate", token, session_id: created?.id, activity_id: activityId, include_landmarks: includeLandmarks, emotion_model_id: emotionModelId }));
      };
      socket.onmessage = (event) => {
        awaitingFrame.current = false;
        let message: AnalysisMessage;
        try { message = JSON.parse(event.data) as AnalysisMessage; }
        catch { failAnalysis("El analizador devolvió una respuesta inválida."); return; }
        if (message.type === "error") { failAnalysis(message.message ?? "Error durante el análisis"); return; }
        if (message.type === "cancelled") { releaseMedia(); sessionRef.current = null; setSession(null); return; }
        setStatus(message); drawLandmarks(message.landmarks);
        if (message.type === "ready" && timerRef.current === null) {
          timerRef.current = window.setInterval(sendFrame, 250);
          if (voiceEnabled && activity) {
            if (activity.steps?.[0]) speakStep(activity.steps[0], 0, activity.steps.length * activity.repetitions);
            else speakExercise(activity);
            announcedStepRef.current = 0;
          }
        }
        if (message.type === "status" && message.step && message.step_index != null &&
            voiceEnabled && announcedStepRef.current !== message.step_index) {
          speakStep(message.step, message.step_index, message.step_count ?? 1);
          announcedStepRef.current = message.step_index;
        }
        if (message.type === "completed") { completedRef.current = true; releaseMedia(); }
      };
      socket.onerror = () => failAnalysis("No se pudo conectar con el analizador.");
      socket.onclose = () => failAnalysis("Se perdió la conexión con el analizador. La cámara se ha apagado.");
    } catch (reason) {
      if (lifecycle !== lifecycleRef.current) {
        if (created) await apiRequest(`/sessions/${created.id}/cancel`, { method: "POST", token }).catch(() => undefined);
        return;
      }
      releaseMedia();
      if (created) { await apiRequest(`/sessions/${created.id}/cancel`, { method: "POST", token }).catch(() => undefined); sessionRef.current = null; setSession(null); }
      if (reason instanceof DOMException && reason.name === "NotAllowedError") setError("Debes permitir el acceso a la cámara para continuar.");
      else if (reason instanceof DOMException && reason.name === "NotFoundError") setError("No se encontró una cámara conectada a tu dispositivo.");
      else if (reason instanceof ApiError && reason.status === 403 && /consentimiento/i.test(reason.message))
        setError("No se puede iniciar el análisis sin consentimiento activo. Registra el consentimiento correspondiente antes de usar la cámara.");
      else setError(reason instanceof ApiError ? reason.message : "No fue posible iniciar la cámara.");
    } finally { if (lifecycle === lifecycleRef.current) setStarting(false); }
  }

  async function cancel(): Promise<boolean> {
    if (!session || !token) return false;
    setCancelling(true);
    try {
      await apiRequest(`/sessions/${session.id}/cancel`, { method: "POST", token });
      sessionRef.current = null; setSession(null); setConfirmCancel(false); releaseMedia();
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo cancelar la sesión");
      return false;
    } finally { setCancelling(false); }
  }

  async function cancelForDeparture(): Promise<boolean> {
    const current = sessionRef.current;
    if (!current || !token) return false;
    try {
      await apiRequest(`/sessions/${current.id}/cancel`, { method: "POST", token });
      completedRef.current = true;
      releaseMedia();
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo cancelar la sesión");
      return false;
    }
  }

  if (!activityId) return <section><PageHeader section="Analizador facial" title="Selecciona una actividad" description="Elige una actividad corporal para preparar el análisis." /><Link className="button primary action-link" to="/activities">Ver actividades</Link></section>;
  const activity = query.data;
  const progress = Math.round(Math.max(0, Math.min(1, status.progress ?? 0)) * 100);
  const stepIndex = status.state === "completed" || status.state === "performing_exercise" ? 2 : status.state === "waiting_for_posture" ? 1 : 0;
  return <section>{session && status.type !== "completed" && <AnalysisNavigationGuard onLeave={cancelForDeparture} />}{(!session || status.type === "completed") && <Link className="back-link" to="/activities">← Volver a actividades</Link>}<PageHeader section="Actividad corporal" title={activity?.name ?? "Actividad"} description={activity?.description ?? "Preparando el análisis de tu actividad."} /><PageState {...query} onRetry={query.reload} />{error && <Alert variant="error">{error}</Alert>}
    {activity && !session && <div className="analysis-preflight card"><div><span className="pill">{postureNames[activity.required_posture] ?? activity.required_posture}</span><h2>Instrucciones</h2><p>{activity.description}</p><dl className="metadata"><div><dt>Duración</dt><dd>{activity.duration_seconds} s</dd></div><div><dt>Repeticiones</dt><dd>{activity.repetitions}</dd></div></dl></div><div className="preflight-actions"><label className="checkbox"><input type="checkbox" checked={includeLandmarks} onChange={(event) => setIncludeLandmarks(event.target.checked)} />Mostrar puntos y líneas</label><label className="checkbox"><input type="checkbox" checked={voiceEnabled} disabled={!speechAvailable()} onChange={(event) => setVoiceEnabled(event.target.checked)} />Leer instrucciones en voz alta</label><p className="muted">El navegador solicitará permiso para utilizar tu cámara.</p><button className="button primary" disabled={starting || modelBlocked} onClick={start}>{starting ? "Iniciando…" : "Permitir cámara e iniciar"}</button></div></div>}
    {activity && !session && <fieldset className="card" disabled={starting}>
      <legend>Modelo de reconocimiento facial</legend>
      <label htmlFor="emotion-model">Modelo de reconocimiento facial</label>
      <select id="emotion-model" value={emotionModelId} onChange={(event) => setEmotionModelId(event.target.value)} aria-describedby="emotion-model-help">
        <option value="ferplus_onnx" disabled={modelsQuery.data?.find((item) => item.model_id === "ferplus_onnx")?.state === "BLOCKED"}>FER+ · ONNX (predeterminado)</option>
        <option value="hardlyhumans_vit" disabled={modelsQuery.data?.find((item) => item.model_id === "hardlyhumans_vit")?.state === "BLOCKED"}>HardlyHumans · ViT/PyTorch (experimental)</option>
      </select>
      <p id="emotion-model-help" className="muted">Elige el modelo que prefieras según su disponibilidad y rendimiento en el servidor. FER+ suele requerir menos recursos; HardlyHumans puede tardar más y usar más RAM. En esta versión el análisis ocurre en el servidor, no en tu dispositivo. No se ha demostrado que uno reconozca mejor las emociones en EMOtv. Puedes cambiarlo antes de iniciar la sesión.</p>
      <PageState {...modelsQuery} onRetry={modelsQuery.reload} />
      {selectedAdmission && <Alert variant={selectedAdmission.state === "BLOCKED" ? "error" : selectedAdmission.state === "WARNING" ? "warning" : "info"}>
        {selectedAdmission.state}: {selectedAdmission.reasons.join("; ") || "Recursos suficientes según evaluación del servidor"}
      </Alert>}
      <button className="button" onClick={modelsQuery.reload}>Actualizar evaluación</button>
    </fieldset>}
    {session && <div className="live-analysis">
      <div className="video-stage"><video ref={videoRef} aria-label="Vista previa de tu cámara" playsInline muted /><canvas ref={overlayRef} aria-hidden="true" width="640" height="480" /><canvas ref={captureRef} hidden /></div>
      <aside className="analysis-panel">
        <p className="step-caption">Etapa {stepIndex + 1} de {analysisSteps.length}</p>
        <ol className="analysis-steps" aria-label="Etapas del análisis">{analysisSteps.map((step, index) => <li key={step} className={index < stepIndex ? "done" : index === stepIndex ? "current" : "upcoming"} aria-current={index === stepIndex ? "step" : undefined}>{step}</li>)}</ol>
        <p>Modelo facial: {emotionModelId === "ferplus_onnx" ? "FER+ · ONNX" : "HardlyHumans · ViT/PyTorch (experimental)"}</p>
        {status.admission?.state === "WARNING" && <Alert variant="warning">{status.admission.reasons.join("; ")}</Alert>}
        <span role="status" aria-live="polite" className={`analysis-state state-${status.state}`}>{stateNames[status.state ?? ""] ?? status.state}</span>
        <h2>{status.message}</h2><p>{status.step ? `Paso ${(status.step_index ?? 0) + 1} de ${status.step_count ?? 1}: ${status.step.instruction}` : activity?.description}</p>
        {activity && status.type !== "completed" && speechAvailable() && <button className="button secondary" onClick={() => status.step ? speakStep(status.step, status.step_index ?? 0, status.step_count ?? 1) : speakExercise(activity)}>Repetir instrucción</button>}
        {status.emotion && <p>Emoción inicial: <strong>{status.emotion}</strong> ({Math.round((status.emotion_confidence ?? 0) * 100)} %)</p>}
        <div className="progress-label"><span>Progreso</span><strong>{progress} %</strong></div>
        <div className="progress-track" role="progressbar" aria-label="Progreso de la actividad" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><div style={{ width: `${progress}%` }} /></div>
        {status.type !== "completed" ? <button className="button danger" onClick={() => setConfirmCancel(true)}>Cancelar sesión</button> : <Link className="button primary action-link" to={`/sessions/${session.id}`}>Ver resultado</Link>}
      </aside></div>}
    <ConfirmDialog open={confirmCancel} title="Cancelar actividad" message="Se cerrará la sesión y se apagará la cámara." confirming={cancelling} confirmLabel="Cancelar actividad" onCancel={() => setConfirmCancel(false)} onConfirm={cancel} />
  </section>;
}
