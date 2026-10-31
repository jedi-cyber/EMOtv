import type { MetricCapture, PracticeOutcome, SessionMetrics, SessionPractice } from "../api/types";
import { Callout } from "../components/Callout";
import { practiceTargetNames } from "../stimuli/labels";

export const practiceOutcomeNames: Record<PracticeOutcome, string> = {
  achieved: "Logró la expresión pedida", timed_out: "Terminó el tiempo", skipped: "Se saltó", stopped: "La sesión se detuvo",
};
export const secondsText = (value: number) => `${value.toLocaleString("es-PE", { maximumFractionDigits: 1 })} s`;

const issueNames: Record<string, string> = {
  no_frame: "sin imagen de la cámara", no_face: "sin rostro", off_center: "rostro no centrado", too_small: "rostro lejos",
  too_dark: "poca luz", too_bright: "demasiada luz", tilted: "cabeza inclinada",
};

function quality(item: MetricCapture) {
  return item.quality === "good" ? "Buena" : `Marcada: ${item.quality_issues.map((issue) => issueNames[issue] ?? issue).join(", ")}`;
}

const percent = (value: number | null) => (value == null ? "—" : `${Math.round(value * 100)} %`);

/** Ejercicios de práctica de una sesión, con el aviso fijo sobre los modelos. */
export function PracticeMetrics({ practice }: { practice: SessionPractice }) {
  const { totals } = practice;
  return <section className="form-stack" aria-label="Ejercicios de práctica">
    <h3>Ejercicios de práctica</h3>
    <Callout variant="info" role="note">{practice.notice}</Callout>
    <p><strong>{totals.sentence}</strong></p>
    {totals.average_sentence && <p>{totals.average_sentence}</p>}
    {totals.feedback_sentence && <p className="muted">{totals.feedback_sentence}</p>}
    {(totals.skipped > 0 || totals.stopped > 0 || totals.not_reached > 0) && <p className="muted">
      No cuentan en el total: {[
        totals.skipped > 0 && `${totals.skipped} ${totals.skipped === 1 ? "se saltó" : "se saltaron"}`,
        totals.stopped > 0 && `${totals.stopped} quedó a medias al detener la sesión`,
        totals.not_reached > 0 && `${totals.not_reached} sin aplicar`,
      ].filter(Boolean).join(", ")}.</p>}
    <div className="table-wrap"><table><thead><tr>
      <th>Paso</th><th>Expresión pedida</th><th>Resultado</th><th>Hasta lograrla</th><th>Señal visual</th>
    </tr></thead><tbody>{practice.exercises.map((item) => <tr key={item.step_index}>
      <td>{item.step_index + 1}</td>
      <td>{practiceTargetNames[item.target_expression] ?? item.target_expression}</td>
      <td>{item.outcome ? practiceOutcomeNames[item.outcome] : <span className="muted">Sin aplicar</span>}</td>
      <td>{item.seconds_to_achieve != null ? secondsText(item.seconds_to_achieve) : "—"}</td>
      <td>{item.feedback_visible == null ? "—" : item.feedback_visible ? "Activa" : "Apagada"}</td>
    </tr>)}</tbody></table></div>
    {practice.by_target.length > 1 && <div className="table-wrap"><table><thead><tr>
      <th>Expresión pedida</th><th>Logrados</th><th>Tiempo promedio</th>
    </tr></thead><tbody>{practice.by_target.map((row) => <tr key={row.target_expression}>
      <td>{practiceTargetNames[row.target_expression] ?? row.target_expression}</td>
      <td>{row.achieved} de {row.applied}</td>
      <td>{row.average_seconds_to_achieve != null ? secondsText(row.average_seconds_to_achieve) : "—"}</td>
    </tr>)}</tbody></table></div>}
  </section>;
}

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
    {metrics.practice && <PracticeMetrics practice={metrics.practice} />}
  </div>;
}
