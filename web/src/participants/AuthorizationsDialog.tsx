import { useState } from "react";
import { apiRequest } from "../api/http";
import type { Participant, ParticipantAuthorization } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { Modal } from "../components/Modal";
import { StatusChip } from "../components/StatusChip";

const scopeNames = { participation: "la participación", camera: "el uso de la cámara", assent: "el asentimiento" } as const;
const day = (value: string) => new Date(value.length === 10 ? `${value}T12:00:00` : value).toLocaleDateString("es-PE", { dateStyle: "long" });
const today = () => new Date().toISOString().slice(0, 10);

type Scope = keyof typeof scopeNames;
type Party = "participant" | "guardian";

/** Registra el formato firmado en papel y los retiros. Ninguna casilla viene marcada. */
export function AuthorizationsDialog({ participant, onClose, onChanged }: {
  participant: Participant;
  onClose: () => void;
  onChanged: () => Promise<unknown>;
}) {
  const { token } = useAuth();
  const path = `/participants/${encodeURIComponent(participant.id)}/authorizations`;
  const query = useApiQuery<ParticipantAuthorization[]>(path);
  const items = query.data ?? [];
  const child = participant.kind === "child";
  const revoked = participant.authorization_status === "revoked";
  const [formVersion, setFormVersion] = useState("");
  const [signedOn, setSignedOn] = useState(today());
  const [participation, setParticipation] = useState(false);
  const [camera, setCamera] = useState(false);
  const [assent, setAssent] = useState(false);
  const [revoking, setRevoking] = useState<ParticipantAuthorization | null>(null);
  const [party, setParty] = useState<Party>(child ? "guardian" : "participant");
  const [scope, setScope] = useState<Scope>("participation");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function run(action: () => Promise<unknown>) {
    setBusy(true); setError("");
    try {
      await action();
      await Promise.all([query.reload(), onChanged()]);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo guardar."); }
    finally { setBusy(false); }
  }

  function record() {
    void run(async () => {
      await apiRequest(path, { method: "POST", token, body: JSON.stringify({
        form_version: formVersion.trim(), signed_on: signedOn, participation, camera, ...(child ? { child_assent: assent } : {}),
      }) });
      setFormVersion(""); setParticipation(false); setCamera(false); setAssent(false);
    });
  }

  function revoke(item: ParticipantAuthorization) {
    void run(async () => {
      await apiRequest(`${path}/${encodeURIComponent(item.id)}/revoke`, { method: "POST", token, body: JSON.stringify({ party, scope }) });
      setRevoking(null);
    });
  }

  return <Modal open title={`Autorizaciones de ${participant.code}`} onClose={onClose} busy={busy}
    footer={<div className="inline-actions"><Button onClick={onClose} disabled={busy}>Cerrar</Button></div>}>
    <p className="muted">
      Registra aquí el formato firmado en papel. {child
        ? "Lo firma el padre, la madre o el tutor; además se registra el asentimiento del niño o la niña, explicado de acuerdo con su edad."
        : "Lo firma el propio participante."} No se guardan nombres ni datos de quien firma.
    </p>
    {error && <Callout variant="error">{error}</Callout>}
    {revoked && <Callout variant="warning">
      Se retiró una autorización: no se pueden iniciar sesiones nuevas ni registrar otra autorización. El docente decide su eliminación.
    </Callout>}

    {!revoked && <div className="form-stack">
      <label>Versión del formato<input value={formVersion} maxLength={64} required onChange={(event) => setFormVersion(event.target.value)} /></label>
      <label>Fecha de la firma<input type="date" value={signedOn} max={today()} onChange={(event) => setSignedOn(event.target.value)} /></label>
      <Checkbox checked={participation} onChange={(event) => setParticipation(event.target.checked)}>
        (a) Autoriza la participación y el registro de la expresión estimada
      </Checkbox>
      <Checkbox checked={camera} onChange={(event) => setCamera(event.target.checked)}>(b) Autoriza el uso de la cámara</Checkbox>
      {child && <Checkbox checked={assent} onChange={(event) => setAssent(event.target.checked)}>
        El niño o la niña dio su asentimiento
      </Checkbox>}
      <Button variant="primary" disabled={busy || !formVersion.trim() || !signedOn} onClick={record}>Registrar autorización</Button>
    </div>}

    <h3>Historial</h3>
    {!query.loading && items.length === 0 && <p className="muted">Todavía no hay autorizaciones registradas.</p>}
    <ul className="card-list">{items.map((item) => <li key={item.id} className="row-card">
      <div>
        <strong>Formato {item.form_version} · firmado el {day(item.signed_on)}</strong>
        <span>
          Participación: {item.participation ? "sí" : "no"} · Cámara: {item.camera ? "sí" : "no"}
          {item.child_assent !== null && ` · Asentimiento: ${item.child_assent ? "sí" : "no"}`}
        </span>
        {item.revoked_at
          ? <StatusChip tone="neutral">Retirada el {day(item.revoked_at)}: {scopeNames[item.revoked_scope ?? "participation"]}</StatusChip>
          : null}
      </div>
      {!item.revoked_at && <Button variant="danger" size="sm" disabled={busy} onClick={() => setRevoking(item)}>Registrar retiro</Button>}
    </li>)}</ul>

    {revoking && <div className="card form-stack">
      <h3>Registrar retiro</h3>
      <p className="muted">Se bloquean las sesiones nuevas y el participante queda marcado para que el docente decida su eliminación.</p>
      {child && <label>Quién lo retira<select value={party} onChange={(event) => setParty(event.target.value as Party)}>
        <option value="guardian">El padre, la madre o el tutor</option>
        <option value="participant">El niño o la niña</option>
      </select></label>}
      <label>Qué se retira<select value={scope} onChange={(event) => setScope(event.target.value as Scope)}>
        <option value="participation">La participación y el registro de la expresión estimada</option>
        <option value="camera">El uso de la cámara</option>
        {child && <option value="assent">El asentimiento</option>}
      </select></label>
      <div className="inline-actions">
        <Button onClick={() => setRevoking(null)} disabled={busy}>Cancelar</Button>
        <Button variant="danger" disabled={busy} onClick={() => revoke(revoking)}>Confirmar retiro</Button>
      </div>
    </div>}
  </Modal>;
}
