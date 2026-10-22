import type { ReactNode } from "react";
import type { AnswerValue, MarkerKind, SessionTimeline as Timeline } from "../api/types";

const WIDTH = 1000;
const LABEL = 170;
const LANE = 48;
const PLOT = WIDTH - LABEL - 20;
const lanes = [
  { key: "questionnaires", label: "Cuestionarios" },
  { key: "stimuli", label: "Estímulos" },
  { key: "captures", label: "Expresión estimada" },
  { key: "said", label: "Lo que dijo ver" },
  { key: "markers", label: "Marcadores" },
  { key: "heart_rate", label: "Ritmo cardíaco" },
] as const;
const markerNames: Record<MarkerKind, string> = {
  distracted: "Se distrajo", laughed: "Se rió", cried: "Lloró", asked_to_stop: "Pidió parar", note: "Nota",
};

function seconds(value: number) {
  const whole = Math.round(value);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}

function answerText(value: AnswerValue | null) {
  if (value === null || value === undefined) return "sin respuesta";
  return Array.isArray(value) ? value.join(", ") : String(value);
}

interface Event { time: number; text: string }

/**
 * Línea de tiempo de una sesión en un solo eje. Todo se dibuja con el mismo
 * color: ninguna expresión tiene color propio. Las capturas marcadas por
 * calidad se dibujan huecas. Debajo, la misma información como lista.
 */
export function SessionTimeline({ timeline, expressionLabel }: { timeline: Timeline; expressionLabel: (key: string | null) => string }) {
  const duration = Math.max(timeline.duration_seconds, 1);
  const x = (time: number | null) => LABEL + (Math.min(Math.max(time ?? 0, 0), duration) / duration) * PLOT;
  const y = (index: number) => 24 + index * LANE + LANE / 2;
  const height = 24 + lanes.length * LANE + 28;
  const step = duration > 300 ? 60 : duration > 120 ? 30 : duration > 40 ? 10 : 5;
  const ticks = Array.from({ length: Math.floor(duration / step) + 1 }, (_, index) => index * step);
  const { questionnaires, stimuli, captures, said, markers } = timeline.lanes;

  const events: Event[] = [
    ...questionnaires.map((item) => ({ time: item.time, text: `Cuestionario ${item.moment === "pre" ? "previo" : "posterior"} «${item.title}»: ${item.answers.map((answer) => `${answer.question} ${answerText(answer.answer)}`).join("; ")}` })),
    ...stimuli.map((item) => ({ time: item.start ?? 0, text: `Aparece el estímulo «${item.title}»${item.skipped ? " (se saltó)" : ""}` })),
    ...captures.map((item) => ({ time: item.time, text: `Captura: ${item.emotion ? `${expressionLabel(item.emotion)} (estimada)` : "sin expresión estimada"}${item.quality === "flagged" ? ", marcada por calidad" : ""}` })),
    ...said.map((item) => ({ time: item.time, text: `Dijo ver en «${item.title}»: ${item.text}` })),
    ...markers.map((item) => ({ time: item.time, text: `${markerNames[item.kind]}${item.note ? `: ${item.note}` : ""}` })),
  ].sort((a, b) => a.time - b.time);

  const marks: Record<(typeof lanes)[number]["key"], ReactNode> = {
    questionnaires: questionnaires.map((item, index) => <g key={index}>
      <rect x={x(item.time) - 6} y={y(0) - 6} width={12} height={12} transform={`rotate(45 ${x(item.time)} ${y(0)})`} className="timeline-mark" />
      <title>{`${seconds(item.time)} · Cuestionario ${item.moment === "pre" ? "previo" : "posterior"}`}</title>
    </g>),
    stimuli: stimuli.map((item, index) => <g key={index}>
      <rect x={x(item.start)} y={y(1) - 12} width={Math.max(4, x(item.end ?? duration) - x(item.start))} height={24} rx={3}
        className={item.skipped ? "timeline-bar timeline-bar-skipped" : "timeline-bar"} />
      <title>{`${seconds(item.start ?? 0)} · ${item.title}${item.kind === "abstract" ? " (abstracta)" : ""}${item.skipped ? " · se saltó" : ""}`}</title>
    </g>),
    captures: captures.map((item, index) => <g key={index}>
      <circle cx={x(item.time)} cy={y(2)} r={6} className={item.quality === "good" ? "timeline-mark" : "timeline-mark-hollow"} />
      <title>{`${seconds(item.time)} · ${item.emotion ? `${expressionLabel(item.emotion)} (estimada)` : "Sin expresión"}${item.quality === "flagged" ? " · marcada por calidad" : ""}`}</title>
    </g>),
    said: said.map((item, index) => <g key={index}>
      <rect x={x(item.time) - 5} y={y(3) - 5} width={10} height={10} className="timeline-mark" />
      <title>{`${seconds(item.time)} · ${item.text}`}</title>
    </g>),
    markers: markers.map((item, index) => <g key={index}>
      <path d={`M ${x(item.time)} ${y(4) - 7} l 7 12 h -14 z`} className="timeline-mark" />
      <title>{`${seconds(item.time)} · ${markerNames[item.kind]}`}</title>
    </g>),
    heart_rate: <text x={LABEL + 8} y={y(5) + 4} className="timeline-empty">Sin sensor conectado (reservado)</text>,
  };

  return <figure className="timeline">
    <svg viewBox={`0 0 ${WIDTH} ${height}`} role="img" aria-label={`Línea de tiempo de ${seconds(duration)} con ${events.length} eventos`}>
      {lanes.map((lane, index) => <g key={lane.key}>
        <line x1={LABEL} x2={WIDTH - 20} y1={y(index)} y2={y(index)} className={lane.key === "heart_rate" ? "timeline-lane timeline-lane-reserved" : "timeline-lane"} />
        <text x={8} y={y(index) + 5} className="timeline-label">{lane.label}</text>
        {marks[lane.key]}
      </g>)}
      {ticks.map((tick) => <g key={tick}>
        <line x1={x(tick)} x2={x(tick)} y1={20} y2={height - 24} className="timeline-grid" />
        <text x={x(tick)} y={height - 8} textAnchor="middle" className="timeline-tick">{seconds(tick)}</text>
      </g>)}
    </svg>
    <figcaption className="muted">Cuadros rellenos: capturas de buena calidad; huecos: marcadas por calidad. Las expresiones son estimaciones del modelo.</figcaption>
    <details>
      <summary>Eventos en orden</summary>
      <ol className="timeline-events">{events.map((event, index) => <li key={index}><span className="timeline-time">{seconds(event.time)}</span> {event.text}</li>)}</ol>
    </details>
  </figure>;
}
