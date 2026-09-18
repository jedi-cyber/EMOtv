import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, apiRequest, apiWebSocketUrl } from "../api/http";
import type { Activity, EmotionalSession, Student } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { useActiveSession } from "../analysis/ActiveSessionContext";
import { AnalysisNavigationGuard } from "../analysis/AnalysisNavigationGuard";
import { Alert } from "../components/Alert";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { paths } from "../routes/paths";

type Phase = "ready" | "recognizing" | "choosing" | "exercise" | "completed";
type Admission = { model_id: string; state: "SUPPORTED" | "WARNING" | "BLOCKED"; reasons: string[] };
type Landmark = { x: number; y: number; visibility: number };
type Message = {
  type: "ready" | "status" | "recommendation" | "activity_started" | "completed" | "cancelled" | "error";
  state?: string; message?: string; progress?: number;
  emotion?: string | null; emotion_confidence?: number | null;
  activity?: Activity | null; activities?: Activity[];
  landmarks?: Record<string, Landmark> | null;
};

const postureNames: Record<string, string> = {
  arms_up: "Brazos arriba", arms_open: "Brazos abiertos",
  hands_on_hips: "Manos en las caderas", arms_forward: "Brazos al frente", squat: "Sentadilla",
};

export function AdaptiveAnalysisPage() {
  const { token } = useAuth();
  const { setActiveSession } = useActiveSession();
  const modelsQuery = useApiQuery<Admission[]>("/analysis/models");
  const [modelId, setModelId] = useState("ferplus_onnx");
  const admission = modelsQuery.data?.find((item) => item.model_id === modelId);
  const modelBlocked = modelsQuery.loading || Boolean(modelsQuery.error) || !admission || admission.state === "BLOCKED";
  const [phase, setPhase] = useState<Phase>("ready");
  const [starting, setStarting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [includeLandmarks, setIncludeLandmarks] = useState(true);
  const [session, setSession] = useState<EmotionalSession | null>(null);
  const [message, setMessage] = useState("Preparado para reconocer tu expresión facial.");
  const [error, setError] = useState("");
  const [emotion, setEmotion] = useState<string | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [recommendation, setRecommendation] = useState<Activity | null>(null);
  const [availableActivities, setAvailableActivities] = useState<Activity[]>([]);
  const [selectedActivityId, setSelectedActivityId] = useState("");
  const [selectingActivity, setSelectingActivity] = useState(false);
  const [activity, setActivity] = useState<Activity | null>(null);
  const [progress, setProgress] = useState(0);
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

  useEffect(() => {
    setActiveSession(session && phase !== "completed" ? { id: session.id } : null);
    return () => setActiveSession(null);
  }, [session?.id, phase, setActiveSession]);

  useEffect(() => {
    return () => {
      lifecycleRef.current += 1;
      const current = sessionRef.current;
      if (current && !completedRef.current && token) {
        void apiRequest(`/sessions/${current.id}/cancel`, { method: "POST", token, keepalive: true }).catch(() => undefined);
      }
      releaseMedia();
    };
  }, [token]);

  function pauseFrames() {
    if (timerRef.current !== null) window.clearInterval(timerRef.current);
    timerRef.current = null;
  }

  function releaseMedia() {
    pauseFrames();
    if (socketRef.current) {
      socketRef.current.onopen = null; socketRef.current.onmessage = null;
      socketRef.current.onerror = null; socketRef.current.onclose = null;
      socketRef.current.close(); socketRef.current = null;
    }
    awaitingFrame.current = false;
    streamRef.current?.getTracks().forEach((track) => track.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }

  async function previewCamera(): Promise<boolean> {
    if (streamRef.current) return true;
    if (!navigator.mediaDevices?.getUserMedia) {
      setError("La cámara requiere HTTPS o localhost y un navegador compatible.");
      return false;
    }
    setError("");
    const lifecycle = lifecycleRef.current;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      if (lifecycle !== lifecycleRef.current) {
        stream.getTracks().forEach((track) => track.stop());
        return false;
      }
      streamRef.current = stream;
      if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play(); }
      setPreviewing(true);
      return true;
    } catch (reason) {
      releaseMedia();
      if (reason instanceof DOMException && reason.name === "NotAllowedError") setError("Permite el acceso a la cámara en el navegador.");
      else if (reason instanceof DOMException && reason.name === "NotFoundError") setError("No se encontró una cámara en este dispositivo.");
      else setError("No se pudo abrir la cámara. Comprueba sus permisos y que no esté ocupada.");
      return false;
    }
  }

  function sendFrame() {
    const video = videoRef.current; const canvas = captureRef.current; const socket = socketRef.current;
    if (!video || !canvas || !socket || socket.readyState !== WebSocket.OPEN || awaitingFrame.current || video.readyState < 2) return;
    canvas.width = 640; canvas.height = Math.round(640 * video.videoHeight / video.videoWidth) || 480;
    canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
    awaitingFrame.current = true;
    canvas.toBlob((blob) => {
      if (blob && socket.readyState === WebSocket.OPEN) socket.send(blob);
      else awaitingFrame.current = false;
    }, "image/jpeg", .72);
  }

  function resumeFrames() {
    pauseFrames();
    timerRef.current = window.setInterval(sendFrame, 250);
  }

  function drawLandmarks(landmarks: Record<string, Landmark> | null | undefined) {
    const canvas = overlayRef.current;
    const context = canvas?.getContext("2d");
    if (!canvas || !context) return;
    context.clearRect(0, 0, canvas.width, canvas.height);
    if (!includeLandmarks || !landmarks) return;
    context.fillStyle = "#fff";
    for (const point of Object.values(landmarks)) {
      if (point.visibility < .5) continue;
      context.beginPath(); context.arc(point.x * canvas.width, point.y * canvas.height, 4, 0, Math.PI * 2); context.fill();
    }
  }

  function failAnalysis(reason: string) {
    setError(reason);
    releaseMedia(); setPreviewing(false); setPhase("ready");
    const current = sessionRef.current;
    sessionRef.current = null; setSession(null);
    if (current && token && !completedRef.current) {
      void apiRequest(`/sessions/${current.id}/cancel`, { method: "POST", token }).catch(() => undefined);
    }
  }

  async function requireConsent(): Promise<void> {
    if (!token) throw new Error("Inicia sesión nuevamente para continuar.");
    const students = await apiRequest<Student[]>("/students", { token });
    const student = students[0];
    if (!student) throw new Error("Tu cuenta no tiene un perfil de estudiante asociado.");
    const consent = await apiRequest<unknown | null>(`/students/${encodeURIComponent(student.id)}/consents/active`, { token });
    if (!consent) throw new Error("No hay consentimiento activo para iniciar el análisis. Consulta con la institución antes de continuar.");
  }

  async function start() {
    if (modelBlocked || !token) return;
    const lifecycle = lifecycleRef.current;
    setStarting(true); setError(""); completedRef.current = false;
    let created: EmotionalSession | null = null;
    try {
      await requireConsent();
      if (lifecycle !== lifecycleRef.current) return;
      if (!await previewCamera()) return;
      if (lifecycle !== lifecycleRef.current) return;
      created = await apiRequest<EmotionalSession>("/sessions", { method: "POST", body: JSON.stringify({}), token });
      if (lifecycle !== lifecycleRef.current) {
        await apiRequest(`/sessions/${created.id}/cancel`, { method: "POST", token }).catch(() => undefined);
        return;
      }
      sessionRef.current = created; setSession(created);
      const socket = new WebSocket(apiWebSocketUrl("/ws/activity"));
      socket.binaryType = "arraybuffer"; socketRef.current = socket;
      socket.onopen = () => socket.send(JSON.stringify({
        type: "authenticate", token, session_id: created?.id,
        emotion_model_id: modelId, include_landmarks: includeLandmarks,
      }));
      socket.onmessage = (event) => {
        awaitingFrame.current = false;
        let result: Message;
        try { result = JSON.parse(event.data) as Message; }
        catch { failAnalysis("El analizador devolvió una respuesta inválida."); return; }
        if (result.type === "error") { failAnalysis(result.message ?? "No se pudo completar el análisis."); return; }
        if (result.type === "cancelled") { releaseMedia(); setSession(null); sessionRef.current = null; setPhase("ready"); return; }
        setMessage(result.message ?? "Procesando…");
        if (result.emotion) setEmotion(result.emotion);
        if (result.emotion_confidence != null) setConfidence(result.emotion_confidence);
        if (result.type === "ready") { setPhase("recognizing"); resumeFrames(); }
        else if (result.type === "recommendation") {
          pauseFrames(); setPhase("choosing"); setSelectingActivity(false);
          setRecommendation(result.activity ?? null);
          setAvailableActivities(result.activities ?? []);
          setSelectedActivityId(result.activity?.id ?? result.activities?.[0]?.id ?? "");
        } else if (result.type === "activity_started") {
          setActivity(result.activity ?? null); setPhase("exercise"); setSelectingActivity(false); resumeFrames();
        } else if (result.type === "completed") {
          setProgress(1); setPhase("completed"); completedRef.current = true;
          releaseMedia(); setPreviewing(false);
        } else if (result.type === "status") {
          setProgress(result.progress ?? 0); drawLandmarks(result.landmarks);
        }
      };
      socket.onerror = () => failAnalysis("No se pudo conectar con el analizador. Revisa que FastAPI esté activo.");
      socket.onclose = () => failAnalysis("Se perdió la conexión con el analizador. La cámara se apagó.");
    } catch (reason) {
      if (lifecycle !== lifecycleRef.current) {
        if (created) await apiRequest(`/sessions/${created.id}/cancel`, { method: "POST", token }).catch(() => undefined);
        releaseMedia();
        return;
      }
      if (created) {
        await apiRequest(`/sessions/${created.id}/cancel`, { method: "POST", token }).catch(() => undefined);
        sessionRef.current = null; setSession(null); releaseMedia(); setPreviewing(false);
      }
      setError(reason instanceof ApiError ? reason.message : reason instanceof Error ? reason.message : "No se pudo iniciar el análisis.");
    } finally { if (lifecycle === lifecycleRef.current) setStarting(false); }
  }

  function chooseActivity() {
    if (!selectedActivityId || selectingActivity || socketRef.current?.readyState !== WebSocket.OPEN) return;
    setSelectingActivity(true);
    setMessage("Preparando la actividad seleccionada…");
    socketRef.current.send(JSON.stringify({ type: "select_activity", activity_id: selectedActivityId }));
  }

  async function cancel(): Promise<boolean> {
    const current = sessionRef.current;
    if (!current || !token) return false;
    setCancelling(true);
    try {
      await apiRequest(`/sessions/${current.id}/cancel`, { method: "POST", token });
      completedRef.current = true;
      releaseMedia(); setPreviewing(false); sessionRef.current = null; setSession(null);
      setPhase("ready"); setConfirmCancel(false);
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo cancelar la sesión.");
      return false;
    } finally { setCancelling(false); }
  }

  async function cancelForDeparture(): Promise<boolean> {
    const current = sessionRef.current;
    if (!current || !token) return false;
    try {
      await apiRequest(`/sessions/${current.id}/cancel`, { method: "POST", token });
      completedRef.current = true; releaseMedia();
      return true;
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo cancelar la sesión.");
      return false;
    }
  }

  return <section>
    {session && phase !== "completed" && <AnalysisNavigationGuard onLeave={cancelForDeparture} />}
    <PageHeader section="Analizador facial" title="Reconoce tu expresión y recibe una actividad" description="Primero analizamos tu expresión facial. Después podrás revisar una actividad sugerida y decidir si deseas realizarla." />
    {error && <Alert variant="error">{error}</Alert>}
    <div className="analysis-preflight card">
      <div>
        <div className="video-stage adaptive-video-stage">
          <video ref={videoRef} aria-label="Vista previa de tu cámara" playsInline muted />
          <canvas ref={overlayRef} aria-hidden="true" width="640" height="480" />
          <canvas ref={captureRef} hidden />
          {!previewing && <p className="video-placeholder">La cámara está apagada. Puedes probarla antes de iniciar.</p>}
        </div>
        {phase === "ready" && <div className="camera-actions"><div className="inline-actions">
          <button className="button secondary" onClick={() => { void previewCamera(); }}>Probar cámara</button>
          {previewing && <button className="button secondary" onClick={() => { releaseMedia(); setPreviewing(false); }}>Apagar cámara</button>}
        </div><p className="muted">Esta prueba es local: no crea una sesión ni envía imágenes al servidor.</p></div>}
      </div>
      <div className="adaptive-analysis-panel">
        {phase === "ready" && <>
          <h2>Antes de comenzar</h2>
          <p>Necesitas permiso de cámara, <Link to={paths.consent}>consentimiento activo</Link> y un modelo disponible en el servidor.</p>
          <label htmlFor="adaptive-model">Modelo facial</label>
          <select id="adaptive-model" value={modelId} onChange={(event) => setModelId(event.target.value)}>
            <option value="ferplus_onnx">FER+ · ONNX</option>
            <option value="hardlyhumans_vit">HardlyHumans · ViT/PyTorch</option>
          </select>
          <PageState {...modelsQuery} onRetry={modelsQuery.reload} />
          {admission && <Alert variant={admission.state === "BLOCKED" ? "error" : admission.state === "WARNING" ? "warning" : "info"}>{admission.state === "BLOCKED" ? "Modelo no disponible" : admission.state === "WARNING" ? "Modelo con advertencias" : "Modelo disponible"}: {admission.reasons.join("; ") || "listo para usar"}</Alert>}
          <label className="checkbox"><input type="checkbox" checked={includeLandmarks} onChange={(event) => setIncludeLandmarks(event.target.checked)} />Mostrar landmarks durante la actividad</label>
          <button className="button primary" disabled={starting || modelBlocked} onClick={() => { void start(); }}>{starting ? "Preparando análisis…" : "Reconocer mi expresión"}</button>
          <p className="muted">El análisis ocurre en el servidor. Si el modelo está bloqueado, consulta el motivo mostrado arriba.</p>
        </>}
        {phase !== "ready" && <>
          <p className="step-caption">{phase === "recognizing" ? "Paso 1 de 3 · Reconocimiento" : phase === "choosing" ? "Paso 2 de 3 · Actividad sugerida" : "Paso 3 de 3 · Actividad corporal"}</p>
          <span role="status" className="analysis-state">{message}</span>
          {emotion && <p>Expresión detectada: <strong>{emotion}</strong>{confidence != null && ` (${Math.round(confidence * 100)} %)`}</p>}
          {phase === "choosing" && <>
            {recommendation ? <p><strong>Actividad sugerida:</strong> {recommendation.name}. {recommendation.description}</p>
              : <p>No hay una recomendación automática para esta expresión. Puedes elegir una actividad disponible.</p>}
            {availableActivities.length > 0 ? <>
              <label htmlFor="suggested-activity">Actividad que deseas realizar</label>
              <select id="suggested-activity" value={selectedActivityId} onChange={(event) => setSelectedActivityId(event.target.value)}>
                {availableActivities.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
              <button className="button primary" disabled={selectingActivity} onClick={chooseActivity}>{selectingActivity ? "Preparando actividad…" : "Continuar con la actividad"}</button>
            </> : <p>No hay actividades configuradas. Contacta con administración.</p>}
            <p className="muted">Esta sugerencia técnica no constituye una evaluación clínica.</p>
          </>}
          {(phase === "exercise" || phase === "completed") && activity && <>
            <h2>{activity.name}</h2><p>{activity.description}</p>
            <p>Postura: {postureNames[activity.required_posture] ?? activity.required_posture} · Mantén {activity.duration_seconds} s</p>
            <div className="progress-label"><span>Progreso</span><strong>{Math.round(progress * 100)} %</strong></div>
            <div className="progress-track" role="progressbar" aria-label="Progreso de la actividad" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)}><div style={{ width: `${Math.round(progress * 100)}%` }} /></div>
          </>}
          {phase === "completed" && session ? <Link className="button primary action-link" to={paths.session(session.id)}>Ver resultado</Link>
            : <button className="button danger" disabled={cancelling} onClick={() => setConfirmCancel(true)}>Cancelar análisis</button>}
        </>}
      </div>
    </div>
    <ConfirmDialog open={confirmCancel} title="Cancelar análisis" message="Se cancelará la sesión y se apagará la cámara." confirming={cancelling} confirmLabel="Cancelar sesión" onCancel={() => setConfirmCancel(false)} onConfirm={() => { void cancel(); }} />
  </section>;
}
