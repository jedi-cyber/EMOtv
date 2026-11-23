import { useState } from "react";
import { apiRequest } from "../api/http";
import type { ImageAudience, ImageReview, UserImage } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { Modal } from "../components/Modal";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip } from "../components/StatusChip";
import { StimulusImage } from "../components/StimulusImage";
import { toast } from "../components/Toaster";

type Decision = ImageAudience | "delete";

const PERSON_HINT = "Si ves a una persona, elimina la imagen.";
// Frases completas: «Aprobar para niños», «aprobada para adultos».
const forWhom: Record<ImageAudience, string> = { children: "para niños", adults: "para adultos" };
const other: Record<ImageAudience, ImageAudience> = { children: "adults", adults: "children" };

function formatDate(value: string) {
  return new Date(value).toLocaleDateString("es-PE", { day: "numeric", month: "long", year: "numeric" });
}

function fileOf(id: string, preview = false) {
  return `/own-stimuli/${encodeURIComponent(id)}/file${preview ? "?preview=true" : ""}`;
}

function images(count: number) { return count === 1 ? "1 imagen" : `${count} imágenes`; }

/** Revisión del docente: imágenes que subieron los usuarios de su grupo. Una imagen sin aprobar no se usa. */
export function ImageReviewPage() {
  const { token } = useAuth();
  const query = useApiQuery<ImageReview>("/own-stimuli/review");
  const pending = query.data?.pending ?? [];
  const approved = query.data?.approved ?? [];
  const pendingCount = pending.reduce((total, batch) => total + batch.images.length, 0);
  const [busy, setBusy] = useState<string[]>([]);
  const [enlarged, setEnlarged] = useState<UserImage | null>(null);
  const [removing, setRemoving] = useState<UserImage | null>(null);
  const [reason, setReason] = useState("");

  /** Aplica una decisión a varias imágenes; las agrupa para enviar una petición por decisión. */
  async function decide(targets: { item: UserImage; decision: Decision }[], success: string) {
    const ids = targets.map(({ item }) => item.id);
    setBusy((current) => [...current, ...ids]);
    const groups = new Map<Decision, string[]>();
    for (const { item, decision } of targets) groups.set(decision, [...(groups.get(decision) ?? []), item.id]);
    try {
      for (const [decision, group] of groups) {
        await apiRequest("/own-stimuli/review", { method: "POST", token, body: JSON.stringify({
          image_ids: group, decision, reason: decision === "delete" ? reason.trim() || null : null,
        }) });
      }
      toast.success(success);
      setRemoving(null); setReason("");
    } catch (failure) {
      toast.error(failure instanceof Error ? failure.message : "No se pudo aplicar la decisión.");
    } finally {
      setBusy((current) => current.filter((id) => !ids.includes(id)));
      await query.reload();
    }
  }

  function card(item: UserImage) {
    const isPending = item.status === "pending";
    const working = busy.includes(item.id);
    const proposed = item.audience;
    return <li key={item.id} className={`card review-card ${isPending ? "is-pending" : "is-approved"}`}>
      <p className="review-status">
        {isPending
          ? <><span className="review-status-icon" aria-hidden="true">●</span>Sin revisar: aún no se usa</>
          : <><span className="review-status-icon" aria-hidden="true">✓</span>Aprobada {forWhom[item.audience]}</>}
      </p>
      <button type="button" className="review-preview" onClick={() => setEnlarged(item)} aria-label={`Ampliar «${item.title}»`}>
        <StimulusImage id={item.id} alt={item.title} path={fileOf(item.id)} className="review-thumb" />
      </button>
      <div className="review-meta">
        <strong>{item.title}</strong>
        <span>Origen: {item.origin}</span>
        {isPending && <span>El usuario la propuso {forWhom[proposed]}.</span>}
        {isPending && item.possible_person && <span><StatusChip tone="error">Revisar: posible persona</StatusChip></span>}
      </div>
      {isPending && <p className="review-hint">{PERSON_HINT}</p>}
      <div className="review-actions" role="group" aria-label={`Decisión sobre «${item.title}»`}>
        {isPending ? <>
          <Button variant="primary" size="sm" loading={working} disabled={working}
            onClick={() => { void decide([{ item, decision: proposed }], `«${item.title}» quedó aprobada ${forWhom[proposed]}.`); }}>
            Aprobar {forWhom[proposed]}
          </Button>
          <Button size="sm" disabled={working}
            onClick={() => { void decide([{ item, decision: other[proposed] }], `«${item.title}» quedó aprobada ${forWhom[other[proposed]]}.`); }}>
            Aprobar {forWhom[other[proposed]]}
          </Button>
        </> : <Button size="sm" loading={working} disabled={working}
          onClick={() => { void decide([{ item, decision: other[item.audience] }], `«${item.title}» ahora es ${forWhom[other[item.audience]]}.`); }}>
          Cambiar a {forWhom[other[item.audience]]}
        </Button>}
        <Button variant="ghost" size="sm" className="review-delete" disabled={working}
          onClick={() => { setReason(""); setRemoving(item); }}>Eliminar</Button>
      </div>
    </li>;
  }

  const empty = !query.loading && !query.error && pendingCount === 0 && approved.length === 0;

  return <section>
    <PageHeader title="Imágenes por revisar"
      description="Imágenes que subieron los usuarios de tu grupo. Solo se usan en sus protocolos cuando las apruebas." />
    <Callout variant="info" role="note">
      El sistema rechaza las imágenes que parecen mostrar a una persona, pero esa detección automática puede equivocarse.
      {" "}{PERSON_HINT} «Para niños» sirve en protocolos para niños y para adultos; «Para adultos», solo para adultos.
    </Callout>

    <PageState {...query} empty={empty} emptyMessage="No hay imágenes de tu grupo por revisar." onRetry={query.reload} />

    {!query.loading && !query.error && !empty && <section className="review-batch" aria-labelledby="review-pending-title">
      <header className="review-batch-head">
        <h2 id="review-pending-title">Sin revisar ({pendingCount})</h2>
      </header>
      {pendingCount === 0 && <p className="muted">No hay imágenes nuevas. Las aprobadas están abajo.</p>}
      {pending.map((batch) => {
        const working = batch.images.some((item) => busy.includes(item.id));
        return <section key={batch.batch_id} className="review-lot" aria-label={`Lote de ${batch.uploaded_by}`}>
          <header className="review-batch-head">
            <h3>{batch.uploaded_by} · {formatDate(batch.uploaded_at)}</h3>
            {batch.images.length > 1 && <Button size="sm" disabled={working}
              onClick={() => { void decide(batch.images.map((item) => ({ item, decision: item.audience })),
                `Se aprobaron ${images(batch.images.length)} como las propuso el usuario.`); }}>
              Aprobar las {batch.images.length} como las propuso
            </Button>}
          </header>
          <ul className="review-grid">{batch.images.map(card)}</ul>
        </section>;
      })}
    </section>}

    {approved.length > 0 && <section className="review-batch" aria-labelledby="review-approved-title">
      <header className="review-batch-head">
        <h2 id="review-approved-title">Aprobadas ({approved.length})</h2>
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

    <Modal open={removing !== null} title="Eliminar imagen" onClose={() => setRemoving(null)}
      busy={removing !== null && busy.includes(removing.id)}
      footer={<>
        <Button disabled={removing !== null && busy.includes(removing.id)} onClick={() => setRemoving(null)}>Cancelar</Button>
        <Button variant="danger" loading={removing !== null && busy.includes(removing.id)}
          onClick={() => { if (removing) void decide([{ item: removing, decision: "delete" }], `Se eliminó «${removing.title}».`); }}>
          Eliminar
        </Button>
      </>}>
      <p>Se eliminará «{removing?.title}»: se borra el archivo y su registro.</p>
      <label>Motivo (opcional; lo verá el usuario)
        <textarea rows={3} maxLength={300} value={reason} onChange={(event) => setReason(event.target.value)} />
      </label>
    </Modal>
  </section>;
}
