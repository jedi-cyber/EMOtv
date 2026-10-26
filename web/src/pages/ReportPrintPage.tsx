import { useState } from "react";
import { useParams } from "react-router-dom";
import { apiRequest } from "../api/http";
import type { SessionReport } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button, ButtonLink } from "../components/Button";
import { Callout } from "../components/Callout";
import { PageState } from "../components/PageState";
import { useExpressionCatalog } from "../expressions/ExpressionCatalog";
import { ReportBody } from "../reports/ReportBody";
import { paths } from "../routes/paths";

/**
 * Vista imprimible del reporte aprobado. Imprime el navegador: el servidor no
 * genera archivos. Si la persona adulta o el tutor de un niño piden una
 * copia, el docente la imprime y se la entrega. Cada impresión queda en la auditoría.
 */
export function ReportPrintPage() {
  const { reportId = "" } = useParams();
  const { token } = useAuth();
  const { label: expressionLabel } = useExpressionCatalog();
  const query = useApiQuery<SessionReport>(`/reports/${encodeURIComponent(reportId)}`);
  const [error, setError] = useState("");
  const report = query.data;

  async function print() {
    setError("");
    try {
      // La impresión queda en la auditoría antes de abrir el diálogo del navegador.
      await apiRequest(`/reports/${encodeURIComponent(reportId)}/print`, { method: "POST", token });
      window.print();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo registrar la impresión."); }
  }

  return <section>
    <div className="inline-actions no-print">
      {report && <ButtonLink variant="ghost" to={paths.sessionReport(report.session.id)}>← Volver al reporte</ButtonLink>}
      {report?.status === "approved" && <Button variant="primary" onClick={() => { void print(); }}>Imprimir reporte</Button>}
    </div>
    {error && <Callout variant="error">{error}</Callout>}
    {report && report.status !== "approved" && <Callout variant="warning">Solo se imprime un reporte aprobado.</Callout>}
    <PageState {...query} onRetry={query.reload} />
    {report?.status === "approved" && <article className="report-print">
      <h1>Reporte de sesión</h1>
      <ReportBody report={report} expressionLabel={expressionLabel} printing />
      <p className="muted">EMOtv estima expresiones faciales; no diagnostica, no determina el estado psicológico de la persona y no sustituye a un profesional.</p>
      <p>Docente: ______________________________ Firma: ______________</p>
    </article>}
  </section>;
}
