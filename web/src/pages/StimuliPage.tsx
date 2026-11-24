import { useState } from "react";
import type { FormEvent } from "react";
import { apiRequest } from "../api/http";
import type { Stimulus, StimulusIntensity } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { ActionsMenu } from "../components/ActionsMenu";
import type { ActionsMenuItem } from "../components/ActionsMenu";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Modal } from "../components/Modal";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip } from "../components/StatusChip";
import { StimulusImage } from "../components/StimulusImage";
import { expectedExpressionNames, stimulusSummary } from "../stimuli/labels";
import { toast } from "../components/Toaster";

// Las imágenes abstractas están congeladas: solo se agregan imágenes emocionales.
const emptyForm = {
  title: "", kind: "emotional", category: "", expected_expression: "happiness",
  intensity: "mild" as StimulusIntensity, min_age: "6", origin: "", license: "",
};

/** Categoría de los dibujos de creación propia que trae EMOtv (igual que en el servidor). */
export const INITIAL_BANK_CATEGORY = "Banco inicial EMOtv";

/** Banco de estímulos: el docente gestiona los de su grupo; el administrador, los institucionales. */
export function StimuliPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";
  const query = useApiQuery<Stimulus[]>("/stimuli");
  const items = query.data ?? [];
  const [form, setForm] = useState(emptyForm);
  const [file, setFile] = useState<File | null>(null);
  const [notParticipantPhoto, setNotParticipantPhoto] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fileKey, setFileKey] = useState(0);
  const [adding, setAdding] = useState(false);
  // Estímulo que se mira en grande y el que se va a eliminar.
  const [preview, setPreview] = useState<Stimulus | null>(null);
  const [removing, setRemoving] = useState<Stimulus | null>(null);
  const ready = file != null && notParticipantPhoto
    && form.title.trim() && form.category.trim() && form.origin.trim() && form.license.trim();

  function set<K extends keyof typeof emptyForm>(key: K, value: (typeof emptyForm)[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    setBusy(true); setError("");
    const body = new FormData();
    body.append("file", file);
    for (const [key, value] of Object.entries(form)) body.append(key, value);
    body.append("not_a_participant_photo", String(notParticipantPhoto));
    try {
      const created = await apiRequest<Stimulus>("/stimuli", { method: "POST", body, token });
      toast.success(`Se agregó «${created.title}». Las imágenes que agregas no pasan por revisión.`);
      setForm(emptyForm); setFile(null); setFileKey((key) => key + 1);
      setNotParticipantPhoto(false); setAdding(false);
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo agregar el estímulo."); }
    finally { setBusy(false); }
  }

  async function addInitialBank() {
    setBusy(true); setError("");
    try {
      const result = await apiRequest<{ added: number }>("/stimuli/initial-bank", { method: "POST", token });
      toast.success(result.added > 0
        ? `Se agregaron ${result.added} dibujos del banco inicial. Ya se pueden usar en los protocolos.`
        : "El banco inicial ya estaba completo.");
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo agregar el banco inicial."); }
    finally { setBusy(false); }
  }

  async function change(item: Stimulus, action: "approve" | "retire" | "restore") {
    setBusy(true); setError("");
    try {
      if (action === "approve") await apiRequest(`/stimuli/${encodeURIComponent(item.id)}/approve`, { method: "POST", token });
      else await apiRequest(`/stimuli/${encodeURIComponent(item.id)}/active`, {
        method: "PUT", token, body: JSON.stringify({ active: action === "restore" }),
      });
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo actualizar el estímulo."); }
    finally { setBusy(false); }
  }

  async function deleteStimulus() {
    const item = removing;
    if (!item) return;
    setBusy(true); setError("");
    try {
      await apiRequest(`/stimuli/${encodeURIComponent(item.id)}`, { method: "DELETE", token });
      toast.success(`Se eliminó «${item.title}».`);
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo eliminar el estímulo."); }
    finally { setBusy(false); setRemoving(null); }
  }

  function actions(item: Stimulus): ActionsMenuItem[] {
    const items: ActionsMenuItem[] = [{ label: "Vista previa", onSelect: () => setPreview(item) }];
    if (!item.can_manage) return items;
    if (!item.approved) items.push({ label: "Aprobar", disabled: busy, onSelect: () => { void change(item, "approve"); } });
    items.push(item.active
      ? { label: "Retirar", disabled: busy, onSelect: () => { void change(item, "retire"); } }
      : { label: "Volver a ofrecer", disabled: busy, onSelect: () => { void change(item, "restore"); } });
    items.push({ label: "Eliminar", danger: true, disabled: busy, onSelect: () => setRemoving(item) });
    return items;
  }

  return <section>
    <PageHeader title={isAdmin ? "Estímulos institucionales" : "Estímulos"}
      description={isAdmin
        ? "Imágenes que pueden usar todos los usuarios y docentes de la Facultad."
        : "Imágenes que los usuarios de tu grupo pueden usar en sus protocolos, junto con las institucionales."}
      actions={<Button variant="primary" type="button" onClick={() => { setError(""); setAdding(true); }}>Agregar estímulo</Button>} />
    <Callout variant="info" role="note">
      Un estímulo nunca es una fotografía de una persona evaluada. El sistema solo muestra y registra: no relaciona
      ninguna imagen con una condición.
    </Callout>
    {error && !adding && <Callout variant="error">{error}</Callout>}
    {isAdmin && !query.loading && !query.error && !items.some((item) => item.category === INITIAL_BANK_CATEGORY) &&
      <Callout variant="info" role="note">
        <p>EMOtv trae un banco inicial de 18 dibujos sencillos de creación propia: seis emociones básicas, tres
          versiones de cada una, aptos para niños desde los 3 años. No son fotografías de personas.</p>
        <Button disabled={busy} onClick={() => { void addInitialBank(); }}>Agregar el banco inicial</Button>
      </Callout>}

    <Modal open={adding} title="Agregar estímulo" onClose={() => setAdding(false)} busy={busy}
      footer={<>
        <Button variant="secondary" type="button" disabled={busy} onClick={() => setAdding(false)}>Cancelar</Button>
        <Button variant="primary" type="submit" form="stimulus-form" disabled={busy || !ready}>{busy ? "Agregando…" : "Agregar"}</Button>
      </>}>
    <form id="stimulus-form" className="form-stack" onSubmit={(event) => { void submit(event); }}>
      {error && <Callout variant="error">{error}</Callout>}
      <label>Imagen (PNG, JPEG o WebP, hasta 5 MB)
        <input key={fileKey} type="file" accept="image/png,image/jpeg,image/webp"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
      </label>
      <label>Título<input value={form.title} maxLength={120} required onChange={(event) => set("title", event.target.value)} /></label>
      <label>Categoría<input value={form.category} maxLength={80} required onChange={(event) => set("category", event.target.value)} /></label>
      <label>Expresión que se espera provocar
        <select value={form.expected_expression} onChange={(event) => set("expected_expression", event.target.value)}>
          {Object.entries(expectedExpressionNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select></label>
      <label>Intensidad<select value={form.intensity} onChange={(event) => set("intensity", event.target.value as StimulusIntensity)}>
        <option value="mild">Leve</option>
        <option value="moderate">Moderada (no se ofrece a niños)</option>
      </select></label>
      <label>Edad mínima en años<input type="number" min={1} max={99} value={form.min_age} required
        onChange={(event) => set("min_age", event.target.value)} /></label>
      <label>Origen<input value={form.origin} maxLength={500} required placeholder="Creación propia, banco con licencia abierta…"
        onChange={(event) => set("origin", event.target.value)} /></label>
      <label>Licencia<input value={form.license} maxLength={300} required onChange={(event) => set("license", event.target.value)} /></label>
      <Checkbox checked={notParticipantPhoto} onChange={(event) => setNotParticipantPhoto(event.target.checked)}>
        Confirmo que la imagen no es una fotografía de una persona evaluada
      </Checkbox>
    </form>
    </Modal>

    <PageState {...query} empty={!query.loading && !query.error && items.length === 0}
      emptyMessage="Todavía no hay estímulos en el banco." onRetry={query.reload} />
    {items.length > 0 && <ul className="card-list stimulus-list">{items.map((item) => <li key={item.id} className="card row-card stimulus-row">
      <StimulusImage id={item.id} alt={item.title} />
      <div>
        <strong>{item.title}</strong>
        <span>{stimulusSummary(item)}</span>
        <span>Origen: {item.origin} · Licencia: {item.license}</span>
        <span className="inline-actions">
          {item.approved ? <StatusChip tone="success">Aprobado</StatusChip> : <StatusChip tone="progress">Sin aprobar</StatusChip>}
          {!item.active && <StatusChip tone="neutral">Retirado</StatusChip>}
          {item.scope === "institution" && !isAdmin && <StatusChip tone="neutral">Institucional</StatusChip>}
        </span>
      </div>
      <ActionsMenu name={item.title} items={actions(item)} />
    </li>)}</ul>}

    <Modal open={preview !== null} title={preview?.title ?? "Vista previa"} onClose={() => setPreview(null)}>
      {preview && <StimulusImage id={preview.id} alt={preview.title} className="stimulus-preview" />}
    </Modal>
    <ConfirmDialog open={removing !== null} title="Eliminar estímulo" confirmLabel="Eliminar" confirming={busy}
      message={removing ? `Se eliminará «${removing.title}» y su archivo. Los protocolos que lo usan pedirán elegir otra imagen; las sesiones ya hechas conservan su registro. Si solo quieres dejar de ofrecerlo, usa «Retirar».` : ""}
      onConfirm={() => { void deleteStimulus(); }} onCancel={() => setRemoving(null)} />
  </section>;
}
