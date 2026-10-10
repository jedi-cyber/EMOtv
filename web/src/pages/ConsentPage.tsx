import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../api/http";
import { useApiQuery } from "../api/useApiQuery";
import type { Student } from "../api/types";
import { useAuth } from "../auth/useAuth";
import { Callout } from "../components/Callout";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { paths } from "../routes/paths";
import { Button, ButtonAnchor, ButtonLink } from "../components/Button";
import { Checkbox } from "../components/Checkbox";

type Policy = { id?: string | null; code?: string | null; version: string | null;
  title?: string | null; content?: string | null; effective_at?: string | null; is_demo?: boolean;
  mode?: "development" | "demo" | "production"; url: string | null; available: boolean };
type Consent = { id: string; policy_version: string; granted_at: string } | null;

function formatDate(value: string): string {
  return new Date(value).toLocaleDateString("es-PE", { day: "2-digit", month: "long", year: "numeric" });
}

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
    if (!token || !student || !policy.data?.available || !(policy.data.id || policy.data.version) || !confirmed) return;
    setBusy(true); setError("");
    try {
      await apiRequest(`/students/${encodeURIComponent(student.id)}/consents`, {
        method: "POST", token,
        body: JSON.stringify({ policy_version: policy.data.id ?? policy.data.version }),
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
    <PageHeader title="Consentimiento para el análisis facial"
      description="Tú decides si deseas usar el analizador. No aceptar no impide consultar las demás secciones." />
    {error && <Callout variant="error">{error}</Callout>}
    {notice && <Callout variant="info">{notice}</Callout>}
    <PageState {...students} onRetry={students.reload} />
    <PageState {...policy} onRetry={policy.reload} />
    {student && <PageState {...active} onRetry={active.reload} />}
    {!students.loading && !student && <p>No hay un perfil estudiantil asociado a tu cuenta. Contacta con administración.</p>}
    {policy.data?.available && <div className="card onboarding-card" aria-label="Política vigente">
      <h2>Política vigente</h2>
      <p>{policy.data.code ?? "Política"} · versión {policy.data.version}
        {policy.data.effective_at && <> · vigente desde el {formatDate(policy.data.effective_at)}</>}</p>
      {active.data
        ? <p>Puedes retirar tu participación cuando quieras: <ButtonAnchor variant="ghost" href="#revocar">Revocar mi consentimiento</ButtonAnchor></p>
        : <p>No tienes un consentimiento activo. Si lo aceptas, podrás revocarlo desde esta página en cualquier momento.</p>}
    </div>}
    {active.data ? <div className="card onboarding-card" id="revocar">
      <h2>Consentimiento activo</h2>
      <p>Versión aceptada: {active.data.policy_version}</p>
      {policy.data?.available && (policy.data.id ?? policy.data.version) !== active.data.policy_version &&
        <Callout variant="warning">La política vigente cambió. Lee y acepta la nueva versión para volver a usar el analizador.</Callout>}
      <p>Registrado: {new Date(active.data.granted_at).toLocaleString("es-PE")}</p>
      <Button variant="danger" type="submit" disabled={busy} onClick={() => { void revoke(); }}>Revocar consentimiento</Button>
    </div> : null}
    {student && !active.loading && (!active.data || (policy.data?.available && (policy.data.id ?? policy.data.version) !== active.data.policy_version)) && <div className="card onboarding-card">
      {!policy.data?.available ? <>
        <p>{policy.data?.mode === "development" ? "Modo técnico de desarrollo: el consentimiento no bloquea el analizador. No uses este modo con personas reales." : "No hay una política activa. No es posible solicitar tu consentimiento por ahora."}</p>
        {policy.data?.mode === "development" && <ButtonLink variant="secondary" to={paths.analysis}>Ir al analizador</ButtonLink>}
      </> : <>
        <p>{policy.data.is_demo ? "POLÍTICA PROVISIONAL DE DEMOSTRACIÓN: no está aprobada para despliegue institucional." : "Política institucional activa"} · {policy.data.code ?? ""} {policy.data.version}</p>
        <h3>{policy.data.title}</h3>
        {policy.data.content && <pre className="consent-document">{policy.data.content}</pre>}
        {!policy.data.content && policy.data.url && <p><ButtonAnchor variant="secondary" href={policy.data.url} target="_blank" rel="noopener noreferrer">Leer política de consentimiento</ButtonAnchor></p>}
        <Checkbox checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)}>He leído la política y acepto el análisis facial descrito en ella.</Checkbox>
        <div className="inline-actions">
          <Button variant="primary" type="submit" disabled={!confirmed || busy} onClick={() => { void accept(); }}>{active.data ? "Acepto la nueva versión" : "Acepto y quiero usar el analizador"}</Button>
          <ButtonLink variant="secondary" to={paths.dashboard}>No acepto por ahora</ButtonLink>
        </div>
      </>}
    </div>}
  </section>;
}
