import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, apiRequest } from "../api/http";
import type { ReportSection, ReportStatus, SessionReport } from "../api/types";
import { useAuth } from "../auth/useAuth";
import { Button, ButtonLink } from "../components/Button";
import { Callout } from "../components/Callout";
import { PageHeader } from "../components/PageHeader";
import { StatusChip } from "../components/StatusChip";
import type { StatusTone } from "../components/StatusChip";
import { useExpressionCatalog } from "../expressions/ExpressionCatalog";
import { ReportBody, sectionNames } from "../reports/ReportBody";
import { paths } from "../routes/paths";

const statusChips: Record<ReportStatus, [StatusTone, string]> = {
  draft: ["neutral", "Borrador"],
  submitted: ["progress", "Enviado a revisión"],
  changes_requested: ["progress", "Con observaciones"],
  approved: ["success", "Aprobado"],
};
const actionNames: Record<string, string> = {
  created: "Se creó", edited: "Se editó el texto", submitted: "Se envió a revisión", commented: "El docente comentó",
  returned: "Se devolvió con observaciones", approved: "El docente aprobó", closed: "Se cerró (aprobado)",
  new_version: "Se creó una versión nueva", printed: "Se imprimió",
};
const when = (value: string) => new Date(value).toLocaleString("es-PE", { dateStyle: "medium", timeStyle: "short" });

/** Reporte de una sesión con participante: redacción, revisión por secciones e historial. */
export function SessionReportPage() {
  const { sessionId = "" } = useParams();
  const { token } = useAuth();
  const { label: expressionLabel } = useExpressionCatalog();
  const [report, setReport] = useState<SessionReport | null>(null);
  const [missing, setMissing] = useState(false);
  const [narrative, setNarrative] = useState("");
  const [comments, setComments] = useState<Partial<Record<ReportSection, string>>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");

  function show(next: SessionReport) { setReport(next); setNarrative(next.narrative); setMissing(false); }

  useEffect(() => {
    apiRequest<SessionReport>(`/sessions/${encodeURIComponent(sessionId)}/report`, { token })
      .then(show)
      .catch((reason) => {
        if (reason instanceof ApiError && reason.status === 404) setMissing(true);
        else setError(reason instanceof Error ? reason.message : "No se pudo cargar el reporte.");
      });
  }, [sessionId, token]);

  async function act(path: string, method = "POST", body?: unknown, success = "") {
    setBusy(true); setError(""); setMessage("");
    try {
      show(await apiRequest<SessionReport>(path, { method, token, ...(body === undefined ? {} : { body: JSON.stringify(body) }) }));
      if (success) setMessage(success);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo completar la acción."); }
    finally { setBusy(false); }
  }

  const base = report ? `/reports/${encodeURIComponent(report.id)}` : "";
  const sectionComments = (section: ReportSection) => {
    const items = (report?.comments ?? []).filter((item) => item.section === section);
    return <div className="report-comments no-print">
      {items.map((item) => <Callout key={item.id} variant="warning"><strong>Comentario del docente:</strong> {item.text}</Callout>)}
      {report?.can_review && <form className="inline-actions" onSubmit={(event) => {
        event.preventDefault();
        void act(`${base}/comments`, "POST", { section, text: comments[section] ?? "" }).then(() => setComments({ ...comments, [section]: "" }));
      }}>
        <label>Comentario sobre {sectionNames[section].toLowerCase()}
          <input value={comments[section] ?? ""} maxLength={2000} onChange={(event) => setComments({ ...comments, [section]: event.target.value })} /></label>
        <Button type="submit" disabled={busy || !(comments[section] ?? "").trim()}>Comentar</Button>
      </form>}
    </div>;
  };

  return <section>
    <ButtonLink variant="ghost" className="back-link" to={paths.session(sessionId)}>← Detalle de la sesión</ButtonLink>
    <PageHeader title="Reporte de la sesión" description="Lo redacta quien condujo la sesión y lo revisa su docente. Describe lo registrado; no es una evaluación." />
    {error && <Callout variant="error">{error}</Callout>}
    {message && <Callout variant="success">{message}</Callout>}
    {missing && <div className="card form-stack">
      <p>Esta sesión todavía no tiene reporte.</p>
      <Button variant="primary" disabled={busy} onClick={() => { void act(`/sessions/${encodeURIComponent(sessionId)}/report`); }}>Redactar el reporte</Button>
    </div>}
    {report && <>
      <div className="inline-actions">
        <StatusChip tone={statusChips[report.status][0]}>{statusChips[report.status][1]}</StatusChip>
        {!report.current && <StatusChip tone="neutral">Versión reemplazada</StatusChip>}
        {report.requires_review === false && <span className="muted">Lo redactaste como docente: no requiere revisión.</span>}
      </div>
      {report.status === "approved" && <p className="muted">Un reporte aprobado no se edita. Si hay que corregirlo, crea una versión nueva: vuelve a revisión.</p>}
      <ReportBody report={report} expressionLabel={expressionLabel} renderSection={sectionComments}
        narrative={report.can_edit ? <div className="form-stack">
          <label htmlFor="report-narrative">Texto</label>
          <textarea id="report-narrative" rows={8} maxLength={8000} value={narrative} aria-describedby="report-narrative-help"
            onChange={(event) => setNarrative(event.target.value)} />
          <small id="report-narrative-help" className="muted">Se guarda cifrado. Describe lo que observaste; no diagnostiques ni etiquetes a la persona. No escribas nombres ni datos que la identifiquen.</small>
          <div className="inline-actions">
            <Button disabled={busy || narrative === report.narrative} onClick={() => { void act(base, "PUT", { narrative }, "Texto guardado."); }}>Guardar texto</Button>
            <Button variant="primary" disabled={busy || narrative !== report.narrative || !narrative.trim()}
              onClick={() => { void act(`${base}/submit`, "POST", undefined, report.requires_review ? "Reporte enviado a revisión." : "Reporte cerrado y aprobado."); }}>
              {report.requires_review ? "Enviar a revisión" : "Cerrar el reporte"}</Button>
          </div>
        </div> : undefined} />
      <section className="report-section no-print">
        <h2>{sectionNames.general}</h2>
        {sectionComments("general")}
        <div className="inline-actions">
          {report.can_review && <>
            <Button variant="primary" disabled={busy} onClick={() => { void act(`${base}/approve`, "POST", undefined, "Reporte aprobado."); }}>Aprobar</Button>
            <Button disabled={busy} onClick={() => { void act(`${base}/return`, "POST", undefined, "Reporte devuelto con observaciones."); }}>Devolver con observaciones</Button>
          </>}
          {report.can_new_version && <Button disabled={busy} onClick={() => { void act(`${base}/new-version`, "POST", undefined, "Se creó una versión nueva en borrador."); }}>Crear versión nueva</Button>}
          {report.status === "approved" && <ButtonLink variant="secondary" to={paths.reportPrint(report.id)}>Vista imprimible</ButtonLink>}
        </div>
      </section>
      {report.history && <section className="report-section no-print">
        <h2>Historial</h2>
        <ol className="timeline-events">{report.history.map((item, index) => <li key={index}>
          <span className="timeline-time">{when(item.occurred_at)}</span> {actionNames[item.action] ?? item.action}
          {item.version ? ` (versión ${item.version})` : ""}{item.by === "docente" && !["commented", "returned", "approved"].includes(item.action) ? " · docente" : ""}
        </li>)}</ol>
      </section>}
    </>}
  </section>;
}
