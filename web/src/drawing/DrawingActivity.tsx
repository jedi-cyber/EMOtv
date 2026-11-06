import { useCallback, useEffect, useRef, useState } from "react";
import type { PointerEvent as ReactPointerEvent } from "react";
import { speakText, speechAvailable, stopExerciseSpeech } from "../analysis/exerciseSpeech";
import { Button } from "../components/Button";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { emotionPictograms, practiceTargetNames } from "../stimuli/labels";
import {
  INK_COLORS, INK_SIZES, MAX_POINTS, drawStroke, pointCount, redraw, relativePoint,
  type DrawingTool, type Stroke,
} from "./strokes";

export const DRAWING_INSTRUCTION = "Dibuja una cara que muestre una emoción.";
export const DRAWING_QUESTION = "¿Qué emoción quisiste dibujar?";
/** Las emociones para señalar lo que se quiso dibujar; el dibujo no se clasifica. */
export const DRAWING_EMOTIONS = ["happiness", "sadness", "anger", "fear", "surprise", "disgust", "neutral"];

type Phase = "drawing" | "choosing" | "done";

/** En un paso de un protocolo: lo que dice el servidor y cómo enviar la emoción elegida. */
export interface DrawingSessionStep {
  instruction: string;
  question: string;
  options: { key: string; label: string }[];
  /** El paso terminó: respondido (por la persona o por quien conduce) o sin tiempo. */
  finished: boolean;
  chosen: string | null;
  message: string | null;
  /** Envía solo la emoción elegida; el dibujo no sale de la pantalla. */
  onChoose(key: string): Promise<void>;
  readAloud?: boolean;
}

export const DRAWING_TIME_UP = "Terminó el tiempo para dibujar.";

/**
 * Actividad de dibujo táctil: la persona dibuja una expresión y después señala
 * qué emoción quiso representar. El dibujo vive solo en la memoria de esta
 * pantalla: se borra al limpiar, al dibujar otra vez y al salir o recargar. No
 * se envía al servidor ni se guarda en el navegador, y EMOtv no lo interpreta.
 */
export function DrawingActivity({ onDrawingChange, session }: {
  /** Avisa si hay un dibujo en pantalla (para confirmar antes de salir). */
  onDrawingChange?(hasDrawing: boolean): void;
  /** Como paso de un protocolo; sin él, la actividad suelta (se puede dibujar otra vez). */
  session?: DrawingSessionStep;
}) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [strokes, setStrokes] = useState<Stroke[]>([]);
  const strokesRef = useRef<Stroke[]>([]);
  const current = useRef<{ pointerId: number; stroke: Stroke } | null>(null);
  const [tool, setTool] = useState<DrawingTool>("pen");
  const [color, setColor] = useState(INK_COLORS[0].value);
  const [size, setSize] = useState(INK_SIZES[1].width);
  const [phase, setPhase] = useState<Phase>("drawing");
  const [chosen, setChosen] = useState<string | null>(null);
  const [confirmClear, setConfirmClear] = useState(false);
  const [full, setFull] = useState(false);
  const [sending, setSending] = useState(false);
  const [sendError, setSendError] = useState("");

  strokesRef.current = strokes;
  const hasDrawing = strokes.length > 0;
  useEffect(() => { onDrawingChange?.(hasDrawing); }, [hasDrawing, onDrawingChange]);

  // En una sesión, el servidor decide cuándo termina el paso (respuesta o tiempo).
  const sessionDone = Boolean(session?.finished);
  useEffect(() => {
    if (!sessionDone) return;
    current.current = null;
    setPhase("done");
    setChosen(session?.chosen ?? null);
  }, [sessionDone, session?.chosen]);
  const instruction = session?.instruction ?? DRAWING_INSTRUCTION;
  const question = session?.question ?? DRAWING_QUESTION;
  const options = session?.options ?? DRAWING_EMOTIONS.map((key) => ({ key, label: practiceTargetNames[key] }));
  const readAloud = Boolean(session?.readAloud);
  useEffect(() => {
    if (readAloud && phase !== "done") speakText(phase === "drawing" ? instruction : question);
  }, [readAloud, phase, instruction, question]);

  async function choose(key: string) {
    if (!session) { setChosen(key); setPhase("done"); return; }
    setSending(true);
    setSendError("");
    try {
      await session.onChoose(key);
      setChosen(key);
      setPhase("done");
    } catch {
      setSendError("No se pudo enviar tu elección. Intenta de nuevo o avisa a quien conduce la sesión.");
    } finally {
      setSending(false);
    }
  }

  const context = useCallback(() => canvasRef.current?.getContext("2d") ?? null, []);

  /** Ajusta el lienzo a su tamaño en pantalla (y a la densidad de píxeles) y redibuja. */
  const fit = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ratio = window.devicePixelRatio || 1;
    const width = Math.max(1, Math.round(canvas.clientWidth * ratio));
    const height = Math.max(1, Math.round(canvas.clientHeight * ratio));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    const ctx = context();
    if (ctx) redraw(ctx, strokesRef.current, canvas.width, canvas.height);
  }, [context]);

  useEffect(() => {
    fit();
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    const observer = typeof ResizeObserver === "undefined" ? null : new ResizeObserver(() => fit());
    observer?.observe(canvas);
    window.addEventListener("orientationchange", fit);
    // Safari antiguo ignora touch-action: el dedo sobre el lienzo nunca desplaza la página.
    const block = (event: TouchEvent) => { if (event.cancelable) event.preventDefault(); };
    canvas.addEventListener("touchmove", block, { passive: false });
    canvas.addEventListener("touchstart", block, { passive: false });
    return () => {
      observer?.disconnect();
      window.removeEventListener("orientationchange", fit);
      canvas.removeEventListener("touchmove", block);
      canvas.removeEventListener("touchstart", block);
      stopExerciseSpeech();
      // Al salir, el dibujo se descarta también del lienzo.
      canvas.width = 0;
      canvas.height = 0;
    };
  }, [fit]);

  // Deshacer, limpiar o dibujar otra vez cambian la lista: se redibuja todo.
  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = context();
    if (canvas && ctx) redraw(ctx, strokes, canvas.width, canvas.height);
  }, [strokes, context]);

  /** La zona de dibujo sin el borde: el trazo cae justo bajo el dedo. */
  function area(canvas: HTMLCanvasElement) {
    const rect = canvas.getBoundingClientRect();
    return { left: rect.left + canvas.clientLeft, top: rect.top + canvas.clientTop,
      width: canvas.clientWidth || rect.width, height: canvas.clientHeight || rect.height };
  }

  function point(event: ReactPointerEvent<HTMLCanvasElement>): [number, number] {
    return relativePoint(event.clientX, event.clientY, area(event.currentTarget));
  }

  function start(event: ReactPointerEvent<HTMLCanvasElement>) {
    // Un solo dedo dibuja: un segundo toque (la palma, otro dedo) se ignora.
    if (phase !== "drawing" || current.current || !event.isPrimary) return;
    event.preventDefault();
    if (pointCount(strokesRef.current) >= MAX_POINTS) return;
    // El trazo sigue aunque el dedo salga del lienzo; si el navegador no puede capturarlo, se dibuja igual.
    try { event.currentTarget.setPointerCapture?.(event.pointerId); } catch { /* sin captura */ }
    const stroke: Stroke = { tool, color, width: size, points: [point(event)] };
    current.current = { pointerId: event.pointerId, stroke };
    const canvas = canvasRef.current;
    const ctx = context();
    if (canvas && ctx) drawStroke(ctx, stroke, canvas.width, canvas.height);
  }

  function move(event: ReactPointerEvent<HTMLCanvasElement>) {
    const active = current.current;
    if (!active || active.pointerId !== event.pointerId) return;
    event.preventDefault();
    const native = event.nativeEvent as PointerEvent;
    const samples = typeof native.getCoalescedEvents === "function" ? native.getCoalescedEvents() : [];
    const before = active.stroke.points.length;
    const room = MAX_POINTS - pointCount(strokesRef.current) - before;
    const rect = area(event.currentTarget);
    const added = (samples.length ? samples : [native])
      .slice(0, Math.max(0, room))
      .map((sample) => relativePoint(sample.clientX, sample.clientY, rect));
    if (added.length === 0) return;
    active.stroke.points.push(...added);
    const canvas = canvasRef.current;
    const ctx = context();
    if (canvas && ctx) drawStroke(ctx, active.stroke, canvas.width, canvas.height, before);
  }

  function end(event: ReactPointerEvent<HTMLCanvasElement>) {
    const active = current.current;
    if (!active || active.pointerId !== event.pointerId) return;
    current.current = null;
    try { event.currentTarget.releasePointerCapture?.(event.pointerId); } catch { /* ya liberado */ }
    setStrokes((items) => [...items, active.stroke]);
  }

  function again() {
    setStrokes([]);
    setChosen(null);
    setPhase("drawing");
  }

  const locked = phase !== "drawing";
  return <div className={`drawing-activity${full ? " drawing-activity--full" : ""}`}>
    <div className="drawing-header">
      <p className="participant-instruction">{phase === "drawing" ? instruction : question}</p>
      {speechAvailable() && <Button variant="secondary" size="sm" onClick={() => {
        speakText(phase === "drawing" ? instruction : question);
      }}>Escuchar</Button>}
    </div>

    {/* Primero el lienzo; debajo, las herramientas al alcance del pulgar. */}
    <div className="drawing-surface">
      <canvas ref={canvasRef} className="drawing-canvas" role="img"
        aria-label={hasDrawing ? "Lienzo con tu dibujo" : "Lienzo en blanco: dibuja con el dedo o el lápiz"}
        data-locked={locked || undefined}
        onPointerDown={start} onPointerMove={move} onPointerUp={end} onPointerCancel={end}
        onContextMenu={(event) => { event.preventDefault(); }} />
    </div>

    {phase === "drawing" && <div className="drawing-tools" role="toolbar" aria-label="Herramientas de dibujo">
      <div className="drawing-group" role="group" aria-label="Color">
        {INK_COLORS.map((ink) => <button key={ink.key} type="button" className="drawing-swatch"
          aria-pressed={tool === "pen" && color === ink.value}
          onClick={() => { setTool("pen"); setColor(ink.value); }}>
          <span className="drawing-swatch-color" style={{ background: ink.value }} aria-hidden="true" />{ink.name}
        </button>)}
      </div>
      <div className="drawing-group" role="group" aria-label="Grosor">
        {INK_SIZES.map((item) => <button key={item.key} type="button" className="drawing-size"
          aria-pressed={size === item.width} onClick={() => { setSize(item.width); }}>
          <span className="drawing-size-dot" style={{ width: `${0.3 + item.width * 25}rem`, height: `${0.3 + item.width * 25}rem` }} aria-hidden="true" />{item.name}
        </button>)}
      </div>
      <div className="drawing-group" role="group" aria-label="Acciones">
        <button type="button" className="drawing-size" aria-pressed={tool === "eraser"}
          onClick={() => { setTool(tool === "eraser" ? "pen" : "eraser"); }}>Borrador</button>
        <Button variant="secondary" disabled={!hasDrawing} onClick={() => { setStrokes((items) => items.slice(0, -1)); }}>Deshacer</Button>
        <Button variant="secondary" disabled={!hasDrawing} onClick={() => { setConfirmClear(true); }}>Limpiar</Button>
        <Button variant="ghost" onClick={() => { setFull(!full); }}>{full ? "Lienzo normal" : "Lienzo más grande"}</Button>
      </div>
    </div>}

    {phase === "drawing" && <div className="inline-actions drawing-finish">
      <Button variant="primary" disabled={!hasDrawing} onClick={() => { setPhase("choosing"); }}>Terminé</Button>
      <p className="muted">{session
        ? "El dibujo se queda en esta pantalla: no se envía ni se guarda. Solo se registra la emoción que elijas."
        : "El dibujo se queda en esta pantalla: no se envía ni se guarda."}</p>
    </div>}

    {phase === "choosing" && <>
      <div className="recognition-options">
        {options.map((option) => <Button key={option.key} className="recognition-option" variant="secondary"
          disabled={sending} onClick={() => { void choose(option.key); }}>
          <span className="recognition-pictogram" aria-hidden="true">{emotionPictograms[option.key]}</span>
          {option.label}
        </Button>)}
      </div>
      {sendError && <p role="alert">{sendError}</p>}
      <Button variant="ghost" disabled={sending} onClick={() => { setPhase("drawing"); }}>Seguir dibujando</Button>
    </>}

    {phase === "done" && <div className="drawing-done">
      {/* Describe lo que eligió la persona; no se compara con el dibujo. */}
      <p className="participant-achieved recognition-answer" role="status">
        {session ? (session.message ?? (session.finished && !session.chosen ? DRAWING_TIME_UP : ""))
          : chosen ? `Dibujaste ${practiceTargetNames[chosen].toLowerCase()}.` : ""}</p>
      {/* En una sesión, repetir el paso lo decide quien conduce. */}
      {!session && <Button variant="primary" onClick={again}>Dibujar otra vez</Button>}
    </div>}

    <ConfirmDialog open={confirmClear} title="Limpiar el lienzo" message="Se borrará todo el dibujo. ¿Quieres limpiarlo?"
      confirmLabel="Limpiar" onCancel={() => { setConfirmClear(false); }}
      onConfirm={() => { setConfirmClear(false); setStrokes([]); }} />
  </div>;
}
