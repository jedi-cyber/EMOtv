import type { MetricCapture, SessionMetrics } from "../api/types";
import { Callout } from "../components/Callout";

const issueNames: Record<string, string> = {
  no_frame: "sin imagen de la cámara", no_face: "sin rostro", off_center: "rostro no centrado", too_small: "rostro lejos",
  too_dark: "poca luz", too_bright: "demasiada luz", tilted: "cabeza inclinada",
};

function quality(item: MetricCapture) {
  return item.quality === "good" ? "Buena" : `Marcada: ${item.quality_issues.map((issue) => issueNames[issue] ?? issue).join(", ")}`;
}

const percent = (value: number | null) => (value == null ? "—" : `${Math.round(value * 100)} %`);

/** Métricas por estímulo: describen lo registrado, no lo interpretan. */
export function StimulusMetrics({ metrics, expressionLabel }: { metrics: SessionMetrics; expressionLabel: (key: string | null) => string }) {
  return <div className="form-stack">
    {metrics.emotional.length > 0 && <>
      <p><strong>{metrics.totals.sentence}</strong></p>
      {metrics.totals.excluded_captures > 0 && <p className="muted">
        {metrics.totals.excluded_captures} {metrics.totals.excluded_captures === 1 ? "captura marcada por calidad se muestra" : "capturas marcadas por calidad se muestran"}, pero no cuenta en los totales.
      </p>}
      <div className="table-wrap"><table><thead><tr>
        <th>Estímulo</th><th>Expresión esperada</th><th>Expresión estimada</th><th>Probabilidad</th><th>Desde la aparición</th><th>Calidad</th><th>Coincide</th>
      </tr></thead><tbody>{metrics.emotional.flatMap((item) => item.captures.length === 0
        ? [<tr key={item.step_index}><td>{item.title}</td><td>{expressionLabel(item.expected_expression)}</td>
          <td colSpan={5} className="muted">{item.skipped ? "Se saltó" : "Sin capturas"}</td></tr>]
        : item.captures.map((capture, index) => <tr key={capture.id}>
          <td>{index === 0 ? item.title : ""}</td>
          <td>{index === 0 ? expressionLabel(item.expected_expression) : ""}</td>
          <td>{capture.emotion ? expressionLabel(capture.emotion) : <span className="muted">—</span>}</td>
          <td>{percent(capture.probability)}</td>
          <td>{capture.seconds_since_stimulus} s</td>
          <td>{quality(capture)}</td>
          <td>{capture.matches_expected == null ? "—" : capture.matches_expected ? "Sí" : "No"}{!capture.counted && <span className="muted"> (no cuenta)</span>}</td>
        </tr>))}</tbody></table></div>
    </>}
    {metrics.abstract.length > 0 && <>
      <h3>Imágenes abstractas</h3>
      {metrics.abstract_notice && <Callout variant="info" role="note">{metrics.abstract_notice}</Callout>}
      <ul className="card-list">{metrics.abstract.map((item) => <li key={item.step_index} className="card">
        <strong>{item.title}</strong>
        <p>{item.said ? `Dijo ver: «${item.said}»` : <span className="muted">No se registró lo que dijo ver.</span>}</p>
        <p className="muted">{item.captures.length === 0 ? "Sin capturas." : `Expresiones estimadas: ${item.captures.map((capture) =>
          `${capture.emotion ? expressionLabel(capture.emotion) : "sin expresión"} a los ${capture.seconds_since_stimulus} s${capture.quality === "flagged" ? " (marcada)" : ""}`).join("; ")}.`}</p>
      </li>)}</ul>
    </>}
  </div>;
}
