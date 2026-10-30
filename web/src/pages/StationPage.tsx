import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { ApiError, apiRequest } from "../api/http";
import type { ExamStationJoin, ParticipantViewState } from "../api/types";
import { cameraErrorMessage, cameraUnavailableReason, cameraProblemMessages, stopStream } from "../analysis/camera";
import { Button } from "../components/Button";
import { ConfirmDialog } from "../components/ConfirmDialog";

const POLL_MS = 500;
const STORAGE_KEY = "emotv.exam-station";
/** Lado mayor del cuadro enviado: basta para detectar el rostro y pesa poco en la red del laboratorio. */
const FRAME_SIDE = 640;
/** Fases en las que la cámara queda abierta (entre la calibración y el examen no se cierra). */
const CAMERA_PHASES = new Set(["calibration", "ready", "exam"]);

function savedStation(): ExamStationJoin | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) as ExamStationJoin : null;
  } catch { return null; }
}

function saveStation(station: ExamStationJoin | null) {
  try {
    if (station) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(station));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch { /* sin almacenamiento: al recargar se vuelve a unir */ }
}

/**
 * Estación del examen simulado (celular en su soporte o PC con cámara USB),
 * sin cuenta y sin la navegación de la aplicación. Se une con el código del
 * examen y muestra el código de su sesión para el consentimiento firmado. No
 * muestra expresiones ni resultados: los cuadros se analizan en el servidor y se
 * descartan. Pantalla oscura y sin bloqueo mientras dura el examen.
 */
export function StationPage() {
  const [station, setStation] = useState<ExamStationJoin | null>(savedStation);
  function leave() { saveStation(null); setStation(null); }
  if (!station) return <StationJoin onJoined={(joined) => { saveStation(joined); setStation(joined); }} />;
  return <StationScreen station={station} onLeave={leave} />;
}

function StationJoin({ onJoined }: { onJoined(station: ExamStationJoin): void }) {
  const [code, setCode] = useState("");
  const [joining, setJoining] = useState(false);
  const [error, setError] = useState("");

  async function submit(event: FormEvent) {
    event.preventDefault();
    setJoining(true); setError("");
    try {
      onJoined(await apiRequest<ExamStationJoin>("/exam-stations", {
        method: "POST", body: JSON.stringify({ join_code: code.trim().toUpperCase() }),
      }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo unir la estación.");
      setJoining(false);
    }
  }

  return <main className="station-view">
    <form className="station-join" onSubmit={(event) => { void submit(event); }}>
      <h1>Estación del examen</h1>
      <label>Código del examen
        <input className="station-code-input" value={code} required maxLength={16} autoComplete="off" autoCapitalize="characters"
          spellCheck={false} inputMode="text" onChange={(event) => setCode(event.target.value.toUpperCase())} />
      </label>
      {error && <p className="station-error" role="alert">{error}</p>}
      <Button type="submit" loading={joining} disabled={!code.trim()}>Unirse</Button>
    </form>
  </main>;
}

function StationScreen({ station, onLeave }: { station: ExamStationJoin; onLeave(): void }) {
  const base = `/participant-view/${encodeURIComponent(station.view_token)}`;
  const [view, setView] = useState<ParticipantViewState | null>(null);
  const [gone, setGone] = useState(false);
  const [cameraError, setCameraError] = useState("");
  const [askingStop, setAskingStop] = useState(false);
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const finished = gone || view?.phase === "finished" || view?.phase === "stopped";

  useEffect(() => {
    if (finished) return;
    let cancelled = false;
    async function poll() {
      try {
        const next = await apiRequest<ParticipantViewState>(base);
        if (!cancelled) setView(next);
      } catch (reason) {
        if (!cancelled && reason instanceof ApiError && reason.status === 404) setGone(true);
      }
    }
    void poll();
    const timer = window.setInterval(() => { void poll(); }, POLL_MS);
    return () => { cancelled = true; window.clearInterval(timer); };
  }, [base, finished]);

  // La pantalla no se apaga mientras dura el examen (si el navegador lo permite).
  useEffect(() => {
    if (finished || !("wakeLock" in navigator)) return;
    let lock: WakeLockSentinel | null = null;
    let released = false;
    async function request() {
      try {
        if (document.visibilityState === "visible") lock = await navigator.wakeLock.request("screen");
        if (released) void lock?.release();
      } catch { /* batería baja o sin permiso: la pantalla puede apagarse */ }
    }
    function onVisible() { if (document.visibilityState === "visible") void request(); }
    void request();
    document.addEventListener("visibilitychange", onVisible);
    return () => {
      released = true;
      document.removeEventListener("visibilitychange", onVisible);
      void lock?.release().catch(() => undefined);
    };
  }, [finished]);

  // La cámara frontal queda abierta desde la calibración hasta el cierre.
  const cameraOpen = !finished && CAMERA_PHASES.has(view?.phase ?? "");
  useEffect(() => {
    if (!cameraOpen) { stopStream(streamRef.current); streamRef.current = null; return; }
    const unavailable = cameraUnavailableReason();
    if (unavailable) { setCameraError(cameraProblemMessages[unavailable]); return; }
    let cancelled = false;
    navigator.mediaDevices.getUserMedia({ video: { facingMode: "user", width: { ideal: 640 }, height: { ideal: 480 } }, audio: false })
      .then(async (stream) => {
        if (cancelled) { stopStream(stream); return; }
        streamRef.current = stream;
        setCameraError("");
        if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play().catch(() => undefined); }
      })
      .catch((reason: unknown) => { if (!cancelled) setCameraError(cameraErrorMessage(reason)); });
    return () => { cancelled = true; stopStream(streamRef.current); streamRef.current = null; };
  }, [cameraOpen]);

  // Cuadros solo cuando el servidor los pide (calibración y examen).
  const sending = !finished && Boolean(view?.capture_frames);
  const interval = view?.frame_interval_ms ?? POLL_MS;
  useEffect(() => {
    if (!sending) return;
    function sendFrame() {
      const video = videoRef.current, canvas = canvasRef.current;
      if (!video || !canvas || video.readyState < 2 || !video.videoWidth) return;
      const scale = Math.min(1, FRAME_SIDE / Math.max(video.videoWidth, video.videoHeight));
      canvas.width = Math.round(video.videoWidth * scale);
      canvas.height = Math.round(video.videoHeight * scale);
      canvas.getContext("2d")?.drawImage(video, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((blob) => {
        // Solo se confirma la recepción: el servidor nunca devuelve resultados aquí.
        if (blob) void apiRequest(`${base}/frames`, { method: "POST", body: blob, headers: { "Content-Type": "image/jpeg" } }).catch(() => undefined);
      }, "image/jpeg", 0.8);
    }
    const timer = window.setInterval(sendFrame, interval);
    return () => window.clearInterval(timer);
  }, [sending, interval, base]);

  async function stop() {
    try { await apiRequest(`${base}/stop`, { method: "POST" }); } catch { /* ya terminó */ }
    setAskingStop(false);
    try { setView(await apiRequest<ParticipantViewState>(base)); } catch { setGone(true); }
  }

  const waiting = !finished && (!view || view.phase === "waiting");
  return <main className="station-view">
    <video ref={videoRef} className="participant-camera" playsInline muted aria-hidden="true" />
    <canvas ref={canvasRef} hidden />
    <div className="station-stage" aria-live="polite">
      {(waiting || finished) && <p className="station-session-code">
        Código de tu sesión<strong>{station.session_code}</strong>
        {waiting && <span>Anótalo en tu consentimiento firmado.</span>}
      </p>}
      <p className="station-message">
        {finished ? view?.message ?? "El examen terminó. Gracias por participar." : view?.message ?? "Conectando…"}
      </p>
      {cameraError && <p className="station-error" role="alert">{cameraError}</p>}
    </div>
    <div className="participant-actions">
      {finished
        ? <Button variant="secondary" onClick={onLeave}>Salir</Button>
        : <Button variant="secondary" onClick={() => setAskingStop(true)}>Quiero parar</Button>}
    </div>
    <ConfirmDialog open={askingStop} title="Parar" confirmLabel="Sí, parar"
      message="Esta estación deja de registrar y no puede volver a unirse a este examen con la misma sesión."
      onConfirm={() => { void stop(); }} onCancel={() => setAskingStop(false)} />
  </main>;
}
