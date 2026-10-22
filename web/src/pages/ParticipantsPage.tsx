import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError, apiRequest } from "../api/http";
import type { AuthorizationStatus, DeletionCertificate, Participant, ParticipantKind } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import type { VersionedText } from "../commitment/CommitmentContext";
import { Button, ButtonLink } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Modal } from "../components/Modal";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { PolicyDocument } from "../components/PolicyDocument";
import { StatusChip } from "../components/StatusChip";
import type { StatusTone } from "../components/StatusChip";
import { AuthorizationsDialog } from "../participants/AuthorizationsDialog";
import { paths } from "../routes/paths";

const kindNames: Record<ParticipantKind, string> = { adult: "Adulto", child: "Niño o niña" };
const ADULT_AGE = 18;
const authorizationChips: Record<AuthorizationStatus, [StatusTone, string]> = {
  ready: ["success", "Autorizado"],
  missing: ["neutral", "Falta autorización"],
  revoked: ["error", "Autorización retirada"],
  no_age: ["neutral", "Sin edad registrada"],
};
const day = (value: string) => new Date(value).toLocaleDateString("es-PE", { dateStyle: "long" });

export function ParticipantsPage() {
  const { token, user } = useAuth();
  const isDocente = user?.role === "psychologist";
  const query = useApiQuery<Participant[]>("/participants");
  const expiringQuery = useApiQuery<Participant[]>(isDocente ? "/participants/expiring" : null);
  const certificatesQuery = useApiQuery<DeletionCertificate[]>("/participant-deletions");
  const items = query.data ?? [];
  const expiring = expiringQuery.data ?? [];
  const certificates = certificatesQuery.data ?? [];
  const [age, setAge] = useState("");
  const ageYears = Number.parseInt(age, 10);
  const validAge = Number.isInteger(ageYears) && ageYears >= 1 && ageYears <= 120;
  // La edad define el tipo: adulto desde los 18 años.
  const kind: ParticipantKind = validAge && ageYears < ADULT_AGE ? "child" : "adult";
  const [notes, setNotes] = useState("");
  const [authorizing, setAuthorizing] = useState<Participant | null>(null);
  const [notice, setNotice] = useState<VersionedText | null>(null);
  const [noticeRead, setNoticeRead] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [deleting, setDeleting] = useState<Participant | null>(null);
  const [certificate, setCertificate] = useState<DeletionCertificate | null>(null);

  async function reloadAll() {
    await Promise.all([query.reload(), isDocente ? expiringQuery.reload() : Promise.resolve(), certificatesQuery.reload()]);
  }

  async function register(childNoticeVersion?: string) {
    setBusy(true); setError(""); setMessage("");
    try {
      const created = await apiRequest<Participant>("/participants", {
        method: "POST", token,
        body: JSON.stringify({ kind, age_years: ageYears, notes: notes.trim() || null, ...(childNoticeVersion ? { child_notice_version: childNoticeVersion } : {}) }),
      });
      setMessage(`Participante registrado con el código ${created.code}. Anótalo en la ficha de papel junto a la persona; el sistema no puede recuperar esa relación. Antes de su primera sesión, registra su autorización firmada.`);
      setNotes(""); setAge(""); setNotice(null); setNoticeRead(false);
      await reloadAll();
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 428 && kind === "child" && !childNoticeVersion) {
        // Primer niño o niña: antes aparece el aviso reforzado sobre datos de menores.
        try { setNotice(await apiRequest<VersionedText>("/commitment/child-notice", { token })); }
        catch { setError("No se pudo cargar el aviso sobre datos de menores."); }
      } else {
        setError(reason instanceof Error ? reason.message : "No se pudo registrar al participante.");
      }
    } finally { setBusy(false); }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void register();
  }

  async function requestDeletion(item: Participant) {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiRequest(`/participants/${encodeURIComponent(item.id)}/deletion-request`, { method: "POST", token });
      setMessage(`Solicitaste la eliminación de ${item.code}. Tu docente la ejecutará.`);
      await reloadAll();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo solicitar la eliminación."); }
    finally { setBusy(false); }
  }

  async function executeDeletion(item: Participant) {
    setBusy(true); setError(""); setMessage("");
    try {
      setCertificate(await apiRequest<DeletionCertificate>(`/participants/${encodeURIComponent(item.id)}/delete`, { method: "POST", token }));
      await reloadAll();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo eliminar al participante."); }
    finally { setBusy(false); setDeleting(null); }
  }

  return <section>
    <PageHeader title="Participantes"
      description={isDocente
        ? "Participantes que registraste y los de los usuarios de tu grupo. Se identifican solo por un código: sin nombre, DNI ni foto."
        : "Participantes que registraste. Se identifican solo por un código: sin nombre, DNI ni foto."} />
    {message && <Callout variant="success">{message}</Callout>}
    {error && <Callout variant="error">{error}</Callout>}
    {certificate && <Callout variant="success">
      Se eliminó a {certificate.participant_code} con todos sus registros. Verificación: {certificate.verified ? "correcta, no quedó ningún registro" : "fallida"}.
      <ButtonLink variant="secondary" to={paths.deletionCertificate(certificate.id)}>Ver e imprimir el acta</ButtonLink>
    </Callout>}

    <form className="card form-stack" onSubmit={submit}>
      <h2>Registrar participante</h2>
      <p className="muted">Antes de cualquier sesión necesitas la autorización firmada en papel (propia, o del padre, la madre o el tutor si es un niño) y, con niños, su asentimiento.</p>
      <Callout variant="info" role="note">
        El sistema genera un código aleatorio que no se puede cambiar y guarda solo la edad: nunca el nombre, el DNI, una foto ni datos del tutor.
        La relación entre el código y la persona se anota en una ficha de papel que custodia el docente; el sistema no puede recuperarla.
      </Callout>
      <div className="form-field">
        <label htmlFor="participant-age">Edad en años</label>
        <input id="participant-age" type="number" min={1} max={120} required value={age} aria-describedby="participant-age-help"
          onChange={(event) => setAge(event.target.value)} />
        <small id="participant-age-help" className="muted">{validAge ? `Se registrará como: ${kindNames[kind].toLowerCase()}.` : "Adulto: 18 años o más."}</small>
      </div>
      <div className="form-field">
        <label htmlFor="participant-notes">Notas (opcional)</label>
        <textarea id="participant-notes" rows={3} maxLength={2000} value={notes} aria-describedby="participant-notes-help"
          onChange={(event) => setNotes(event.target.value)} />
        <small id="participant-notes-help" className="muted">Se guardan cifradas. No escribas nombres, DNI, colegios ni datos que permitan reconocer a la persona.</small>
      </div>
      <Button variant="primary" type="submit" disabled={busy || !validAge}>{busy ? "Registrando…" : "Registrar participante"}</Button>
    </form>

    {isDocente && items.some((item) => item.authorization_status === "revoked") && <Callout variant="warning">
      <strong>Autorización retirada:</strong> {items.filter((item) => item.authorization_status === "revoked").map((item) => item.code).join(", ")}.
      No pueden iniciar sesiones nuevas. Decide si los eliminas con el procedimiento de eliminación y acta.
    </Callout>}

    {isDocente && expiring.length > 0 && <Callout variant="warning">
      <strong>Por vencer en los próximos 30 días:</strong> {expiring.map((item) => `${item.code} (${day(item.expires_at)})`).join(", ")}.
      Al vencer se eliminan con todos sus registros. Decide si imprimes su reporte aprobado antes de esa fecha.
    </Callout>}

    <PageState {...query} empty={!query.loading && !query.error && items.length === 0}
      emptyMessage="Todavía no hay participantes registrados." onRetry={query.reload} />
    {items.length > 0 && <div className="table-wrap"><table><thead><tr>
      <th>Código</th><th>Tipo</th><th>Edad</th><th>Registro</th><th>Se elimina el</th>{isDocente && <th>Registrado por</th>}<th>Autorización</th><th>Estado</th><th><span className="sr-only">Acciones</span></th>
    </tr></thead><tbody>
      {items.map((item) => <tr key={item.id}>
        <td><strong>{item.code}</strong></td>
        <td>{kindNames[item.kind]}</td>
        <td>{item.age_years ?? <span className="muted">—</span>}</td>
        <td>{day(item.created_at)}</td>
        <td>{day(item.expires_at)}</td>
        {isDocente && <td>{item.registered_by_me ? "Tú" : "Usuario de tu grupo"}</td>}
        <td><StatusChip tone={authorizationChips[item.authorization_status][0]}>{authorizationChips[item.authorization_status][1]}</StatusChip></td>
        <td>{item.deletion_requested_at ? <StatusChip tone="progress">Eliminación solicitada</StatusChip> : <StatusChip tone="neutral">Vigente</StatusChip>}</td>
        <td className="inline-actions">
          <Button variant="secondary" type="button" disabled={busy} onClick={() => setAuthorizing(item)}>Autorizaciones</Button>
          <ButtonLink variant="ghost" to={paths.participantTrends(item.id)}>Tendencias</ButtonLink>
          {!isDocente && item.registered_by_me && !item.deletion_requested_at &&
            <Button variant="secondary" type="button" disabled={busy} onClick={() => { void requestDeletion(item); }}>Solicitar eliminación</Button>}
          {isDocente && <Button variant="danger" type="button" disabled={busy} onClick={() => setDeleting(item)}>Eliminar</Button>}
        </td>
      </tr>)}
    </tbody></table></div>}

    {certificates.length > 0 && <section className="card">
      <h2>Actas de eliminación</h2>
      <ul className="card-list">{certificates.map((item) => <li key={item.id} className="row-card">
        <span>{item.participant_code} · {day(item.deleted_at)}</span>
        <ButtonLink variant="secondary" to={paths.deletionCertificate(item.id)}>Ver acta</ButtonLink>
      </li>)}</ul>
    </section>}

    {authorizing && <AuthorizationsDialog participant={items.find((item) => item.id === authorizing.id) ?? authorizing} onClose={() => setAuthorizing(null)} onChanged={reloadAll} />}

    <ConfirmDialog open={deleting != null} title="Eliminar participante"
      message={`Se eliminará a ${deleting?.code ?? ""} con todas sus sesiones y registros. Se verificará que no quede nada y se generará un acta. No se puede deshacer.`}
      confirming={busy} confirmLabel="Eliminar definitivamente" onCancel={() => setDeleting(null)}
      onConfirm={() => { if (deleting) void executeDeletion(deleting); }} />

    {notice && <Modal open title="Antes de registrar a un niño o una niña" onClose={() => { setNotice(null); setNoticeRead(false); }} busy={busy}
      footer={<div className="inline-actions">
        <Button variant="secondary" disabled={busy} onClick={() => { setNotice(null); setNoticeRead(false); }}>Cancelar</Button>
        <Button variant="primary" disabled={!noticeRead || busy} onClick={() => { void register(notice.version); }}>Entendido, registrar</Button>
      </div>}>
      {notice.provisional && <Callout variant="warning" role="note">Texto provisional: pendiente de la revisión de la Facultad.</Callout>}
      <PolicyDocument content={notice.content} skipTitle />
      <Checkbox checked={noticeRead} onChange={(event) => setNoticeRead(event.target.checked)}>Entiendo que los datos de menores son más sensibles y cuento con la autorización y el asentimiento</Checkbox>
    </Modal>}
  </section>;
}
