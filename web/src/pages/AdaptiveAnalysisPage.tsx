import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { ApiError, SESSION_EXPIRED_ANALYSIS_MESSAGE, SESSION_EXPIRED_CLOSE_CODE, apiRequest, apiWebSocketUrl, notifySessionExpired } from "../api/http";
import type { Activity, ActivityStep, EmotionalSession, Student } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { useActiveSession } from "../analysis/ActiveSessionContext";
import { AnalysisNavigationGuard } from "../analysis/AnalysisNavigationGuard";
import { drawPoseOverlay } from "../analysis/drawPoseOverlay";
import type { PoseLandmarks } from "../analysis/drawPoseOverlay";
import { speakExercise, speakStep, speechAvailable, stopExerciseSpeech } from "../analysis/exerciseSpeech";
import { remainingSeconds, stepPosition } from "../analysis/activityProgress";
import { Callout } from "../components/Callout";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { paths } from "../routes/paths";
import { useExpressionCatalog } from "../expressions/ExpressionCatalog";
import type { ExpressionInfo } from "../expressions/ExpressionCatalog";
import { ExpressionResult } from "../expressions/ExpressionResult";
import { LiveExpressionPanel, percent, type LiveReading } from "../analysis/LiveExpressionPanel";
import { Button, ButtonLink } from "../components/Button";
import { CameraFrame } from "../components/CameraFrame";
import { Checkbox } from "../components/Checkbox";
import { NavIcon } from "../components/NavIcon";
import { StatusChip, type StatusTone } from "../components/StatusChip";
import { useConsentStatus } from "../consent/useConsentStatus";
import { postureName } from "../components/PostureIcon";
import { cameraErrorMessage, cameraProblem, cameraProblemMessages, cameraUnavailableReason, stopStream, type CameraProblem } from "../analysis/camera";

type Phase = "ready" | "live" | "result" | "exercise" | "completed";
type Admission = { model_id: string; state: "SUPPORTED" | "WARNING" | "BLOCKED"; reasons: string[] };
type Message = Partial<LiveReading> & {
  type: "ready" | "live" | "confirm_rejected" | "recognized" | "status" | "recommendation" | "activity_started" | "completed" | "cancelled" | "error";
  state?: string; message?: string; progress?: number; code?: number;
  emotion?: string | null; emotion_confidence?: number | null;
  activity?: Activity | null; activities?: Activity[];
  step?: ActivityStep; step_index?: number; step_count?: number;
  repetition_index?: number; repetition_count?: number; step_remaining_seconds?: number;
  landmarks?: PoseLandmarks | null;
  exercise_result?: string | null; recognition_kept?: boolean;
  expression?: ExpressionInfo | null;
  notice?: string | null; stage?: string;
};


type RequirementState = "ready" | "pending" | "blocked" | "checking";
type Requirement = { key: string; label: string; state: RequirementState; detail: string; action?: ReactNode };
const requirementText: Record<RequirementState, string> = { ready: "Listo", pending: "Pendiente", blocked: "Bloqueado", checking: "Comprobando" };
const requirementTone: Record<RequirementState, StatusTone> = { ready: "success", pending: "progress", blocked: "error", checking: "neutral" };
const cameraProblemShort: Record<CameraProblem, string> = {
  insecure: "Requiere una conexión segura (https).",
  denied: "El navegador bloqueó el permiso.",
  busy: "Otra aplicación la está usando.",
  not_found: "No se encontró ninguna cámara.",
  unknown: "No se pudo abrir.",
};

/** Guía previa: lo que más influye en la lectura del rostro y en la verificación de posturas. */
export function AnalysisGuide({ activity = false }: { activity?: boolean }) {
  return <section className="analysis-guide" aria-labelledby="analysis-guide-title">
    <h2 id="analysis-guide-title">Antes de empezar</h2>
    <ul>
      <li><strong>Luz de frente.</strong> Ponte mirando hacia la ventana o la lámpara, no de espaldas a ella.</li>
      <li><strong>Rostro centrado.</strong> Mira a la cámara con la cara completa dentro del encuadre.</li>
      <li><strong>{activity ? "Cuerpo completo." : "Para la actividad, aléjate."}</strong> {activity
        ? "Aléjate hasta que la cámara vea tu cuerpo completo, de la cabeza a los pies, con espacio para mover los brazos."
        : "Después del registro, colócate a unos dos metros para que la cámara vea tu cuerpo completo."}</li>
    </ul>
  </section>;
}

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
  const [cameraIssue, setCameraIssue] = useState<CameraProblem | null>(null);
  const consentStatus = useConsentStatus(user?.role === "student");
  const [service, setService] = useState<"checking" | "ready" | "blocked">("checking");
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
  const [repetitionCount, setRepetitionCount] = useState(1);
  const [stepRemaining, setStepRemaining] = useState<number | null>(null);
  // Índice global del último paso anunciado: la voz habla una vez por paso,
  // no en cada frame.
  const announcedStepRef = useRef(-1);
  const position = stepPosition(stepNumber, stepCount, repetitionCount);
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

  // Al cerrar o recargar la pestaña la cámara se apaga aunque React no llegue a desmontar.
  useEffect(() => {
    const release = () => { releaseMedia(); setPreviewing(false); };
    window.addEventListener("pagehide", release);
    return () => window.removeEventListener("pagehide", release);
  }, []);

  async function checkService() {
    setService("checking");
    try { await apiRequest("/health", { token }); setService("ready"); }
    catch { setService("blocked"); }
  }
  // El servicio se comprueba al abrir la página; /health no revela configuración.
  useEffect(() => { void checkService(); }, [token]);

  const consentReady = consentStatus.state === "active" || consentStatus.state === "not_required";
  const requirements: Requirement[] = [
    { key: "camera", label: "Cámara", state: previewing ? "ready" : cameraIssue ? "blocked" : "pending",
      detail: previewing ? "La vista previa funciona." : cameraIssue ? cameraProblemShort[cameraIssue] : "Pruébala para comprobar que el navegador puede usarla.",
      action: <Button variant="secondary" size="sm" onClick={() => { void previewCamera(); }}>Probar cámara</Button> },
    { key: "consent", label: "Consentimiento vigente",
      state: consentStatus.state === "loading" ? "checking" : consentReady ? "ready"
        : consentStatus.state === "missing" || consentStatus.state === "outdated" ? "pending" : "blocked",
      detail: consentReady ? "Aceptaste la política vigente."
        : consentStatus.state === "outdated" ? "La política cambió; acepta la nueva versión."
          : consentStatus.state === "missing" ? "Acepta la política de análisis facial."
            : consentStatus.state === "loading" ? "Comprobando…" : "No se puede solicitar el consentimiento ahora. Consulta con administración.",
      action: consentStatus.state === "missing" || consentStatus.state === "outdated"
        ? <ButtonLink variant="secondary" size="sm" to={paths.consent}>Revisar consentimiento</ButtonLink>
        : consentStatus.state === "error" ? <Button variant="secondary" size="sm" onClick={() => { void consentStatus.reload(); }}>Comprobar de nuevo</Button> : undefined },
    { key: "service", label: "Servicio de análisis", state: service === "ready" && modelBlocked ? "blocked" : service,
      detail: service === "ready" ? (modelBlocked ? "El modelo elegido no está disponible." : "Responde correctamente.")
        : service === "checking" ? "Comprobando…" : "No responde en este momento.",
      action: service === "blocked" ? <Button variant="secondary" size="sm" onClick={() => { void checkService(); }}>Comprobar de nuevo</Button> : undefined },
  ];
  const pendingRequirements = requirements.filter((item) => item.state !== "ready");

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
    stopStream(streamRef.current);
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    lastLandmarksRef.current = null;
    drawPoseOverlay(overlayRef.current, null);
  }

  async function previewCamera(): Promise<boolean> {
    if (streamRef.current) return true;
    const unavailable = cameraUnavailableReason();
    if (unavailable) {
      setCameraIssue(unavailable); setError(cameraProblemMessages[unavailable]);
      return false;
    }
    setError("");
    const lifecycle = lifecycleRef.current;
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" }, audio: false });
      if (lifecycle !== lifecycleRef.current) {
        stopStream(stream);
        return false;
      }
      streamRef.current = stream;
      if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play(); }
      setPreviewing(true); setCameraIssue(null);
      return true;
    } catch (reason) {
      releaseMedia(); setPreviewing(false);
      setCameraIssue(cameraProblem(reason)); setError(cameraErrorMessage(reason));
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

  function announceStep(step: ActivityStep, index: number, count: number, repetitions: number) {
    const at = stepPosition(index, count, repetitions);
    speakStep(step, at.step - 1, at.steps, { index: at.repetition - 1, count: at.repetitions });
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
          releaseMedia(); setPreviewing(false); setSession(null); sessionRef.current = null; setPhase("ready"); setLive(null);
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
          const repetitions = result.activity?.repetitions ?? 1;
          const total = (result.activity?.steps?.length ?? 1) * repetitions;
          setCurrentStep(firstStep ?? null);
          setStepNumber(0);
          setStepCount(total);
          setRepetitionCount(repetitions);
          setStepRemaining(firstStep?.duration_seconds ?? result.activity?.duration_seconds ?? null);
          announcedStepRef.current = 0;
          if (voiceEnabled && result.activity) {
            if (firstStep) announceStep(firstStep, 0, total, repetitions);
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
            const repetitions = result.repetition_count ?? 1;
            setCurrentStep(result.step); setStepNumber(result.step_index);
            setStepCount(result.step_count ?? 1);
            setRepetitionCount(repetitions);
            setStepRemaining(result.step_remaining_seconds ?? result.step.duration_seconds);
            if (voiceEnabled && result.step_index !== announcedStepRef.current) {
              announcedStepRef.current = result.step_index;
              announceStep(result.step, result.step_index, result.step_count ?? 1, repetitions);
            }
          }
        }
      };
      socket.onerror = () => failAnalysis("No se pudo conectar con el analizador. Comprueba tu conexión y vuelve a intentarlo.");
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
    setRepetitionCount(1);
    setStepRemaining(null);
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
    <PageHeader title="Analizador" description="Primero analizamos tu expresión facial. Después podrás revisar una actividad sugerida y decidir si deseas realizarla." />
    {error && <Callout variant="error">{error}</Callout>}
    {notice && <Callout variant="info">{notice}</Callout>}
    <div className="analysis-preflight card">
      <div>
        <CameraFrame className="video-stage adaptive-video-stage" stable={phase === "live" && Boolean(live?.can_confirm)}>
          <video ref={videoRef} aria-label="Vista previa de tu cámara" playsInline muted />
          <canvas ref={overlayRef} aria-hidden="true" width="640" height="480" />
          <canvas ref={captureRef} hidden />
          {!previewing && <div className="video-placeholder">
            <NavIcon name="camera-off" />
            <p>La cámara está apagada. Puedes probarla antes de iniciar.</p>
            {phase === "ready" && <Button variant="secondary" onClick={() => { void previewCamera(); }}>Probar cámara</Button>}
          </div>}
        </CameraFrame>
        {phase === "ready" && <div className="camera-actions">
          {previewing && <Button variant="secondary" onClick={() => { releaseMedia(); setPreviewing(false); }}>Apagar cámara</Button>}
          <p className="muted">Esta prueba es local: no crea una sesión ni envía imágenes al servidor.</p>
        </div>}
      </div>
      <div className="adaptive-analysis-panel">
        {phase === "ready" && <>
          <AnalysisGuide />
          <h2>Requisitos</h2>
          <ul className="requirement-list" aria-label="Requisitos para empezar">
            {requirements.map((item) => <li key={item.key} className="requirement">
              <div className="requirement-text">
                <strong>{item.label}</strong>
                <span>{item.detail}</span>
              </div>
              <StatusChip tone={requirementTone[item.state]}>{requirementText[item.state]}</StatusChip>
              {item.action && item.state !== "ready" && <div className="requirement-action">{item.action}</div>}
            </li>)}
          </ul>
          {canChooseModel && <>
            <label htmlFor="adaptive-model">Modelo facial</label>
            <select id="adaptive-model" value={modelId} onChange={(event) => setModelId(event.target.value)}>
              <option value="ferplus_onnx">FER+ · ONNX</option>
              <option value="hardlyhumans_vit">HardlyHumans · ViT/PyTorch</option>
            </select>
            <PageState {...modelsQuery} onRetry={modelsQuery.reload} />
            {admission && <Callout variant={admission.state === "BLOCKED" ? "error" : admission.state === "WARNING" ? "warning" : "info"}>{admission.state === "BLOCKED" ? "Modelo no disponible" : admission.state === "WARNING" ? "Modelo con advertencias" : "Modelo disponible"}: {admission.reasons.join("; ") || "listo para usar"}</Callout>}
          </>}
          <Checkbox checked={includeLandmarks} onChange={(event) => { setIncludeLandmarks(event.target.checked); drawPoseOverlay(overlayRef.current, lastLandmarksRef.current, event.target.checked); }}>Mostrar puntos y líneas durante la actividad</Checkbox>
          <Checkbox checked={voiceEnabled} disabled={!speechAvailable()} onChange={(event) => setVoiceEnabled(event.target.checked)}>Leer instrucciones en voz alta</Checkbox>
          <Button variant="primary" disabled={starting || modelBlocked || pendingRequirements.length > 0} aria-describedby="start-help" onClick={() => { void start(); }}>{starting ? "Preparando análisis…" : "Reconocer mi expresión"}</Button>
          <p id="start-help" className="muted" aria-live="polite">{pendingRequirements.length > 0
            ? `Para empezar falta: ${pendingRequirements.map((item) => item.label.toLowerCase()).join(", ")}.`
            : "Todo listo. La cámara se usará solo mientras dure el análisis."}</p>
        </>}
        {phase !== "ready" && <>
          <p className="step-caption">{phase === "live" ? "Paso 1 de 3 · Expresión en vivo" : phase === "result" ? "Paso 2 de 3 · Resultado y actividad sugerida" : "Paso 3 de 3 · Actividad corporal"}</p>
          {phase !== "live" && <span role="status" className="analysis-state">{message}</span>}
          {phase === "live" && <LiveExpressionPanel live={live} />}
          {phase === "live" && <>
            <Button variant="primary" type="submit" disabled={!live?.can_confirm || confirming} aria-describedby="confirm-help" onClick={confirmExpression}>{confirming ? "Registrando…" : "Registrar esta expresión"}</Button>
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
                    <small>{postureName(step.posture)} · {step.duration_seconds} s</small>
                  </li>) : <li>
                    <span>{recommendation.description}</span>
                    <small>{postureName(recommendation.required_posture)} · {recommendation.duration_seconds} s</small>
                  </li>}
                </ol>
              </div>
              <Button variant="primary" type="submit" disabled={selectingActivity} onClick={() => chooseActivity(recommendation.id)}>{selectingActivity ? "Preparando actividad…" : "Realizar actividad"}</Button>
            </div> : <p>No hay una recomendación automática para esta expresión. Puedes elegir una actividad disponible.</p>}
            {recommendation && availableActivities.some((item) => item.id !== recommendation.id) && !showAlternatives &&
              <Button variant="secondary" type="submit" disabled={selectingActivity} onClick={showOtherActivities}>Ver otras actividades</Button>}
            {(!recommendation || showAlternatives) && availableActivities.length > 0 ? <>
              <label htmlFor="suggested-activity">Actividad que deseas realizar</label>
              <select id="suggested-activity" value={selectedActivityId} onChange={(event) => setSelectedActivityId(event.target.value)}>
                {availableActivities.filter((item) => !recommendation || item.id !== recommendation.id).map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}
              </select>
              <Button variant="primary" type="submit" disabled={selectingActivity || !selectedActivityId} onClick={() => chooseActivity()}>{selectingActivity ? "Preparando actividad…" : "Continuar con la actividad"}</Button>
            </> : !recommendation && <p>No hay actividades configuradas. Contacta con administración.</p>}
            {(recommendation || availableActivities.length > 0) && <Callout variant="info" role="note">
              <strong>Antes de la actividad:</strong> aléjate hasta que la cámara vea tu cuerpo completo, de la cabeza a los pies, y deja espacio para mover los brazos.
            </Callout>}
            <div className="inline-actions">
              <Button variant="secondary" type="submit" disabled={selectingActivity} onClick={() => finishWithoutActivity()}>Finalizar sin actividad</Button>
              <Button variant="secondary" type="submit" disabled={selectingActivity || starting} onClick={() => finishWithoutActivity(true)}>Analizar otra expresión</Button>
            </div>
            <p className="muted">Esta sugerencia técnica no constituye una evaluación clínica.</p>
          </>}
          {phase === "completed" && !activity && outcome === "skipped" && <p>Sesión finalizada sin actividad. Tu expresión quedó registrada.</p>}
          {(phase === "exercise" || phase === "completed") && activity && <>
            <h2>{activity.name}</h2><p>{activity.description}</p>
            {phase === "exercise" && speechAvailable() && <Button variant="secondary" type="submit" onClick={() => currentStep ? announceStep(currentStep, stepNumber, stepCount, repetitionCount) : speakExercise(activity)}>Repetir instrucción</Button>}
            {currentStep && <p><strong>Paso {position.step} de {position.steps}:</strong> {currentStep.instruction}</p>}
            {phase === "exercise" && <p>Repetición {position.repetition} de {position.repetitions}</p>}
            <p>Postura esperada: {postureName(currentStep?.posture ?? activity.required_posture)} · Mantén {currentStep?.duration_seconds ?? activity.duration_seconds} s</p>
            {phase === "exercise" && stepRemaining != null && <p>Tiempo restante del paso: {remainingSeconds(stepRemaining)} s</p>}
            <div className="progress-label"><span>Progreso</span><strong>{Math.round(progress * 100)} %</strong></div>
            <div className="progress-track" role="progressbar" aria-label="Progreso de la actividad" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)}><div style={{ width: `${Math.round(progress * 100)}%` }} /></div>
            {phase === "completed" && <p>{outcome === "completed"
              ? "Terminaste todos los pasos. La cámara ya se apagó."
              : "La actividad terminó sin completar todos los pasos. La cámara ya se apagó."}</p>}
          </>}
          {phase === "completed" && session ? <div className="inline-actions"><ButtonLink variant="secondary" to={paths.session(session.id)}>Ver resultado</ButtonLink><Button variant="primary" type="submit" disabled={starting || modelBlocked} onClick={analyzeAgain}>{starting ? "Preparando análisis…" : "Analizar otra expresión"}</Button></div>
            : <>
              <Button variant="danger" type="submit" disabled={cancelling} onClick={() => setConfirmCancel(true)}>Cancelar análisis</Button>
              {expressionRecorded && <p className="muted">Tu expresión ya quedó registrada; cancelar solo detiene la actividad.</p>}
            </>}
        </>}
      </div>
    </div>
    <ConfirmDialog open={confirmCancel} title="Cancelar análisis" message={expressionRecorded ? "Tu expresión ya quedó registrada y se conserva. Se cancelará la actividad y se apagará la cámara." : "Se cancelará la sesión y se apagará la cámara."} confirming={cancelling} confirmLabel="Cancelar sesión" onCancel={() => setConfirmCancel(false)} onConfirm={() => { void cancel(); }} />
  </section>;
}
