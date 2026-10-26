import { useState } from "react";
import { useParams } from "react-router-dom";
import { apiRequest } from "../api/http";
import type { DeletionCertificate } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button, ButtonLink } from "../components/Button";
import { Callout } from "../components/Callout";
import { PageState } from "../components/PageState";
import { paths } from "../routes/paths";

/** Nombres de los tipos de registro; la clave técnica nunca se muestra. */
const recordNames: Record<string, string> = {
  sessions: "Sesión",
  questionnaire_responses: "Respuestas de cuestionarios", expression_captures: "Capturas de expresión estimada",
  session_markers: "Marcadores", verbal_responses: "Lo que dijo ver en imágenes abstractas",
  guided_runs: "Avance del protocolo", session_reports: "Reportes", report_comments: "Comentarios de reportes",
  report_events: "Historial de reportes",
};
const when = (value: string) => new Date(value).toLocaleString("es-PE", { dateStyle: "long", timeStyle: "short" });

/** Acta imprimible: código, fecha, registros por tipo y verificación. Sin datos personales. */
export function DeletionCertificatePage() {
  const { certificateId = "" } = useParams();
  const { token } = useAuth();
  const query = useApiQuery<DeletionCertificate>(`/session-deletions/${encodeURIComponent(certificateId)}`);
  const [error, setError] = useState("");
  const certificate = query.data;

  async function print() {
    setError("");
    try {
      // La impresión queda en la auditoría antes de abrir el diálogo del navegador.
      await apiRequest(`/session-deletions/${encodeURIComponent(certificateId)}/print`, { method: "POST", token });
      window.print();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo registrar la impresión."); }
  }

  return <section>
    <div className="inline-actions no-print">
      <ButtonLink variant="ghost" to={paths.sessions}>← Volver a sesiones</ButtonLink>
      {certificate && <Button variant="primary" onClick={() => { void print(); }}>Imprimir acta</Button>}
    </div>
    {error && <Callout variant="error">{error}</Callout>}
    <PageState {...query} onRetry={query.reload} />
    {certificate && <article className="card">
      <h1>Acta de eliminación de una sesión</h1>
      <dl className="detail-grid">
        <div><dt>Código de la sesión</dt><dd>{certificate.session_code}</dd></div>
        <div><dt>Fecha y hora</dt><dd>{when(certificate.deleted_at)}</dd></div>
        <div><dt>Verificación</dt><dd>{certificate.verified ? "Correcta: no quedó ningún registro asociado" : "Fallida"}</dd></div>
      </dl>
      <h2>Registros eliminados por tipo</h2>
      <ul>{Object.entries(certificate.counts).map(([key, value]) => <li key={key}>{recordNames[key] ?? "Otros registros"}: {value}</li>)}</ul>
      <p className="muted">El acta no contiene datos personales. EMOtv no guarda imágenes de las personas evaluadas.</p>
      <p>Responsable: ______________________________ Firma: ______________</p>
    </article>}
  </section>;
}
