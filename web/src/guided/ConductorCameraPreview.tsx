import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { cameraErrorMessage, cameraUnavailableReason, stopStream } from "../analysis/camera";
import { Button } from "../components/Button";

/**
 * Vista previa de la cámara para quien conduce, no para la persona: sirve para
 * acomodarla frente a la cámara cuando su pantalla está abierta en esta misma
 * computadora. La imagen solo se dibuja aquí: no se envía, no se guarda y no se
 * analiza (el análisis usa los cuadros que manda la pantalla de la persona).
 * Se enciende con un botón y se apaga al ocultarla o al salir de la página.
 */
export function ConductorCameraPreview({ reading }: {
  /** Lo que estima la cámara, junto al video (solo para quien conduce). */
  reading?: ReactNode;
} = {}) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const streamRef = useRef<MediaStream | null>(null);
  const [on, setOn] = useState(false);
  const [error, setError] = useState("");

  function release() {
    stopStream(streamRef.current);
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
  }

  useEffect(() => {
    if (!on) { release(); return; }
    let cancelled = false;
    (async () => {
      try {
        if (cameraUnavailableReason()) throw Object.assign(new Error("insegura"), { name: "SecurityError" });
        const stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 }, audio: false });
        if (cancelled) { stopStream(stream); return; }
        streamRef.current = stream;
        if (videoRef.current) { videoRef.current.srcObject = stream; await videoRef.current.play().catch(() => undefined); }
        setError("");
      } catch (reason) {
        if (cancelled) return;
        release();
        setOn(false);
        setError(cameraErrorMessage(reason));
      }
    })();
    return () => { cancelled = true; };
  }, [on]);

  // Al salir o cerrar la pestaña, la cámara se apaga.
  useEffect(() => {
    window.addEventListener("pagehide", release);
    return () => { window.removeEventListener("pagehide", release); release(); };
  }, []);

  return <div className="card form-stack conductor-camera" aria-label="Vista previa de la cámara">
    <h2>Vista previa de la cámara</h2>
    <p className="muted">Solo la ves tú, en esta computadora: la persona no se ve a sí misma. La imagen no se envía ni se guarda. Úsala cuando la pantalla de la persona está abierta en esta misma computadora.</p>
    <div className={reading ? "conductor-camera-body has-reading" : "conductor-camera-body"}>
      <div className="form-stack">
        <div className="conductor-camera-frame" hidden={!on}>
          <video ref={videoRef} playsInline muted aria-label="Vista previa de la cámara para quien conduce" />
        </div>
        {error && <p role="alert">{error}</p>}
        <div className="inline-actions">
          <Button variant="secondary" onClick={() => setOn((value) => !value)}>
            {on ? "Ocultar la vista previa" : "Ver la cámara"}</Button>
        </div>
      </div>
      {reading}
    </div>
  </div>;
}
