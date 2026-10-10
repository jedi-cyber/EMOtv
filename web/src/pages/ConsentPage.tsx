import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../api/http";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button, ButtonAnchor, ButtonLink } from "../components/Button";
import { Callout } from "../components/Callout";
import { CardWithHeader } from "../components/Card";
import { Checkbox } from "../components/Checkbox";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Modal } from "../components/Modal";
import { NavIcon } from "../components/NavIcon";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { PolicyDocument } from "../components/PolicyDocument";
import { StatusChip } from "../components/StatusChip";
import { formatLongDate, policyKey, useConsentStatus, versionLabel, type ConsentRecord } from "../consent/useConsentStatus";
import { paths } from "../routes/paths";

const REVOKE_MESSAGE = "Si lo revocas, no podrás iniciar nuevos análisis faciales hasta que vuelvas a aceptar la política. "
  + "Tus sesiones ya registradas se conservan y puedes seguir consultando las demás secciones.";

export function ConsentPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const consent = useConsentStatus();
  const { policy, student, active, state } = consent;
  const history = useApiQuery<ConsentRecord[]>(student ? `/students/${encodeURIComponent(student.id)}/consents` : null);
  const [reading, setReading] = useState<"read" | "accept" | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [revoking, setRevoking] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  const accepted = state === "active";
  const canAccept = Boolean(student && policy?.available && !accepted);
  const previous = (history.data ?? []).filter((item) => item.id !== active?.id);
  const lastRevoked = previous.find((item) => item.revoked_at);

  function openPolicy(mode: "read" | "accept") { setConfirmed(false); setReading(mode); }

  async function accept() {
    if (!token || !student || !policy?.available || !confirmed) return;
    setBusy(true); setError("");
    try {
      await apiRequest(`/students/${encodeURIComponent(student.id)}/consents`, {
        method: "POST", token, body: JSON.stringify({ policy_version: policyKey(policy) }),
      });
      setReading(null);
      await consent.reload();
      navigate(paths.analysis);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo registrar tu decisión."); }
    finally { setBusy(false); }
  }

  async function revoke() {
    if (!token || !student) return;
    setBusy(true); setError("");
    try {
      await apiRequest(`/students/${encodeURIComponent(student.id)}/consents/revoke`, { method: "POST", token });
      setRevoking(false);
      await Promise.all([consent.reload(), history.reload()]);
      setNotice("Consentimiento revocado. No se iniciarán nuevos análisis.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo revocar el consentimiento."); setRevoking(false); }
    finally { setBusy(false); }
  }

  const consentChip = state === "active" ? <StatusChip tone="success">Activo</StatusChip>
    : state === "outdated" ? <StatusChip tone="progress">Desactualizado</StatusChip>
      : lastRevoked ? <StatusChip tone="neutral">Revocado</StatusChip>
        : <StatusChip tone="neutral">Sin aceptar</StatusChip>;

  return <section>
    <PageHeader title="Consentimiento"
      description="Tú decides si deseas usar el analizador. No aceptar no impide consultar las demás secciones." />
    {error && <Callout variant="error">{error}</Callout>}
    {notice && <Callout variant="success">{notice}</Callout>}
    {state === "loading" && <PageState loading error="" onRetry={() => undefined} />}
    {state === "error" && <PageState loading={false} error={consent.error} onRetry={consent.reload} />}
    {state === "no_student" && <Callout variant="warning">No hay un perfil estudiantil asociado a tu cuenta. Contacta con administración.</Callout>}
    {state === "not_required" && <Callout variant="info">
      <p>Modo técnico de desarrollo: el consentimiento no bloquea el analizador. No uses este modo con personas reales.</p>
      <div className="inline-actions"><ButtonLink variant="secondary" to={paths.analysis}>Ir al analizador</ButtonLink></div>
    </Callout>}
    {state === "unavailable" && <Callout variant="warning">No hay una política activa. No es posible solicitar tu consentimiento por ahora.</Callout>}
    {state === "outdated" && <Callout variant="warning">
      <p>La política vigente cambió. Lee y acepta la nueva versión para volver a usar el analizador.</p>
      <div className="inline-actions"><Button variant="secondary" onClick={() => openPolicy("accept")}>Leer y aceptar</Button></div>
    </Callout>}

    {policy?.available && student && <div className="card-grid">
      <CardWithHeader icon={<NavIcon name="document" />} badge={versionLabel(policy.version)} title="Política de análisis facial"
        meta={policy.effective_at ? `Vigente desde el ${formatLongDate(policy.effective_at)}` : undefined}
        status={accepted ? <StatusChip tone="success">Aceptada</StatusChip> : <StatusChip tone="progress">Pendiente de aceptar</StatusChip>}
        actions={accepted || !canAccept
          ? <Button variant="secondary" onClick={() => openPolicy("read")}>Leer política</Button>
          : <Button variant="primary" onClick={() => openPolicy("accept")}>Leer y aceptar</Button>} />
      <CardWithHeader icon={<NavIcon name="shield" />} title="Tu consentimiento"
        meta={active ? `Aceptado el ${formatLongDate(active.granted_at)}`
          : lastRevoked?.revoked_at ? `Revocado el ${formatLongDate(lastRevoked.revoked_at)}` : "Todavía no lo has aceptado"}
        status={consentChip}
        actions={active ? <Button variant="danger" onClick={() => setRevoking(true)}>Revocar consentimiento</Button> : undefined} />
      {previous.length > 0 && <CardWithHeader icon={<NavIcon name="sessions" />} title="Versiones anteriores"
        badge={previous.length === 1 ? "1 registro" : `${previous.length} registros`}>
        <ul className="consent-history">{previous.map((item) => <li key={item.id}>
          <strong>{versionLabel(item.policy_version)}</strong>
          <span>Aceptada el {formatLongDate(item.granted_at)}{item.revoked_at ? ` · revocada el ${formatLongDate(item.revoked_at)}` : ""}</span>
        </li>)}</ul>
      </CardWithHeader>}
    </div>}

    {policy && <Modal open={reading != null} title={policy.title ?? "Política de análisis facial"} onClose={() => setReading(null)} busy={busy}
      footer={reading === "accept" && canAccept ? <div className="consent-footer">
        <Checkbox checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)}>He leído la política y acepto el análisis facial descrito en ella.</Checkbox>
        {!confirmed && <p className="consent-footer-hint">Marca la casilla para continuar</p>}
        <div className="consent-footer-actions">
          <Button variant="secondary" disabled={busy} onClick={() => setReading(null)}>Ahora no</Button>
          <Button variant="primary" disabled={!confirmed} loading={busy} onClick={() => { void accept(); }}>Aceptar la política</Button>
        </div>
      </div> : <Button variant="secondary" onClick={() => setReading(null)}>Cerrar</Button>}>
      {policy.is_demo && <Callout variant="warning" role="note">Política provisional de demostración: no está aprobada para despliegue institucional.</Callout>}
      {policy.content ? <PolicyDocument content={policy.content} skipTitle />
        : policy.url && <p><ButtonAnchor variant="secondary" href={policy.url} target="_blank" rel="noopener noreferrer">Leer política de consentimiento</ButtonAnchor></p>}
      <p className="technical-id">Identificador: {policyKey(policy)}{policy.effective_at && ` · vigente desde el ${formatLongDate(policy.effective_at)}`}</p>
    </Modal>}
    <ConfirmDialog open={revoking} title="Revocar consentimiento" message={REVOKE_MESSAGE} confirming={busy}
      confirmLabel="Revocar" onCancel={() => setRevoking(false)} onConfirm={() => { void revoke(); }} />
  </section>;
}
