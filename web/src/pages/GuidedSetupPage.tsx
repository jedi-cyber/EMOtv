import { useState } from "react";
import type { FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest } from "../api/http";
import type { EmotionalSession, Participant, Protocol, SessionType } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { PageHeader } from "../components/PageHeader";
import { storeViewToken } from "../guided/viewToken";
import { paths } from "../routes/paths";

const typeNames: Record<SessionType, string> = {
  propia: "Sesión propia",
  participante_adulto: "Con un participante adulto",
  participante_infantil: "Con un participante niño o niña",
};

/** Preparar una sesión guiada: tipo, participante y protocolo. */
export function GuidedSetupPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const participantsQuery = useApiQuery<Participant[]>("/participants");
  const protocolsQuery = useApiQuery<Protocol[]>("/protocols");
  const [type, setType] = useState<SessionType>("propia");
  const [participantId, setParticipantId] = useState("");
  const [protocolId, setProtocolId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const kind = type === "participante_infantil" ? "child" : type === "participante_adulto" ? "adult" : null;
  // Solo quien registró al participante conduce sus sesiones, y con autorización vigente.
  const participants = (participantsQuery.data ?? []).filter((item) => item.kind === kind && item.registered_by_me
    && item.authorization_status === "ready");
  const protocols = (protocolsQuery.data ?? []).filter((item) => item.owned_by_me
    && (kind !== "child" || (item.for_children && item.approved)));
  const ready = protocolId && (kind === null || participantId);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      const session = await apiRequest<EmotionalSession>("/sessions", { method: "POST", token, body: JSON.stringify({
        session_type: type, protocol_id: protocolId, ...(kind ? { participant_id: participantId } : {}),
      }) });
      const created = await apiRequest<{ view_token: string }>(`/guided-sessions/${encodeURIComponent(session.id)}`, { method: "POST", token });
      storeViewToken(session.id, created.view_token);
      navigate(paths.guidedSession(session.id));
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo preparar la sesión."); }
    finally { setBusy(false); }
  }

  return <section>
    <PageHeader title="Sesión guiada"
      description="Confirmación, cuestionario previo, calibración y los estímulos de un protocolo, con marcadores de quien conduce la sesión." />
    {error && <Callout variant="error">{error}</Callout>}
    <form className="card form-stack" onSubmit={(event) => { void submit(event); }}>
      <label>Tipo de sesión<select value={type} onChange={(event) => { setType(event.target.value as SessionType); setParticipantId(""); setProtocolId(""); }}>
        {(Object.keys(typeNames) as SessionType[]).map((value) => <option key={value} value={value}>{typeNames[value]}</option>)}
      </select></label>
      {kind && <label>Participante<select value={participantId} required onChange={(event) => setParticipantId(event.target.value)}>
        <option value="">Elige un participante</option>
        {participants.map((item) => <option key={item.id} value={item.id}>{item.code} · {item.age_years} años</option>)}
      </select></label>}
      {kind && participants.length === 0 && <p className="muted">No hay participantes de este tipo con su autorización firmada registrada. Regístrala en Participantes.</p>}
      <label>Protocolo<select value={protocolId} required onChange={(event) => setProtocolId(event.target.value)}>
        <option value="">Elige un protocolo</option>
        {protocols.map((item) => <option key={item.id} value={item.id}>{item.name} (versión {item.version})</option>)}
      </select></label>
      {kind === "child" && <p className="muted">Con niños solo aparecen los protocolos aprobados por tu docente.</p>}
      <Button variant="primary" type="submit" disabled={busy || !ready}>{busy ? "Preparando…" : "Preparar sesión"}</Button>
    </form>
  </section>;
}
