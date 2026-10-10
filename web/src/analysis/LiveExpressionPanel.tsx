import { useExpressionCatalog } from "../expressions/ExpressionCatalog";

export type LiveReading = {
  face_detected: boolean;
  emotion: string | null;
  emotion_confidence: number | null;
  top: { emotion: string; probability: number }[];
  stable_seconds: number;
  required_stable_seconds: number;
  can_confirm: boolean;
  blocked_reason: string | null;
};

export const LIVE_DISCLAIMER = "Estimación del modelo sobre la expresión visible; no indica lo que sientes.";

export const percent = (value: number | null | undefined) => Math.round(Math.max(0, Math.min(1, value ?? 0)) * 100);

function Bar({ label, value, small = false }: { label: string; value: number; small?: boolean }) {
  return <div className={`progress-track${small ? " small" : ""}`} role="progressbar" aria-label={label}
    aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}><div style={{ width: `${value}%` }} /></div>;
}

/** Lectura en vivo del modelo. Solo muestra el último mensaje; no guarda historial. */
export function LiveExpressionPanel({ live }: { live: LiveReading | null }) {
  const { label: expressionName } = useExpressionCatalog();
  const required = live?.required_stable_seconds ?? 1;
  const stability = required > 0 ? percent((live?.stable_seconds ?? 0) / required) : (live?.emotion ? 100 : 0);
  return <div className="live-expression" aria-live="polite">
    {!live ? <p>Conectando con el analizador…</p>
      : !live.face_detected ? <p className="live-expression-face">Ubica tu rostro en el centro de la cámara, de frente y con buena luz.</p>
        : <>
          <p className="live-expression-name">{live.emotion ? expressionName(live.emotion) : "Analizando…"}</p>
          <div className="progress-label"><span>Confianza</span><strong>{percent(live.emotion_confidence)} %</strong></div>
          <Bar label="Confianza de la expresión estimada" value={percent(live.emotion_confidence)} />
          {live.top.length > 0 && <ul className="live-top" aria-label="Expresiones más probables">
            {live.top.map((item) => <li key={item.emotion}>
              <span>{expressionName(item.emotion)} · {percent(item.probability)} %</span>
              <Bar small label={`Probabilidad de ${expressionName(item.emotion)}`} value={percent(item.probability)} />
            </li>)}
          </ul>}
          <div className="progress-label"><span>Estabilidad</span><strong>{Math.min(live.stable_seconds, required).toFixed(1)} / {required} s</strong></div>
          <Bar label="Estabilidad de la expresión" value={stability} />
        </>}
    <p className="muted">{LIVE_DISCLAIMER}</p>
  </div>;
}
