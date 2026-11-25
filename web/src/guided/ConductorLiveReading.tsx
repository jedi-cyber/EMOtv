import type { ConductorLiveReading as Reading } from "../api/types";
import { percent } from "../analysis/LiveExpressionPanel";
import { useExpressionCatalog } from "../expressions/ExpressionCatalog";

const issueHints: Record<string, string> = {
  no_frame: "no llega imagen de la cámara", no_face: "no se ve el rostro", off_center: "el rostro no está centrado",
  too_small: "el rostro está muy lejos", too_dark: "hay poca luz", too_bright: "hay demasiada luz",
  tilted: "la cabeza está inclinada",
};

export const CONDUCTOR_READING_NOTICE =
  "Estimación del modelo sobre la expresión visible de la persona; no indica lo que siente.";

function Bar({ label, value, small = false }: { label: string; value: number; small?: boolean }) {
  return <div className={`progress-track${small ? " small" : ""}`} role="progressbar" aria-label={label}
    aria-valuemin={0} aria-valuemax={100} aria-valuenow={value}><div style={{ width: `${value}%` }} /></div>;
}

/**
 * Lo que estima la cámara ahora, solo en la pantalla de quien conduce: la
 * expresión estimada, su confianza y las cinco expresiones. Llega con el estado
 * de la sesión, a partir de los cuadros que envía la pantalla de la persona; esa
 * pantalla nunca la recibe. No se guarda: es la última estimación en memoria.
 */
export function ConductorLiveReading({ reading, embedded = false }: {
  reading: Reading | null | undefined;
  /** Dentro de la tarjeta de la vista previa, junto al video. */
  embedded?: boolean;
}) {
  const { label: expressionName } = useExpressionCatalog();
  return <section className={embedded ? "form-stack conductor-reading" : "card form-stack conductor-reading"}
    aria-label="Lo que estima la cámara">
    {embedded ? <h3>Lo que estima la cámara</h3> : <h2>Lo que estima la cámara</h2>}
    <p className="muted">Solo lo ves tú: la pantalla de la persona no muestra este resultado. No se guarda.</p>
    <div className="live-expression" aria-live="polite">
      {!reading
        ? <p>Sin lectura en este momento. La cámara se analiza en los pasos que la usan, con la pantalla de la persona abierta.</p>
        : !reading.face_detected
        ? <p className="live-expression-face">La cámara no estima una expresión: {reading.quality_issues.map((issue) => issueHints[issue] ?? issue).join(", ") || "no se ve el rostro"}. Pide a la persona que mire de frente, con buena luz.</p>
        : <>
          <p className="live-expression-name">{reading.emotion ? expressionName(reading.emotion) : "Analizando…"}</p>
          <div className="progress-label"><span>Confianza</span><strong>{percent(reading.confidence)} %</strong></div>
          <Bar label="Confianza de la expresión estimada" value={percent(reading.confidence)} />
          {reading.distribution.length > 0 && <ul className="live-top" aria-label="Expresiones estimadas">
            {reading.distribution.map((item) => <li key={item.emotion}>
              <span>{expressionName(item.emotion)} · {percent(item.probability)} %</span>
              <Bar small label={`Probabilidad de ${expressionName(item.emotion)}`} value={percent(item.probability)} />
            </li>)}
          </ul>}
        </>}
      <p className="muted">{CONDUCTOR_READING_NOTICE}</p>
    </div>
  </section>;
}
