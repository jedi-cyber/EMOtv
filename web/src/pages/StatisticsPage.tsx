import { useState } from "react";
import type { FormEvent } from "react";
import type { SessionStatistics } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { BarChart } from "../components/BarChart";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { expectedExpressionNames } from "../stimuli/labels";

type Scope = "mine" | "group";

interface Filters {
  scope: Scope;
  date_from: string;
  date_to: string;
  protocol: string;
  audience: string;
}

const emptyFilters: Filters = { scope: "mine", date_from: "", date_to: "", protocol: "", audience: "" };
const audienceNames: Record<string, string> = { propia: "Propia", adulto: "Adultos", infantil: "Niños" };
const kindNames: Record<string, string> = {
  scale: "Escala", faces: "Caritas", single_choice: "Una opción", multiple_choice: "Varias opciones", short_text: "Texto breve",
};

function duration(seconds: number | null) {
  if (seconds == null) return "—";
  const minutes = Math.floor(seconds / 60);
  const rest = Math.round(seconds % 60);
  return minutes > 0 ? `${minutes} min ${rest} s` : `${rest} s`;
}

function percentText(value: number) {
  return `${value.toLocaleString("es-PE", { maximumFractionDigits: 1 })} %`;
}

function query(filters: Filters, questionnaireId: string) {
  const params = new URLSearchParams({ scope: filters.scope });
  for (const key of ["date_from", "date_to", "protocol", "audience"] as const) if (filters[key]) params.set(key, filters[key]);
  if (questionnaireId) params.set("questionnaire_id", questionnaireId);
  return `/statistics?${params.toString()}`;
}

/** Texto de una celda para pegar en Excel: sin tabulaciones ni saltos de línea. */
function cell(value: string | number) {
  return String(value).replace(/[\t\r\n]+/g, " ");
}

/** Estadísticas agregadas: cuentan sesiones, no personas, y se calculan en el servidor. */
export function StatisticsPage() {
  const { user } = useAuth();
  const isDocente = user?.role === "psychologist";
  const [draft, setDraft] = useState<Filters>(emptyFilters);
  const [applied, setApplied] = useState<Filters>(emptyFilters);
  const [questionnaireId, setQuestionnaireId] = useState("");
  const [copied, setCopied] = useState("");
  const result = useApiQuery<SessionStatistics>(query(applied, questionnaireId));
  const data = result.data && "sessions" in result.data ? result.data : null;

  function set<K extends keyof Filters>(key: K, value: Filters[K]) {
    setDraft((current) => ({ ...current, [key]: value }));
  }

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setCopied("");
    setApplied(draft);
  }

  function changeScope(scope: Scope) {
    setCopied(""); setQuestionnaireId("");
    setDraft((current) => ({ ...current, scope, protocol: "" }));
    setApplied((current) => ({ ...current, scope, protocol: "" }));
  }

  /** Los datos visibles, separados por tabulaciones. No se crea ningún archivo. */
  function tableText(stats: SessionStatistics) {
    const rows: (string | number)[][] = [
      [stats.notice],
      [],
      ["Sesiones", "Completadas", "Interrumpidas", "Duración promedio (s)"],
      [stats.sessions.total, stats.sessions.completed, stats.sessions.interrupted, stats.sessions.average_duration_seconds ?? ""],
      [],
      ["Expresión estimada", "Porcentaje de capturas", "Capturas", "Sesiones"],
      ...stats.expressions.rows.map((row) => [expectedExpressionNames[row.expression] ?? row.expression, row.percent, row.captures, row.sessions]),
      ["Capturas de buena calidad", stats.expressions.counted_captures],
      ["Capturas excluidas por calidad", stats.expressions.excluded_captures],
      ["Estímulos emocionales comparados", stats.coincidence.compared],
      ["Coincidió con la esperada", stats.coincidence.matched],
    ];
    if (stats.by_user) {
      rows.push([], ["Usuario", "Sesiones", "Completadas", "Interrumpidas"],
        ...stats.by_user.map((row) => [row.email, row.sessions, row.completed, row.interrupted]));
    }
    if (stats.questionnaire) {
      rows.push([], [`${stats.questionnaire.title} (versión ${stats.questionnaire.version})`, "Respuestas", stats.questionnaire.responses]);
      for (const question of stats.questionnaire.questions) {
        rows.push(["Pregunta", question.text, "Respondida", question.answered, "Sin responder", question.unanswered]);
        for (const item of question.counts ?? []) rows.push(["", item.label, item.count]);
      }
    }
    return rows.map((row) => row.map(cell).join("\t")).join("\n");
  }

  async function copy() {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(tableText(data));
      setCopied("Tabla copiada. Pégala en Excel u otra hoja de cálculo.");
    } catch {
      setCopied("No se pudo copiar. Selecciona la tabla y cópiala a mano.");
    }
  }

  return <section>
    <PageHeader title="Estadísticas"
      description={isDocente ? "Resumen de tus sesiones o de las de tu grupo." : "Resumen de las sesiones que condujiste."}
      actions={<Button variant="secondary" disabled={!data} onClick={() => { void copy(); }}>Copiar tabla</Button>} />
    <Callout variant="info" role="note">
      Estas estadísticas cuentan sesiones, no personas, y son estimaciones. No permiten sacar conclusiones sobre ninguna persona.
    </Callout>
    {copied && <Callout variant="success">{copied}</Callout>}

    {isDocente && <fieldset className="audience-choice stat-scope">
      <legend>¿Qué sesiones?</legend>
      {(["mine", "group"] as const).map((scope) => <label key={scope} className={`audience-option${applied.scope === scope ? " is-selected" : ""}`}>
        <input type="radio" name="statistics-scope" checked={applied.scope === scope} onChange={() => changeScope(scope)} />
        <strong>{scope === "mine" ? "Mis sesiones" : "Mi grupo"}</strong>
      </label>)}
    </fieldset>}

    <form className="filter-bar stat-filters" onSubmit={apply}>
      <label>Desde<input type="date" value={draft.date_from} onChange={(event) => set("date_from", event.target.value)} /></label>
      <label>Hasta<input type="date" value={draft.date_to} onChange={(event) => set("date_to", event.target.value)} /></label>
      <label>Protocolo<select value={draft.protocol} onChange={(event) => set("protocol", event.target.value)}>
        <option value="">Todos</option>
        <option value="none">Sin protocolo</option>
        {(data?.protocols ?? []).map((item) => <option key={item.family_id} value={item.family_id}>{item.name}</option>)}
      </select></label>
      <label>Público<select value={draft.audience} onChange={(event) => set("audience", event.target.value)}>
        <option value="">Todos</option>
        {Object.entries(audienceNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select></label>
      <Button variant="primary" type="submit">Aplicar filtros</Button>
    </form>

    <PageState {...result} empty={false} onRetry={result.reload} />
    {data && <>
      {data.few_sessions && <Callout variant="warning" role="note">Hay pocas sesiones para sacar conclusiones.</Callout>}

      <h2 className="stat-heading">Resumen</h2>
      <dl className="detail-grid stat-summary">
        <div><dt>Sesiones</dt><dd>{data.sessions.total}</dd></div>
        <div><dt>Completadas</dt><dd>{data.sessions.completed}</dd></div>
        <div><dt>Interrumpidas</dt><dd>{data.sessions.interrupted}</dd></div>
        <div><dt>Duración promedio de las completadas</dt><dd>{duration(data.sessions.average_duration_seconds)}</dd></div>
      </dl>
      {data.sessions.total > 0 && <BarChart label="Sesiones completadas e interrumpidas" max={data.sessions.total} rows={[
        { key: "completed", label: "Completadas", value: data.sessions.completed, valueText: String(data.sessions.completed),
          detail: `${data.sessions.completed} de ${data.sessions.total} sesiones` },
        { key: "interrupted", label: "Interrumpidas", value: data.sessions.interrupted, valueText: String(data.sessions.interrupted),
          detail: `${data.sessions.interrupted} de ${data.sessions.total} sesiones` },
      ]} />}

      <h2 className="stat-heading">Expresiones estimadas</h2>
      <p className="muted">
        Porcentaje de las {data.expressions.counted_captures} capturas de buena calidad. No cuentan {data.expressions.excluded_captures} capturas
        de mala calidad.
      </p>
      {data.expressions.counted_captures > 0 && <BarChart label="Porcentaje de capturas por expresión estimada" max={100}
        rows={[...data.expressions.rows].sort((a, b) => b.percent - a.percent).map((row) => ({
          key: row.expression, label: expectedExpressionNames[row.expression] ?? row.expression, value: row.percent,
          valueText: percentText(row.percent),
          detail: `${row.captures} ${row.captures === 1 ? "captura" : "capturas"} en ${row.sessions} ${row.sessions === 1 ? "sesión" : "sesiones"}`,
        }))} />}
      <details className="stat-table-view">
        <summary>Ver como tabla</summary>
        <div className="table-wrap"><table className="data-table stat-table">
        <thead><tr><th>Expresión estimada</th><th>Porcentaje</th><th>Capturas</th><th>Sesiones</th></tr></thead>
        <tbody>{data.expressions.rows.map((row) => <tr key={row.expression}>
          <td data-label="Expresión estimada">{expectedExpressionNames[row.expression] ?? row.expression}</td>
          <td data-label="Porcentaje" className="stat-number">{percentText(row.percent)}</td>
          <td data-label="Capturas">{row.captures}</td>
          <td data-label="Sesiones">{row.sessions}</td>
        </tr>)}</tbody>
        </table></div>
      </details>

      <h2 className="stat-heading">Coincidencia con la expresión esperada</h2>
      {data.coincidence.compared > 0 && <BarChart label="Estímulos emocionales en los que coincidió la expresión" max={data.coincidence.compared} rows={[
        { key: "matched", label: "Coincidió", value: data.coincidence.matched, valueText: `${data.coincidence.matched} de ${data.coincidence.compared}` },
      ]} />}
      <p>
        {data.coincidence.compared === 0
          ? "Ningún estímulo emocional tuvo una captura de buena calidad para comparar."
          : `En ${data.coincidence.matched} de ${data.coincidence.compared} estímulos emocionales la expresión estimada coincidió con la esperada.`}
      </p>

      {data.by_user && <>
        <h2 className="stat-heading">Totales por usuario</h2>
        {data.by_user.length === 0 ? <p className="muted">Tu grupo todavía no tiene usuarios.</p>
          : <div className="table-wrap"><table className="data-table">
            <thead><tr><th>Usuario</th><th>Sesiones</th><th>Completadas</th><th>Interrumpidas</th></tr></thead>
            <tbody>{data.by_user.map((row) => <tr key={row.email}>
              <td data-label="Usuario">{row.email}</td><td data-label="Sesiones">{row.sessions}</td>
              <td data-label="Completadas">{row.completed}</td><td data-label="Interrumpidas">{row.interrupted}</td>
            </tr>)}</tbody>
          </table></div>}
      </>}

      <h2 className="stat-heading">Cuestionarios</h2>
      {data.questionnaires.length === 0 ? <p className="muted">Ninguna de estas sesiones tiene cuestionarios respondidos.</p> : <>
        <div className="filter-bar">
          <label>Cuestionario y versión<select value={questionnaireId} onChange={(event) => { setCopied(""); setQuestionnaireId(event.target.value); }}>
            <option value="">Elige un cuestionario</option>
            {data.questionnaires.map((item) => <option key={item.id} value={item.id}>
              {item.title} · versión {item.version} · {item.responses} {item.responses === 1 ? "respuesta" : "respuestas"}
            </option>)}
          </select></label>
        </div>
        <p className="muted">Se cuenta cuántas veces se eligió cada opción o punto. No se suman ni se interpretan. Las respuestas de texto no se muestran.</p>
        {data.questionnaire && data.questionnaire.questions.map((question, index) => <article key={index} className="card stat-question">
          <h3>{question.text}</h3>
          <p className="muted">{kindNames[question.kind]} · {question.answered} {question.answered === 1 ? "respuesta" : "respuestas"} · {question.unanswered} sin responder
            {question.min_label && question.max_label ? ` · 1 = ${question.min_label}, ${question.counts?.length} = ${question.max_label}` : ""}</p>
          {question.counts ? <BarChart label={`Respuestas a «${question.text}»`} rows={question.counts.map((item) => ({
            key: item.label, label: item.label, value: item.count, valueText: String(item.count),
          }))} />
            : <p>Hubo {question.answered} {question.answered === 1 ? "respuesta de texto" : "respuestas de texto"}; su contenido no se muestra aquí.</p>}
        </article>)}
      </>}
    </>}
  </section>;
}
