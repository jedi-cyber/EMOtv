import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiRequest } from "../api/http";
import { useApiQuery } from "../api/useApiQuery";
import type { Student } from "../api/types";
import { useAuth } from "../auth/useAuth";
import { Alert } from "../components/Alert";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { paths } from "../routes/paths";

type Policy = { version: string | null; url: string | null; available: boolean };
type Consent = { id: string; policy_version: string; granted_at: string } | null;

export function ConsentPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const students = useApiQuery<Student[]>("/students");
  const student = students.data?.[0];
  const policy = useApiQuery<Policy>("/consent-policy");
  const active = useApiQuery<Consent>(student ? `/students/${encodeURIComponent(student.id)}/consents/active` : null);
  const [confirmed, setConfirmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function accept() {
    if (!token || !student || !policy.data?.available || !policy.data.version || !confirmed) return;
    setBusy(true); setError("");
    try {
      await apiRequest(`/students/${encodeURIComponent(student.id)}/consents`, {
        method: "POST", token,
        body: JSON.stringify({ policy_version: policy.data.version }),
      });
      setConfirmed(false);
      await active.reload();
      navigate(paths.analysis);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo registrar tu decisión."); }
    finally { setBusy(false); }
  }

  async function revoke() {
    if (!token || !student) return;
    setBusy(true); setError("");
    try {
      await apiRequest(`/students/${encodeURIComponent(student.id)}/consents/revoke`, { method: "POST", token });
      await active.reload();
      setNotice("Consentimiento revocado. No se iniciarán nuevos análisis.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo revocar el consentimiento."); }
    finally { setBusy(false); }
  }

  return <section>
    <PageHeader section="Tu privacidad" title="Consentimiento para el análisis facial"
      description="Tú decides si deseas usar el analizador. No aceptar no impide consultar las demás secciones." />
    {error && <Alert variant="error">{error}</Alert>}
    {notice && <Alert variant="info">{notice}</Alert>}
    <PageState {...students} onRetry={students.reload} />
    <PageState {...policy} onRetry={policy.reload} />
    {student && <PageState {...active} onRetry={active.reload} />}
    {!students.loading && !student && <p>No hay un perfil estudiantil asociado a tu cuenta. Contacta con administración.</p>}
    {active.data ? <div className="card onboarding-card">
      <h2>Consentimiento activo</h2>
      <p>Versión aceptada: {active.data.policy_version}</p>
      {policy.data?.available && policy.data.version !== active.data.policy_version &&
        <Alert variant="warning">La política vigente cambió. Revoca este consentimiento y revisa la nueva versión antes de volver a usar el analizador.</Alert>}
      <p>Registrado: {new Date(active.data.granted_at).toLocaleString("es-PE")}</p>
      <button className="button danger" disabled={busy} onClick={() => { void revoke(); }}>Revocar consentimiento</button>
    </div> : student && !active.loading && <div className="card onboarding-card">
      {!policy.data?.available ? <p>La institución aún no ha configurado una política aprobada. No es posible solicitar tu consentimiento por ahora.</p> : <>
        <p>Antes de decidir, lee la política institucional completa (versión {policy.data.version}). Describe qué datos se procesan, para qué se usan y cómo ejercer tus derechos.</p>
        <p><a href={policy.data.url ?? "#"} target="_blank" rel="noopener noreferrer">Leer política de consentimiento</a></p>
        <label className="checkbox"><input type="checkbox" checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)} />He leído la política y acepto el análisis facial descrito en ella.</label>
        <div className="inline-actions">
          <button className="button primary" disabled={!confirmed || busy} onClick={() => { void accept(); }}>Acepto y quiero usar el analizador</button>
          <Link className="button secondary" to={paths.dashboard}>No acepto por ahora</Link>
        </div>
      </>}
    </div>}
  </section>;
}
