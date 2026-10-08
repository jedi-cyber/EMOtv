import { useAssistant } from "../components/AssistantContext";
import { COMMON_LIMITATION, emiQuestionFor, useExpressionCatalog } from "./ExpressionCatalog";
import type { ExpressionInfo } from "./ExpressionCatalog";

const percent = (value: number) => Math.round(Math.max(0, Math.min(1, value)) * 100);

/**
 * Información base fija y revisable sobre la expresión registrada. Nunca llama
 * al LLM: Emi solo se abre si la persona quiere profundizar y decide preguntar.
 */
export function ExpressionResult({ expressionKey, confidence, info: provided }: {
  expressionKey: string;
  confidence: number | null;
  info?: ExpressionInfo | null;
}) {
  const catalog = useExpressionCatalog();
  const assistant = useAssistant();
  const info = provided ?? catalog.info(expressionKey);
  const label = info?.label_es ?? catalog.label(expressionKey);
  return <article className="expression-result" aria-labelledby="expression-result-title">
    <p className="step-caption">Expresión registrada</p>
    <h2 id="expression-result-title" className="expression-result-name">{label}</h2>
    {confidence != null && <p>Confianza del modelo: <strong>{percent(confidence)} %</strong></p>}
    {info ? <>
      <section><h3>¿Qué es?</h3><p>{info.what_it_is}</p></section>
      <section><h3>¿Por qué suele presentarse?</h3><p>{info.why_it_occurs}</p></section>
      <section><h3>¿Cómo se reconoce en el rostro?</h3><p>{info.facial_cues}</p></section>
      <section><h3>Para practicar</h3><p>{info.practice_tip}</p></section>
      <p className="muted">{info.limitation_note}</p>
    </> : <p className="muted">La información sobre esta expresión no está disponible en este momento.</p>}
    <div className="alert alert-warning expression-limitation" role="note">{info?.common_limitation ?? COMMON_LIMITATION}</div>
    {info?.review_status === "draft" && <p className="muted review-note">Contenido pendiente de revisión por profesionales de Psicología.</p>}
    {assistant && <button type="button" className="button secondary" onClick={() => assistant.askAssistant(emiQuestionFor(expressionKey, label))}>
      Preguntar a Emi sobre esta expresión
    </button>}
  </article>;
}
