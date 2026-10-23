import type { ParticipantTrends } from "../api/types";

type Group = ParticipantTrends["protocols"][number];

const WIDTH = 640;
const HEIGHT = 220;
const PAD = { left: 56, right: 24, top: 20, bottom: 40 };
const day = (value: string) => new Date(value).toLocaleDateString("es-PE", { day: "numeric", month: "short" });

/**
 * Coincidencias de los estímulos emocionales en sesiones con el mismo
 * protocolo. Cada punto dice "x de y"; no hay valoraciones. Con menos de dos
 * sesiones comparables solo se muestra el aviso.
 */
export function TrendChart({ group }: { group: Group }) {
  if (!group.comparable) return <p className="muted">{group.message}</p>;
  const points = group.sessions.filter((item) => item.counted > 0);
  const plotWidth = WIDTH - PAD.left - PAD.right;
  const plotHeight = HEIGHT - PAD.top - PAD.bottom;
  const x = (index: number) => PAD.left + (points.length === 1 ? plotWidth / 2 : (index / (points.length - 1)) * plotWidth);
  const y = (item: (typeof points)[number]) => PAD.top + (1 - item.matched / item.counted) * plotHeight;
  const path = points.map((item, index) => `${index === 0 ? "M" : "L"} ${x(index)} ${y(item)}`).join(" ");
  return <figure className="trend">
    <svg viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label={group.message}>
      {[0, 0.5, 1].map((share) => <g key={share}>
        <line x1={PAD.left} x2={WIDTH - PAD.right} y1={PAD.top + (1 - share) * plotHeight} y2={PAD.top + (1 - share) * plotHeight} className="timeline-grid" />
        <text x={PAD.left - 8} y={PAD.top + (1 - share) * plotHeight + 4} textAnchor="end" className="timeline-tick">{share === 0 ? "ninguno" : share === 1 ? "todos" : "la mitad"}</text>
      </g>)}
      <path d={path} className="trend-line" />
      {points.map((item, index) => <g key={item.session_id}>
        <circle cx={x(index)} cy={y(item)} r={6} className="timeline-mark" />
        <text x={x(index)} y={y(item) - 12} textAnchor="middle" className="timeline-label">{item.matched} de {item.counted}</text>
        <text x={x(index)} y={HEIGHT - 12} textAnchor="middle" className="timeline-tick">{day(item.started_at)}</text>
      </g>)}
    </svg>
    <figcaption>{group.message}</figcaption>
    <ol className="timeline-events">{group.sessions.map((item) => <li key={item.session_id}>
      {day(item.started_at)} (versión {item.protocol_version}): {item.sentence}
    </li>)}</ol>
  </figure>;
}
