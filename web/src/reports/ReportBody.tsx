import type { ReactNode } from "react";
import type { ReportSection, SessionReport } from "../api/types";
import { Callout } from "../components/Callout";
import { SessionTimeline } from "../insights/SessionTimeline";
import { StimulusMetrics } from "../insights/StimulusMetrics";
import { emotionModelName } from "../sessions/labels";

const day = (value: string) => new Date(value).toLocaleString("es-PE", { dateStyle: "long", timeStyle: "short" });

export const sectionNames: Record<ReportSection, string> = {
  timeline: "Línea de tiempo",
  metrics: "Métricas por estímulo",
  questionnaires: "Cuestionarios",
  narrative: "Texto de quien condujo la sesión",
  general: "General",
};

/**
 * Contenido del reporte: el mismo en pantalla y al imprimir. Lleva siempre el
 * aviso de que las expresiones son estimaciones de apoyo y el modelo usado.
 * Muestra el código del participante; el sistema no conoce su nombre.
 */
export function ReportBody({ report, expressionLabel, renderSection, narrative, printing = false }: {
  report: SessionReport;
  printing?: boolean;
  expressionLabel: (key: string | null) => string;
  /** Lo que va al final de cada sección (comentarios del docente en pantalla). */
  renderSection?: (section: ReportSection) => ReactNode;
  /** Reemplaza el texto por un editor cuando se puede editar. */
  narrative?: ReactNode;
}) {
  const questionnaires = report.timeline.lanes.questionnaires;
  return <div className="report-body">
    <dl className="detail-grid">
      <div><dt>Participante</dt><dd>{report.participant_code}</dd></div>
      <div><dt>Sesión</dt><dd>{day(report.session.started_at)}</dd></div>
      <div><dt>Modelo facial</dt><dd>{emotionModelName(report.session.emotion_model_id)}{report.session.emotion_model_version ? ` · versión ${report.session.emotion_model_version}` : ""}</dd></div>
      <div><dt>Versión del reporte</dt><dd>{report.version}</dd></div>
    </dl>
    <Callout variant="info" role="note">{report.estimates_notice}</Callout>
    {report.abstract_notice && <Callout variant="info" role="note">{report.abstract_notice}</Callout>}

    <section className="report-section">
      <h2>{sectionNames.timeline}</h2>
      <SessionTimeline timeline={report.timeline} expressionLabel={expressionLabel} eventsOpen={printing} />
      {renderSection?.("timeline")}
    </section>
    <section className="report-section">
      <h2>{sectionNames.metrics}</h2>
      <StimulusMetrics metrics={report.metrics} expressionLabel={expressionLabel} />
      {renderSection?.("metrics")}
    </section>
    <section className="report-section">
      <h2>{sectionNames.questionnaires}</h2>
      {questionnaires.length === 0 ? <p className="muted">La sesión no tuvo cuestionarios.</p>
        : questionnaires.map((item, index) => <div key={index}>
          <h3>{item.moment === "pre" ? "Antes del análisis" : "Después del análisis"}: {item.title}</h3>
          <dl className="answer-list">{item.answers.map((answer, position) => <div key={position}>
            <dt>{answer.question}</dt>
            <dd>{answer.answer == null ? <span className="muted">Sin respuesta</span> : Array.isArray(answer.answer) ? answer.answer.join(", ")
              : answer.kind === "faces" ? `Figura ${answer.answer} de 5` : String(answer.answer)}</dd>
          </div>)}</dl>
        </div>)}
      <p className="muted">Las respuestas se muestran tal como se dieron; no se suman ni se interpretan.</p>
      {renderSection?.("questionnaires")}
    </section>
    <section className="report-section">
      <h2>{sectionNames.narrative}</h2>
      {narrative ?? (report.narrative ? <p className="report-narrative">{report.narrative}</p> : <p className="muted">Sin texto todavía.</p>)}
      {renderSection?.("narrative")}
    </section>
  </div>;
}
