import { useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, apiBlob, apiRequest } from "../api/http";
import type { ParticipantViewState } from "../api/types";
import { Button } from "../components/Button";

const POLL_MS = 500;

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
  useEffect(() => {
    if (!capturing) {
      streamRef.current?.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
      return;
    }
    let timer: number | undefined;
    let stopped = false;
    async function start() {
      try {
        if (!streamRef.current) {
          streamRef.current = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
          if (videoRef.current) { videoRef.current.srcObject = streamRef.current; await videoRef.current.play().catch(() => undefined); }
        }
        setCameraError("");
        timer = window.setInterval(sendFrame, view?.frame_interval_ms ?? POLL_MS);
      } catch { if (!stopped) setCameraError("No se pudo usar la cámara. Avisa a quien conduce la sesión."); }
    }
    function sendFrame() {
      const video = videoRef.current, canvas = canvasRef.current;
      if (!video || !canvas || video.readyState < 2) return;
      canvas.width = 640; canvas.height = 480;
      canvas.getContext("2d")?.drawImage(video, 0, 0, 640, 480);
      canvas.toBlob((blob) => {
        // Solo se confirma la recepción: el servidor nunca devuelve resultados aquí.
        if (blob) void apiRequest(`${base}/frames`, { method: "POST", body: blob, headers: { "Content-Type": "image/jpeg" } }).catch(() => undefined);
      }, "image/jpeg", 0.8);
    }
    void start();
    return () => { stopped = true; if (timer) window.clearInterval(timer); };
  }, [capturing, base, view?.frame_interval_ms]);

  useEffect(() => () => { streamRef.current?.getTracks().forEach((track) => track.stop()); }, []);

  async function stop() {
    try { await apiRequest(`${base}/stop`, { method: "POST" }); } catch { /* ya terminó */ }
    setEnded(true);
  }

  const finished = ended || view?.phase === "finished" || view?.phase === "stopped";
  return <main className="participant-view">
    <video ref={videoRef} className="participant-camera" playsInline muted aria-hidden="true" />
    <canvas ref={canvasRef} hidden />
    <div className="participant-view-stage">
      {finished
        ? <p className="participant-message">La sesión terminó. Gracias.</p>
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
