import { useState } from "react";
import { apiRequest } from "../api/http";
import type { ImageAudience, ImageReview, UserImage } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { Modal } from "../components/Modal";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip } from "../components/StatusChip";
import { StimulusImage } from "../components/StimulusImage";
import { audienceNames } from "../stimuli/labels";

type Decision = ImageAudience | "delete";

const decisionNames: Record<Decision, string> = { ...audienceNames, delete: "Eliminar" };
const PERSON_HINT = "Si ves a una persona, elimina la imagen.";

function formatDate(value: string) {
  return new Date(value).toLocaleDateString("es-PE", { day: "numeric", month: "long", year: "numeric" });
}

function fileOf(id: string, preview = false) {
  return `/own-stimuli/${encodeURIComponent(id)}/file${preview ? "?preview=true" : ""}`;
}

/** Revisión del docente: imágenes que subieron los usuarios de su grupo. Una imagen sin aprobar no se usa. */
export function ImageReviewPage() {
  const { token } = useAuth();
  const query = useApiQuery<ImageReview>("/own-stimuli/review");
  const pending = query.data?.pending ?? [];
  const approved = query.data?.approved ?? [];
  // Decisión elegida por imagen; sin elegir, la respuesta del usuario (o la clasificación actual).
  const [choices, setChoices] = useState<Record<string, Decision>>({});
  const [selected, setSelected] = useState<string[]>([]);
  const [enlarged, setEnlarged] = useState<UserImage | null>(null);
  const [confirming, setConfirming] = useState(false);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const all = [...pending.flatMap((batch) => batch.images), ...approved];
  const chosen = all.filter((item) => selected.includes(item.id));
  const decisionOf = (item: UserImage): Decision => choices[item.id] ?? item.audience;
  const deleting = chosen.filter((item) => decisionOf(item) === "delete").length;

  function toggle(ids: string[], on: boolean) {
    setSelected((current) => on ? [...new Set([...current, ...ids])] : current.filter((id) => !ids.includes(id)));
  }

  async function apply() {
    setBusy(true); setError(""); setMessage("");
    const groups = new Map<Decision, string[]>();
    for (const item of chosen) groups.set(decisionOf(item), [...(groups.get(decisionOf(item)) ?? []), item.id]);
    try {
      for (const [decision, ids] of groups) {
        await apiRequest("/own-stimuli/review", { method: "POST", token, body: JSON.stringify({
          image_ids: ids, decision, reason: decision === "delete" ? reason.trim() || null : null,
        }) });
      }
      setMessage(chosen.length === 1 ? "Se aplicó la decisión." : `Se aplicaron las decisiones a ${chosen.length} imágenes.`);
      setSelected([]); setChoices({}); setReason(""); setConfirming(false);
    } catch (failure) { setError(failure instanceof Error ? failure.message : "No se pudo aplicar la decisión."); }
    finally { setBusy(false); await query.reload(); }
  }

  function card(item: UserImage) {
    const decision = decisionOf(item);
    return <li key={item.id} className="card review-card">
      <Checkbox checked={selected.includes(item.id)} onChange={(event) => toggle([item.id], event.target.checked)}>
        Seleccionar «{item.title}»
      </Checkbox>
      <button type="button" className="review-preview" onClick={() => setEnlarged(item)} aria-label={`Ampliar «${item.title}»`}>
        <StimulusImage id={item.id} alt={item.title} path={fileOf(item.id)} className="review-thumb" />
      </button>
      <p className="review-hint">{PERSON_HINT}</p>
      <div className="review-meta">
        <strong>{item.title}</strong>
        <span>Origen: {item.origin}</span>
        <span className="inline-actions">
          {item.status === "approved" && <StatusChip tone="success">Aprobada · {audienceNames[item.audience]}</StatusChip>}
          {item.status === "pending" && <StatusChip tone="neutral">El usuario eligió: {audienceNames[item.audience]}</StatusChip>}
          {item.possible_person && <StatusChip tone="error">Revisar: posible persona</StatusChip>}
        </span>
      </div>
      <fieldset className="review-decision">
        <legend>Decisión</legend>
        {(["children", "adults", "delete"] as const).map((option) => <label key={option}
          className={`audience-option${decision === option ? " is-selected" : ""}`}>
          <input type="radio" name={`decision-${item.id}`} checked={decision === option}
            onChange={() => { setChoices((current) => ({ ...current, [item.id]: option })); toggle([item.id], true); }} />
          <strong>{decisionNames[option]}</strong>
        </label>)}
      </fieldset>
    </li>;
  }

  return <section>
    <PageHeader title="Imágenes por revisar"
      description="Imágenes que subieron los usuarios de tu grupo. Solo se usan en sus protocolos cuando las apruebas."
      actions={<Button variant="primary" disabled={busy || chosen.length === 0}
        onClick={() => { if (deleting > 0) setConfirming(true); else void apply(); }}>
        {chosen.length > 0 ? `Aplicar a ${chosen.length} ${chosen.length === 1 ? "imagen" : "imágenes"}` : "Aplicar a las seleccionadas"}
      </Button>} />
    <Callout variant="info" role="note">
      El sistema rechaza las imágenes que parecen mostrar a una persona, pero esa detección automática puede equivocarse.
      {" "}{PERSON_HINT} «Para niños» sirve en protocolos para niños y para adultos; «Para adultos», solo para adultos.
    </Callout>
    {message && <Callout variant="success">{message}</Callout>}
    {error && <Callout variant="error">{error}</Callout>}

    <PageState {...query} empty={!query.loading && !query.error && pending.length === 0 && approved.length === 0}
      emptyMessage="No hay imágenes de tu grupo por revisar." onRetry={query.reload} />

    {pending.map((batch) => {
      const ids = batch.images.map((item) => item.id);
      const allSelected = ids.every((id) => selected.includes(id));
      return <section key={batch.batch_id} className="review-batch" aria-label={`Lote de ${batch.uploaded_by}`}>
        <header className="review-batch-head">
          <h2>{batch.uploaded_by} · {formatDate(batch.uploaded_at)}</h2>
          <Checkbox checked={allSelected} onChange={(event) => toggle(ids, event.target.checked)}>
            Seleccionar las {ids.length} del lote
          </Checkbox>
        </header>
        <ul className="review-grid">{batch.images.map(card)}</ul>
      </section>;
    })}

    {approved.length > 0 && <section className="review-batch">
      <header className="review-batch-head">
        <h2>Aprobadas</h2>
        <p className="muted">Si cambias para quién es o eliminas una imagen que un protocolo usa, ese protocolo queda «Necesita una imagen» y su dueño recibe un aviso.</p>
      </header>
      <ul className="review-grid">{approved.map(card)}</ul>
    </section>}

    <Modal open={enlarged !== null} title={enlarged?.title ?? ""} onClose={() => setEnlarged(null)}
      footer={<Button onClick={() => setEnlarged(null)}>Cerrar</Button>}>
      {enlarged && <>
        <StimulusImage id={enlarged.id} alt={enlarged.title} path={fileOf(enlarged.id, true)} className="review-large" />
        <p className="review-hint">{PERSON_HINT}</p>
      </>}
    </Modal>

    <Modal open={confirming} title="Eliminar imágenes" onClose={() => setConfirming(false)} busy={busy}
      footer={<>
        <Button disabled={busy} onClick={() => setConfirming(false)}>Cancelar</Button>
        <Button variant="danger" disabled={busy} onClick={() => { void apply(); }}>{busy ? "Aplicando…" : "Eliminar y aplicar"}</Button>
      </>}>
      <p>Se eliminarán {deleting === 1 ? "1 imagen" : `${deleting} imágenes`}: se borra el archivo y su registro.</p>
      <label>Motivo (opcional; lo verá el usuario)
        <textarea rows={3} maxLength={300} value={reason} onChange={(event) => setReason(event.target.value)} />
      </label>
    </Modal>
  </section>;
}
