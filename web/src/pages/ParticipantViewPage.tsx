import { useCallback, useEffect, useRef, useState, type CSSProperties } from "react";
import { useParams } from "react-router-dom";
import { ApiError, apiBlob, apiRequest } from "../api/http";
import type { ParticipantPractice, ParticipantRecognition, ParticipantViewState } from "../api/types";
import { cameraProblem, cameraUnavailableReason, stopStream } from "../analysis/camera";
import { speakText, speechAvailable, stopExerciseSpeech } from "../analysis/exerciseSpeech";
import { Button } from "../components/Button";
import { DrawingActivity } from "../drawing/DrawingActivity";
import { MatchingGameStage, type GameAction } from "../game/MatchingGameStage";
import { emotionPictograms } from "../stimuli/labels";

const POLL_MS = 500;
/** Lo que lee la persona si la cámara no se puede usar: qué puede seguir haciendo. */
export const CAMERA_UNAVAILABLE_MESSAGE = "No se pudo usar la cámara. Avisa a quien conduce la sesión: puedes seguir con las actividades de elegir emociones, que no la necesitan.";

/**
 * Ejercicio de práctica: la instrucción grande, la ilustración si existe y una
 * figura que crece con el nivel (sin números ni colores por expresión). Con la
 * señal apagada, solo la instrucción. Al lograrlo, una confirmación breve; si
 * vence el tiempo, el ejercicio termina sin mensaje.
 */
export function PracticeStage({ practice, imageUrl, readAloud = false }: {
  practice: ParticipantPractice; imageUrl: string | null; readAloud?: boolean;
}) {
  const level = practice.level == null ? null : Math.min(1, Math.max(0, practice.level));
  // Apoyo «leer en voz alta»: la instrucción se lee al empezar el ejercicio.
  useEffect(() => {
    if (readAloud) speakText(practice.instruction);
    return () => { if (readAloud) stopExerciseSpeech(); };
  }, [readAloud, practice.instruction]);
  return <div className="participant-practice">
    <p className="participant-instruction">{practice.instruction}</p>
    {imageUrl && <img className="participant-illustration" src={imageUrl} alt="Imagen de apoyo" />}
    {level != null && <div className="practice-signal" role="meter" aria-label="Señal del ejercicio"
      aria-valuemin={0} aria-valuemax={1} aria-valuenow={level}
      style={{ "--practice-level": level } as CSSProperties}>
      <span className="practice-signal-fill" />
    </div>}
    <p className="participant-achieved" role="status" aria-live="polite">{practice.achieved ? practice.message : ""}</p>
  </div>;
}

/**
 * Reconocimiento: la imagen, la situación si el paso la cuenta, la pregunta y
 * botones grandes con el nombre de cada emoción. Al tocar uno (o al vencer el
 * tiempo) se lee el nombre de la emoción de la imagen y su explicación sencilla;
 * no se dice si la elección coincidió. La elegida se marca con texto, no solo
 * con color. «Escuchar» lee lo que está en pantalla cuantas veces se quiera.
 */
export function RecognitionStage({ recognition, imageUrl, onAnswer, accessible = false, readAloud = false }: {
  recognition: ParticipantRecognition; imageUrl: string | null; onAnswer: (key: string) => Promise<void>;
  /** Pictogramas junto a cada emoción. */
  accessible?: boolean;
  /** Lee la consigna al empezar el paso y la respuesta al terminar. */
  readAloud?: boolean;
}) {
  const [sending, setSending] = useState<string | null>(null);
  const done = recognition.message != null;
  const chosen = recognition.chosen ?? sending;
  async function choose(key: string) {
    setSending(key);
    try { await onAnswer(key); } catch { setSending(null); }
  }
  const spoken = done
    ? [recognition.message, recognition.note, recognition.explanation]
    : [recognition.situation, recognition.question];
  // Al cambiar de paso, lo que se estuviera leyendo se corta.
  useEffect(() => () => stopExerciseSpeech(), []);
  const spokenText = spoken.filter(Boolean).join(" ");
  // Se lee al empezar el paso y otra vez al terminar; no en cada actualización.
  useEffect(() => { if (readAloud) speakText(spokenText); }, [readAloud, done]);
  return <div className="participant-practice">
    {imageUrl && <img className="participant-illustration" src={imageUrl} alt="Imagen de la sesión" />}
    {recognition.situation && <p className="participant-situation">{recognition.situation}</p>}
    <p className="participant-instruction">{recognition.question}</p>
    <div className="recognition-options">
      {recognition.options.map((option) => <Button key={option.key} className="recognition-option"
        variant={chosen === option.key ? "primary" : "secondary"} aria-pressed={chosen === option.key}
        disabled={done || sending != null} onClick={() => { void choose(option.key); }}>
        {/* En modo accesible, un pictograma acompaña al nombre; el nombre sigue siendo la etiqueta. */}
        {accessible && emotionPictograms[option.key] && <span className="recognition-pictogram" aria-hidden="true">{emotionPictograms[option.key]}</span>}
        {option.label}
        {/* Visible para no depender del color; el lector de pantalla ya anuncia aria-pressed. */}
        {chosen === option.key && <span className="recognition-chosen" aria-hidden="true">✓ Tu elección</span>}
      </Button>)}
    </div>
    {/* Mismo color con cualquier elección: el nombre de la emoción no indica si coincidió. */}
    <div className="recognition-feedback" role="status" aria-live="polite">
      <p className="participant-achieved recognition-answer">{recognition.message ?? ""}</p>
      {done && recognition.note && <p className="recognition-note">{recognition.note}</p>}
      {done && recognition.explanation && <p className="recognition-explanation">{recognition.explanation}</p>}
    </div>
    {speechAvailable() && <Button variant="secondary" className="recognition-listen" onClick={() => {
      speakText(spokenText);
    }}>Escuchar</Button>}
  </div>;
}

/**
 * Pantalla de la persona evaluada, a pantalla completa y sin la navegación de la
 * aplicación: solo el estímulo o una indicación, y un botón para parar. No
 * recibe expresiones, probabilidades, calidad ni notas. La cámara se usa solo
 * mientras la sesión lo pide; los cuadros se analizan en el servidor y se descartan.
 */
export function ParticipantViewPage() {
  const { token = "" } = useParams();
  const base = `/participant-view/${encodeURIComponent(token)}`;
  const [view, setView] = useState<ParticipantViewState | null>(null);
  const [ended, setEnded] = useState(false);
  const [imageUrl, setImageUrl] = useState<string | null>(null);
  const [cameraError, setCameraError] = useState("");
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const exposure = view?.stimulus?.exposure ?? null;
  const practice = view?.practice ?? null;
  const recognition = view?.recognition ?? null;
  const drawing = view?.drawing ?? null;
  const game = view?.game ?? null;
  // Con un dibujo en pantalla, cerrar o recargar la pestaña pide confirmación (el dibujo se borra).
  const [hasDrawing, setHasDrawing] = useState(false);
  const drawingOpen = drawing != null && !drawing.finished && hasDrawing;
  useEffect(() => {
    if (!drawingOpen) return undefined;
    const warn = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ""; };
    window.addEventListener("beforeunload", warn);
    return () => { window.removeEventListener("beforeunload", warn); };
  }, [drawingOpen]);
  // En una práctica se envía el cuadro siguiente solo cuando el servidor recibió el anterior.
  const interval = practice?.frame_interval_ms ?? view?.frame_interval_ms ?? POLL_MS;
  const oneAtATime = practice != null;
  const inFlightRef = useRef(false);

  useEffect(() => {
    let cancelled = false;
    async function poll() {
      try {
        const next = await apiRequest<ParticipantViewState>(base);
        if (!cancelled) setView(next);
      } catch (reason) {
        if (!cancelled && reason instanceof ApiError && reason.status === 404) setEnded(true);
      }
    }
    void poll();
    const timer = window.setInterval(() => { if (!ended) void poll(); }, POLL_MS);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [base, ended]);

  // La imagen del estímulo que se muestra ahora; se libera al cambiar.
  useEffect(() => {
    if (!exposure) { setImageUrl(null); return; }
    let url: string | null = null;
    let cancelled = false;
    apiBlob(`${base}/stimulus`).then((blob) => {
      if (cancelled) return;
      url = URL.createObjectURL(blob);
      setImageUrl(url);
    }).catch(() => setImageUrl(null));
    return () => { cancelled = true; if (url) URL.revokeObjectURL(url); };
  }, [base, exposure]);

  const capturing = Boolean(view?.capture_frames) && !ended;
  const withoutCamera = view?.uses_camera === false;
  // Si la sesión siguió sin cámara, el aviso del problema ya no hace falta.
  useEffect(() => { if (withoutCamera) setCameraError(""); }, [withoutCamera]);

  function releaseCamera() {
    stopStream(streamRef.current);
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }

  useEffect(() => {
    if (!capturing) { releaseCamera(); return; }
    let timer: number | undefined;
    let stopped = false;
    async function start() {
      try {
        const unavailable = cameraUnavailableReason();
        if (unavailable) throw Object.assign(new Error(unavailable), { name: "SecurityError" });
        if (!streamRef.current) {
          streamRef.current = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
          if (videoRef.current) { videoRef.current.srcObject = streamRef.current; await videoRef.current.play().catch(() => undefined); }
        }
        setCameraError("");
        timer = window.setInterval(sendFrame, interval);
      } catch (reason) {
        if (stopped) return;
        releaseCamera();
        setCameraError(CAMERA_UNAVAILABLE_MESSAGE);
        // Solo el motivo: quien conduce decide si sigue sin cámara.
        void apiRequest(`${base}/camera-problem`, { method: "POST", body: JSON.stringify({ reason: cameraProblem(reason) }) }).catch(() => undefined);
      }
    }
    function sendFrame() {
      const video = videoRef.current, canvas = canvasRef.current;
      if (!video || !canvas || video.readyState < 2) return;
      if (oneAtATime && inFlightRef.current) return;
      canvas.width = 640; canvas.height = 480;
      canvas.getContext("2d")?.drawImage(video, 0, 0, 640, 480);
      inFlightRef.current = true;
      canvas.toBlob((blob) => {
        // Solo se confirma la recepción: el servidor nunca devuelve resultados aquí.
        if (!blob) { inFlightRef.current = false; return; }
        void apiRequest(`${base}/frames`, { method: "POST", body: blob, headers: { "Content-Type": "image/jpeg" } })
          .catch(() => undefined).finally(() => { inFlightRef.current = false; });
      }, "image/jpeg", 0.8);
    }
    void start();
    return () => { stopped = true; if (timer) window.clearInterval(timer); };
  }, [capturing, base, interval, oneAtATime]);

  // Al salir, cerrar o recargar la pestaña la cámara se apaga.
  useEffect(() => {
    window.addEventListener("pagehide", releaseCamera);
    return () => { window.removeEventListener("pagehide", releaseCamera); releaseCamera(); };
  }, []);

  async function answer(key: string) {
    await apiRequest(`${base}/answer`, { method: "POST", body: JSON.stringify({ expression: key }) });
    setView(await apiRequest<ParticipantViewState>(base));
  }

  const loadGameOption = useCallback((key: string) => apiBlob(`${base}/game/option/${encodeURIComponent(key)}`), [base]);

  async function playGame(action: GameAction, expression?: string) {
    await apiRequest(`${base}/game`, { method: "POST", body: JSON.stringify({ action, ...(expression ? { expression } : {}) }) });
    setView(await apiRequest<ParticipantViewState>(base));
  }

  async function stop() {
    try { await apiRequest(`${base}/stop`, { method: "POST" }); } catch { /* ya terminó */ }
    setEnded(true);
  }

  const finished = ended || view?.phase === "finished" || view?.phase === "stopped";
  // Apoyos del protocolo; sin «supports», el modo accesible de antes (pictogramas y botones grandes).
  const supports = view?.supports ?? (view?.accessible ? { pictograms: true, large_controls: true, read_aloud: false } : null);
  return <main className={`participant-view${supports?.large_controls ? " participant-view--accessible" : ""}`}>
    {/* Sin cámara (solo reconocimientos) no se monta el video. */}
    {view?.uses_camera !== false && <video ref={videoRef} className="participant-camera" playsInline muted aria-hidden="true" />}
    <canvas ref={canvasRef} hidden />
    <div className="participant-view-stage">
      {finished
        ? <p className="participant-message">La sesión terminó. Gracias.</p>
        : practice
          ? <PracticeStage practice={practice} imageUrl={imageUrl} readAloud={Boolean(supports?.read_aloud)} />
          : recognition
          // La clave reinicia la elección al pasar a otra imagen.
          ? <RecognitionStage key={exposure ?? ""} recognition={recognition} imageUrl={imageUrl} onAnswer={answer}
            accessible={Boolean(supports?.pictograms)} readAloud={Boolean(supports?.read_aloud)} />
          : drawing
          // Cada intento empieza un lienzo nuevo; al cambiar de paso, el dibujo se borra.
          ? <DrawingActivity key={drawing.round} onDrawingChange={setHasDrawing} session={{
            instruction: drawing.instruction, question: drawing.question, options: drawing.options,
            finished: drawing.finished, chosen: drawing.chosen, message: drawing.message,
            onChoose: answer, readAloud: Boolean(supports?.read_aloud) }} />
          : game
          ? <MatchingGameStage game={game} imageUrl={imageUrl} onAction={playGame} loadOption={loadGameOption}
            pictograms={Boolean(supports?.pictograms)} readAloud={Boolean(supports?.read_aloud)} />
          : imageUrl
          ? <img className="participant-stimulus" src={imageUrl} alt="Imagen de la sesión" />
          : <p className="participant-message">{view?.message ?? "Espera un momento."}</p>}
      {cameraError && <p className="participant-message">{cameraError}</p>}
    </div>
    {!finished && view?.abstract_notice && <p className="participant-notice">{view.abstract_notice}</p>}
    {!finished && <div className="participant-actions">
      <Button variant="danger" onClick={() => { void stop(); }}>Quiero parar</Button>
      <Button variant="ghost" onClick={() => { void document.documentElement.requestFullscreen?.().catch(() => undefined); }}>Pantalla completa</Button>
    </div>}
  </main>;
}
