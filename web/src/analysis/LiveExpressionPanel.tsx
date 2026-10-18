import { useExpressionCatalog } from "../expressions/ExpressionCatalog";
import { StatusChip } from "../components/StatusChip";

export type LiveClass = { emotion: string; probability: number; baseline?: number; change?: number };
export type LiveCalibration = {
  state: "none" | "calibrating" | "calibrated";
  progress: number;
  suggested: string | null;
  notice: string | null;
};

export type LiveReading = {
  face_detected: boolean;
  emotion: string | null;
  emotion_confidence: number | null;
  /** Todas las clases del modelo, de mayor a menor. */
  distribution: LiveClass[];
  calibration: LiveCalibration;
  stable_seconds: number;
  required_stable_seconds: number;
  can_confirm: boolean;
  blocked_reason: string | null;
};

export const NO_CALIBRATION: LiveCalibration = { state: "none", progress: 0, suggested: null, notice: null };

export const LIVE_DISCLAIMER = "Estimación del modelo sobre la expresión visible; no indica lo que sientes.";

export const percent = (value: number | null | undefined) => Math.round(Math.max(0, Math.min(1, value ?? 0)) * 100);

/** Cambio respecto a la base en puntos porcentuales, con signo. */
export const points = (change: number) => {
  const value = Math.round(change * 100);
  return `${value > 0 ? "+" : value < 0 ? "−" : "±"}${Math.abs(value)} pts`;
};

function Bar({ label, value, small = false }: { label: string; value: number; small?: boolean }) {
  return <div className={`progress-track${small ? " small" : ""}`} role="progressbar" aria-label={label}
    aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}><div style={{ width: `${value}%` }} /></div>;
}

/** Lectura en vivo del modelo. Solo muestra el último mensaje; no guarda historial. */
export function LiveExpressionPanel({ live }: { live: LiveReading | null }) {
  const { label: expressionName } = useExpressionCatalog();
  const required = live?.required_stable_seconds ?? 1;
  const stability = required > 0 ? percent((live?.stable_seconds ?? 0) / required) : (live?.emotion ? 100 : 0);
  const calibration = live?.calibration ?? NO_CALIBRATION;
  const calibrated = calibration.state === "calibrated";
  return <div className="live-expression" aria-live="polite">
    {calibration.state === "calibrating" && <div className="live-calibration">
      <p><strong>Calibrando…</strong> Mantén el rostro relajado y mira a la cámara.</p>
      <Bar label="Progreso de la calibración" value={percent(calibration.progress)} />
    </div>}
    {calibration.notice && <p className="live-calibration-notice">{calibration.notice}</p>}
    {!live ? <p>Conectando con el analizador…</p>
      : !live.face_detected ? <p className="live-expression-face">Ubica tu rostro en el centro de la cámara, de frente y con buena luz.</p>
        : <>
          <p className="live-expression-name">{live.emotion ? expressionName(live.emotion) : "Analizando…"}</p>
          <div className="progress-label"><span>Confianza</span><strong>{percent(live.emotion_confidence)} %</strong></div>
          <Bar label="Confianza de la expresión estimada" value={percent(live.emotion_confidence)} />
          <div className="live-calibration-status">
            <StatusChip tone={calibrated ? "success" : "neutral"}>{calibrated ? "Lectura calibrada" : "Lectura sin calibrar"}</StatusChip>
            {calibrated && <p>{calibration.suggested
              ? <>Mayor aumento respecto a tu base: <strong>{expressionName(calibration.suggested)}</strong></>
              : "Sin un cambio claro respecto a tu base."}</p>}
          </div>
          {live.distribution.length > 0 && <ul className="live-top" aria-label="Expresiones estimadas">
            {live.distribution.map((item) => <li key={item.emotion}>
              <span>{expressionName(item.emotion)} · {percent(item.probability)} %{calibrated && item.change != null && ` (${points(item.change)})`}</span>
              <Bar small label={`Probabilidad de ${expressionName(item.emotion)}`} value={percent(item.probability)} />
            </li>)}
          </ul>}
          <div className="progress-label"><span>Estabilidad</span><strong>{Math.min(live.stable_seconds, required).toFixed(1)} / {required} s</strong></div>
          <Bar label="Estabilidad de la expresión" value={stability} />
          {calibrated && <p className="muted">La calibración solo cambia esta comparación. Se registra la lectura directa del modelo.</p>}
        </>}
    <p className="muted">{LIVE_DISCLAIMER}</p>
  </div>;
}
