import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { ApiError, SESSION_EXPIRED_ANALYSIS_MESSAGE, SESSION_EXPIRED_CLOSE_CODE, apiRequest, apiWebSocketUrl, notifySessionExpired } from "../api/http";
import type { Activity, ActivityStep, EmotionalSession, Student } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { useActiveSession } from "../analysis/ActiveSessionContext";
import { AnalysisNavigationGuard } from "../analysis/AnalysisNavigationGuard";
import { drawPoseOverlay } from "../analysis/drawPoseOverlay";
import type { PoseLandmarks } from "../analysis/drawPoseOverlay";
import { speakExercise, speakStep, speechAvailable, stopExerciseSpeech } from "../analysis/exerciseSpeech";
import { Alert } from "../components/Alert";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { paths } from "../routes/paths";
import { useExpressionCatalog } from "../expressions/ExpressionCatalog";
import type { ExpressionInfo } from "../expressions/ExpressionCatalog";
import { ExpressionResult } from "../expressions/ExpressionResult";
import { LiveExpressionPanel, percent, type LiveReading } from "../analysis/LiveExpressionPanel";

type Phase = "ready" | "live" | "result" | "exercise" | "completed";
type Admission = { model_id: string; state: "SUPPORTED" | "WARNING" | "BLOCKED"; reasons: string[] };
type Message = Partial<LiveReading> & {
  type: "ready" | "live" | "confirm_rejected" | "recognized" | "status" | "recommendation" | "activity_started" | "completed" | "cancelled" | "error";
  state?: string; message?: string; progress?: number; code?: number;
  emotion?: string | null; emotion_confidence?: number | null;
  activity?: Activity | null; activities?: Activity[];
  step?: ActivityStep; step_index?: number; step_count?: number;
  landmarks?: PoseLandmarks | null;
  exercise_result?: string | null; recognition_kept?: boolean;
  expression?: ExpressionInfo | null;
  notice?: string | null; stage?: string;
};


const postureNames: Record<string, string> = {
  arms_up: "Brazos arriba", arms_open: "Brazos abiertos",
  hands_on_hips: "Manos en las caderas", arms_forward: "Brazos al frente", squat: "Sentadilla",
};

export function AdaptiveAnalysisPage() {
  const { token, user } = useAuth();
  // Solo administración elige modelo; el estudiante usa siempre FER+ (el servidor lo exige).
  const canChooseModel = user?.role === "admin";
  const { setActiveSession } = useActiveSession();
  const modelsQuery = useApiQuery<Admission[]>(canChooseModel ? "/analysis/models" : null);
  const [modelId, setModelId] = useState("ferplus_onnx");
  const admission = modelsQuery.data?.find((item) => item.model_id === modelId);
  const modelBlocked = canChooseModel && (modelsQuery.loading || Boolean(modelsQuery.error) || !admission || admission.state === "BLOCKED");
  const [phase, setPhase] = useState<Phase>("ready");
  const [starting, setStarting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [previewing, setPreviewing] = useState(false);
  const [includeLandmarks, setIncludeLandmarks] = useState(true);
  const [voiceEnabled, setVoiceEnabled] = useState(true);
  const [session, setSession] = useState<EmotionalSession | null>(null);
  const [message, setMessage] = useState("Preparado para reconocer tu expresión facial.");
  const [error, setError] = useState("");
  // emotion/confidence: solo la expresión registrada. La lectura en vivo vive
  // en `live` y se descarta; no se guarda en ningún almacenamiento del navegador.
  const [emotion, setEmotion] = useState<string | null>(null);
  const [confidence, setConfidence] = useState<number | null>(null);
  const [live, setLive] = useState<LiveReading | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [confirmNotice, setConfirmNotice] = useState("");
  const [outcome, setOutcome] = useState<string | null>(null);
  const [notice, setNotice] = useState("");
  const [expressionInfo, setExpressionInfo] = useState<ExpressionInfo | null>(null);
  const restartAfterFinishRef = useRef(false);
  const { label: expressionLabel } = useExpressionCatalog();
  const expressionRecorded = phase === "result" || phase === "exercise";
  const [recommendation, setRecommendation] = useState<Activity | null>(null);
  const [availableActivities, setAvailableActivities] = useState<Activity[]>([]);
  const [selectedActivityId, setSelectedActivityId] = useState("");
  const [selectingActivity, setSelectingActivity] = useState(false);
  const [showAlternatives, setShowAlternatives] = useState(false);
  const [activity, setActivity] = useState<Activity | null>(null);
  const [progress, setProgress] = useState(0);
  const [currentStep, setCurrentStep] = useState<ActivityStep | null>(null);
  const [stepNumber, setStepNumber] = useState(0);
  const [stepCount, setStepCount] = useState(1);
  const announcedStepRef = useRef(-1);
  const videoRef = useRef<HTMLVideoElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const lastLandmarksRef = useRef<PoseLandmarks | null>(null);
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
    stopExerciseSpeech();
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
    lastLandmarksRef.current = null;
    drawPoseOverlay(overlayRef.current, null);
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

  function resumeFrames() {
    pauseFrames();
    timerRef.current = window.setInterval(sendFrame, 250);
  }

  function drawLandmarks(landmarks: PoseLandmarks | null | undefined) {
    lastLandmarksRef.current = landmarks ?? null;
    drawPoseOverlay(overlayRef.current, landmarks, includeLandmarks);
  }

  function expireAnalysis() {
    failAnalysis(SESSION_EXPIRED_ANALYSIS_MESSAGE);
    notifySessionExpired();
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
    const policy = await apiRequest<{ id?: string | null; version: string | null; mode?: string; available: boolean }>("/consent-policy", { token });
    if (policy.mode === "development") return;
    if (!policy.available) throw new Error("No hay una política de consentimiento activa. Consulta con administración.");
    const students = await apiRequest<Student[]>("/students", { token });
    const student = students[0];
    if (!student) throw new Error("Tu cuenta no tiene un perfil de estudiante asociado.");
    const consent = await apiRequest<{ policy_version: string } | null>(`/students/${encodeURIComponent(student.id)}/consents/active`, { token });
    if (!consent || consent.policy_version !== (policy.id ?? policy.version))
      throw new Error("Debes aceptar la versión vigente del consentimiento antes de iniciar el análisis.");
  }

  async function start() {
    if (modelBlocked || !token) return;
    const lifecycle = lifecycleRef.current;
    setStarting(true); setError(""); setNotice(""); completedRef.current = false;
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
        if (result.type === "error" && result.code === SESSION_EXPIRED_CLOSE_CODE) { expireAnalysis(); return; }
        if (result.type === "error") { failAnalysis(result.message ?? "No se pudo completar el análisis."); return; }
        if (result.type === "cancelled") {
          releaseMedia(); setSession(null); sessionRef.current = null; setPhase("ready"); setLive(null);
          if (result.recognition_kept) setNotice("Actividad cancelada. Tu expresión quedó registrada.");
          return;
        }
        if (result.type === "live") {
          // Lectura momentánea: solo se muestra; no se acumula ni se persiste.
          setLive({
            face_detected: Boolean(result.face_detected), emotion: result.emotion ?? null,
            emotion_confidence: result.emotion_confidence ?? null, top: result.top ?? [],
            stable_seconds: result.stable_seconds ?? 0, required_stable_seconds: result.required_stable_seconds ?? 1,
            can_confirm: Boolean(result.can_confirm), blocked_reason: result.blocked_reason ?? null,
          });
          return;
        }
        if (result.type === "confirm_rejected") {
          setConfirming(false); setConfirmNotice(result.message ?? "Todavía no se puede registrar la expresión.");
          return;
        }
        setMessage(result.message ?? "Procesando…");
        if (result.type !== "status" && result.emotion) setEmotion(result.emotion);
        if (result.type !== "status" && result.emotion_confidence != null) setConfidence(result.emotion_confidence);
        if (result.type === "ready") { setPhase("live"); resumeFrames(); }
        else if (result.type === "recognized") {
          // El servidor responde con la expresión que realmente registró.
          pauseFrames(); setConfirming(false); setConfirmNotice(""); setLive(null); setPhase("result");
        } else if (result.type === "recommendation") {
          setExpressionInfo(result.expression ?? null);
          if (result.notice) setNotice(result.notice);
          setSelectingActivity(false);
          setShowAlternatives(false);
          setRecommendation(result.activity ?? null);
          setAvailableActivities(result.activities ?? []);
          setSelectedActivityId(result.activity?.id ?? result.activities?.[0]?.id ?? "");
        } else if (result.type === "activity_started") {
          setActivity(result.activity ?? null); setPhase("exercise"); setSelectingActivity(false); resumeFrames();
          const firstStep = result.activity?.steps?.[0];
          setCurrentStep(firstStep ?? null);
          setStepNumber(0);
          setStepCount((result.activity?.steps?.length ?? 1) * (result.activity?.repetitions ?? 1));
          announcedStepRef.current = 0;
          if (voiceEnabled && result.activity) {
            if (firstStep) speakStep(firstStep, 0, (result.activity.steps?.length ?? 1) * result.activity.repetitions);
            else speakExercise(result.activity);
          }
        } else if (result.type === "completed") {
          if (restartAfterFinishRef.current) {
            // "Analizar otra expresión": esta sesión ya quedó cerrada como omitida; se inicia otra.
            restartAfterFinishRef.current = false; completedRef.current = true; analyzeAgain(); return;
          }
          setOutcome(result.exercise_result ?? null);
          setProgress(result.exercise_result === "completed" ? 1 : 0); setPhase("completed"); completedRef.current = true;
          releaseMedia(); setPreviewing(false);
        } else if (result.type === "status") {
          setProgress(result.progress ?? 0); drawLandmarks(result.landmarks);
          if (result.step && result.step_index != null) {
            setCurrentStep(result.step); setStepNumber(result.step_index);
            setStepCount(result.step_count ?? 1);
            if (voiceEnabled && result.step_index !== announcedStepRef.current) {
              announcedStepRef.current = result.step_index;
              speakStep(result.step, result.step_index, result.step_count ?? 1);
            }
          }
        }
      };
      socket.onerror = () => failAnalysis("No se pudo conectar con el analizador. Revisa que FastAPI esté activo.");
      socket.onclose = (event) => event?.code === SESSION_EXPIRED_CLOSE_CODE
        ? expireAnalysis()
        : failAnalysis("Se perdió la conexión con el analizador. La cámara se apagó.");
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

  function chooseActivity(activityId = selectedActivityId) {
    if (!activityId || selectingActivity || socketRef.current?.readyState !== WebSocket.OPEN) return;
    setSelectingActivity(true);
    setMessage("Preparando la actividad seleccionada…");
    socketRef.current.send(JSON.stringify({ type: "select_activity", activity_id: activityId }));
  }

  function confirmExpression() {
    if (!live?.can_confirm || confirming || socketRef.current?.readyState !== WebSocket.OPEN) return;
    // Sin etiqueta: el servidor registra su propio último resultado estable.
    setConfirming(true); setConfirmNotice("");
    socketRef.current.send(JSON.stringify({ type: "confirm_expression" }));
  }

  function finishWithoutActivity(analyzeAnother = false) {
    if (selectingActivity || socketRef.current?.readyState !== WebSocket.OPEN) return;
    setSelectingActivity(true);
    restartAfterFinishRef.current = analyzeAnother;
    socketRef.current.send(JSON.stringify({ type: "finish_without_activity" }));
  }

  function showOtherActivities() {
    const firstAlternative = availableActivities.find(
      (item) => item.id !== recommendation?.id,
    );
    setSelectedActivityId(firstAlternative?.id ?? "");
    setShowAlternatives(true);
  }

  function analyzeAgain() {
    if (starting) return;
    releaseMedia();
    sessionRef.current = null;
    setSession(null);
    setPreviewing(false);
    setEmotion(null);
    setConfidence(null);
    setLive(null);
    setConfirming(false);
    setConfirmNotice("");
    setOutcome(null);
    setExpressionInfo(null);
    setSelectingActivity(false);
    setNotice("");
    setRecommendation(null);
    setAvailableActivities([]);
    setShowAlternatives(false);
    setSelectedActivityId("");
    setActivity(null);
    setCurrentStep(null);
    setStepNumber(0);
    setStepCount(1);
    announcedStepRef.current = -1;
    setProgress(0);
    setMessage("Preparando un nuevo reconocimiento facial…");
    setError("");
    setPhase("ready");
    void start();
  }

  async function cancel(): Promise<boolean> {
    const current = sessionRef.current;
    if (!current || !token) return false;
    setCancelling(true);
    try {
      await apiRequest(`/sessions/${current.id}/cancel`, { method: "POST", token });
      completedRef.current = true;
      releaseMedia(); setPreviewing(false); sessionRef.current = null; setSession(null);
      setNotice(expressionRecorded ? "Actividad cancelada. Tu expresión quedó registrada." : "");
      setLive(null); setPhase("ready"); setConfirmCancel(false);
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
    {notice && <Alert variant="info">{notice}</Alert>}
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
          {canChooseModel && <>
            <label htmlFor="adaptive-model">Modelo facial</label>
            <select id="adaptive-model" value={modelId} onChange={(event) => setModelId(event.target.value)}>
              <option value="ferplus_onnx">FER+ · ONNX</option>
              <option value="hardlyhumans_vit">HardlyHumans · ViT/PyTorch</option>
            </select>
            <PageState {...modelsQuery} onRetry={modelsQuery.reload} />
            {admission && <Alert variant={admission.state === "BLOCKED" ? "error" : admission.state === "WARNING" ? "warning" : "info"}>{admission.state === "BLOCKED" ? "Modelo no disponible" : admission.state === "WARNING" ? "Modelo con advertencias" : "Modelo disponible"}: {admission.reasons.join("; ") || "listo para usar"}</Alert>}
          </>}
          <label className="checkbox"><input type="checkbox" checked={includeLandmarks} onChange={(event) => { setIncludeLandmarks(event.target.checked); drawPoseOverlay(overlayRef.current, lastLandmarksRef.current, event.target.checked); }} />Mostrar puntos y líneas durante la actividad</label>
          <label className="checkbox"><input type="checkbox" checked={voiceEnabled} disabled={!speechAvailable()} onChange={(event) => setVoiceEnabled(event.target.checked)} />Leer instrucciones en voz alta</label>
          <button className="button primary" disabled={starting || modelBlocked} onClick={() => { void start(); }}>{starting ? "Preparando análisis…" : "Reconocer mi expresión"}</button>
          <p className="muted">El análisis ocurre en el servidor. {canChooseModel ? "Si el modelo está bloqueado, consulta el motivo mostrado arriba." : "Si el servidor no puede analizar, te mostraremos el motivo."}</p>
        </>}
        {phase !== "ready" && <>
          <p className="step-caption">{phase === "live" ? "Paso 1 de 3 · Expresión en vivo" : phase === "result" ? "Paso 2 de 3 · Resultado y actividad sugerida" : "Paso 3 de 3 · Actividad corporal"}</p>
          {phase !== "live" && <span role="status" className="analysis-state">{message}</span>}
          {phase === "live" && <LiveExpressionPanel live={live} />}
          {phase === "live" && <>
            <button className="button primary" disabled={!live?.can_confirm || confirming} aria-describedby="confirm-help" onClick={confirmExpression}>{confirming ? "Registrando…" : "Registrar esta expresión"}</button>
            <p id="confirm-help" className="muted">{confirmNotice || (live?.can_confirm ? "Puedes registrar la expresión que ves ahora. Se guarda solo la que registres." : live?.blocked_reason ?? "Esperando la primera lectura del modelo.")}</p>
          </>}
          {phase !== "live" && phase !== "result" && emotion && <p>Expresión registrada: <strong>{expressionLabel(emotion)}</strong>{confidence != null && ` (${percent(confidence)} %)`}</p>}
          {phase === "result" && emotion && <ExpressionResult expressionKey={emotion} confidence={confidence} info={expressionInfo} />}
          {phase === "result" && <>
            {recommendation ? <div className="recommendation-card">
              <p className="step-caption">Actividad recomendada</p>
              <h2>{recommendation.name}</h2>
              <p>{recommendation.description}</p>
              <p className="muted">{recommendation.steps?.length ?? 1} pasos · Duración estimada: {(recommendation.steps?.reduce((total, step) => total + step.duration_seconds, 0) ?? recommendation.duration_seconds) * recommendation.repetitions} s</p>
              <div className="recommendation-steps">
                <h3>Pasos de la actividad</h3>
                <ol>
                  {recommendation.steps?.length ? recommendation.steps.map((step, index) => <li key={`${step.posture}-${index}`}>
                    <span>{step.instruction}</span>
                    <small>{postureNames[step.posture] ?? step.posture} · {step.duration_seconds} s</small>
                  </li>) : <li>
                    <span>{recommendation.description}</span>
                    <small>{postureNames[recommendation.required_posture] ?? recommendation.required_posture} · {recommendation.duration_seconds} s</small>
                  </li>}
                </ol>
              </div>
              <button className="button primary" disabled={selectingActivity} onClick={() => chooseActivity(recommendation.id)}>{selectingActivity ? "Preparando actividad…" : "Realizar actividad"}</button>
            </div> : <p>No hay una recomendación automática para esta expresión. Puedes elegir una actividad disponible.</p>}
            {recommendation && availableActivities.some((item) => item.id !== recommendation.id) && !showAlternatives &&
              <button className="button secondary" disabled={selectingActivity} onClick={showOtherActivities}>Ver otras actividades</button>}
            {(!recommendation || showAlternatives) && availableActivities.length > 0 ? <>
              <label htmlFor="suggested-activity">Actividad que deseas realizar</label>
              <select id="suggested-activity" value={selectedActivityId} onChange={(event) => setSelectedActivityId(event.target.value)}>
                {availableActivities.filter((item) => !recommendation || item.id !== recommendation.id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
              <button className="button primary" disabled={selectingActivity || !selectedActivityId} onClick={() => chooseActivity()}>{selectingActivity ? "Preparando actividad…" : "Continuar con la actividad"}</button>
            </> : !recommendation && <p>No hay actividades configuradas. Contacta con administración.</p>}
            <div className="inline-actions">
              <button className="button secondary" disabled={selectingActivity} onClick={() => finishWithoutActivity()}>Finalizar sin actividad</button>
              <button className="button secondary" disabled={selectingActivity || starting} onClick={() => finishWithoutActivity(true)}>Analizar otra expresión</button>
            </div>
            <p className="muted">Esta sugerencia técnica no constituye una evaluación clínica.</p>
          </>}
          {phase === "completed" && !activity && outcome === "skipped" && <p>Sesión finalizada sin actividad. Tu expresión quedó registrada.</p>}
          {(phase === "exercise" || phase === "completed") && activity && <>
            <h2>{activity.name}</h2><p>{activity.description}</p>
            {phase === "exercise" && speechAvailable() && <button className="button secondary" onClick={() => currentStep ? speakStep(currentStep, stepNumber, stepCount) : speakExercise(activity)}>Repetir instrucción</button>}
            {currentStep && <p><strong>Paso {stepNumber + 1} de {stepCount}:</strong> {currentStep.instruction}</p>}
            <p>Postura: {postureNames[currentStep?.posture ?? activity.required_posture] ?? currentStep?.posture ?? activity.required_posture} · Mantén {currentStep?.duration_seconds ?? activity.duration_seconds} s</p>
            <div className="progress-label"><span>Progreso</span><strong>{Math.round(progress * 100)} %</strong></div>
            <div className="progress-track" role="progressbar" aria-label="Progreso de la actividad" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)}><div style={{ width: `${Math.round(progress * 100)}%` }} /></div>
          </>}
          {phase === "completed" && session ? <div className="inline-actions"><Link className="button secondary action-link" to={paths.session(session.id)}>Ver resultado</Link><button className="button primary" disabled={starting || modelBlocked} onClick={analyzeAgain}>{starting ? "Preparando análisis…" : "Analizar otra expresión"}</button></div>
            : <>
              <button className="button danger" disabled={cancelling} onClick={() => setConfirmCancel(true)}>Cancelar análisis</button>
              {expressionRecorded && <p className="muted">Tu expresión ya quedó registrada; cancelar solo detiene la actividad.</p>}
            </>}
        </>}
      </div>
    </div>
    <ConfirmDialog open={confirmCancel} title="Cancelar análisis" message={expressionRecorded ? "Tu expresión ya quedó registrada y se conserva. Se cancelará la actividad y se apagará la cámara." : "Se cancelará la sesión y se apagará la cámara."} confirming={cancelling} confirmLabel="Cancelar sesión" onCancel={() => setConfirmCancel(false)} onConfirm={() => { void cancel(); }} />
  </section>;
}
