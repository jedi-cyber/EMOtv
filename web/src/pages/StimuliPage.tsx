import { useState } from "react";
import type { FormEvent } from "react";
import { apiRequest } from "../api/http";
import type { Stimulus, StimulusIntensity, StimulusKind } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip } from "../components/StatusChip";
import { StimulusImage } from "../components/StimulusImage";
import { expectedExpressionNames, stimulusKindNames, stimulusSummary } from "../stimuli/labels";

const emptyForm = {
  title: "", kind: "emotional" as StimulusKind, category: "", expected_expression: "happiness",
  intensity: "mild" as StimulusIntensity, min_age: "6", origin: "", license: "",
};

/** Banco de estímulos: el docente gestiona los de su grupo; el administrador, los institucionales. */
export function StimuliPage() {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "admin";
  const query = useApiQuery<Stimulus[]>("/stimuli");
  const items = query.data ?? [];
  const [form, setForm] = useState(emptyForm);
  const [file, setFile] = useState<File | null>(null);
  const [notParticipantPhoto, setNotParticipantPhoto] = useState(false);
  const [notProjective, setNotProjective] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [fileKey, setFileKey] = useState(0);
  const abstract = form.kind === "abstract";
  const ready = file != null && notParticipantPhoto && (!abstract || notProjective)
    && form.title.trim() && form.category.trim() && form.origin.trim() && form.license.trim();

  function set<K extends keyof typeof emptyForm>(key: K, value: (typeof emptyForm)[K]) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!file) return;
    setBusy(true); setError(""); setMessage("");
    const body = new FormData();
    body.append("file", file);
    for (const [key, value] of Object.entries(form)) {
      if (key === "expected_expression" && abstract) continue;
      body.append(key, value);
    }
    body.append("not_a_participant_photo", String(notParticipantPhoto));
    body.append("not_a_projective_test", String(abstract && notProjective));
    try {
      const created = await apiRequest<Stimulus>("/stimuli", { method: "POST", body, token });
      setMessage(`Se agregó «${created.title}». Apruébalo cuando lo hayas revisado: con niños solo se ofrecen estímulos aprobados.`);
      setForm(emptyForm); setFile(null); setFileKey((key) => key + 1);
      setNotParticipantPhoto(false); setNotProjective(false);
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo agregar el estímulo."); }
    finally { setBusy(false); }
  }

  async function change(item: Stimulus, action: "approve" | "retire" | "restore") {
    setBusy(true); setError(""); setMessage("");
    try {
      if (action === "approve") await apiRequest(`/stimuli/${encodeURIComponent(item.id)}/approve`, { method: "POST", token });
      else await apiRequest(`/stimuli/${encodeURIComponent(item.id)}/active`, {
        method: "PUT", token, body: JSON.stringify({ active: action === "restore" }),
      });
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo actualizar el estímulo."); }
    finally { setBusy(false); }
  }

  return <section>
    <PageHeader title={isAdmin ? "Estímulos institucionales" : "Estímulos"}
      description={isAdmin
        ? "Imágenes que pueden usar todos los usuarios y docentes de la Facultad."
        : "Imágenes que los usuarios de tu grupo pueden usar en sus protocolos, junto con las institucionales."} />
    <Callout variant="info" role="note">
      Un estímulo nunca es una fotografía de un participante. Las imágenes abstractas son de creación propia o con una
      licencia que lo permita; no se incluyen láminas de pruebas proyectivas publicadas. El sistema solo muestra y
      registra: no relaciona ninguna imagen con una condición.
    </Callout>
    {message && <Callout variant="success">{message}</Callout>}
    {error && <Callout variant="error">{error}</Callout>}

    <form className="card form-stack" onSubmit={(event) => { void submit(event); }}>
      <h2>Agregar estímulo</h2>
      <label>Imagen (PNG, JPEG o WebP, hasta 5 MB)
        <input key={fileKey} type="file" accept="image/png,image/jpeg,image/webp"
          onChange={(event) => setFile(event.target.files?.[0] ?? null)} />
      </label>
      <label>Título<input value={form.title} maxLength={120} required onChange={(event) => set("title", event.target.value)} /></label>
      <label>Tipo<select value={form.kind} onChange={(event) => set("kind", event.target.value as StimulusKind)}>
        <option value="emotional">{stimulusKindNames.emotional}</option>
        <option value="abstract">{stimulusKindNames.abstract}</option>
      </select></label>
      <label>Categoría<input value={form.category} maxLength={80} required onChange={(event) => set("category", event.target.value)} /></label>
      {!abstract && <label>Expresión que se espera provocar
        <select value={form.expected_expression} onChange={(event) => set("expected_expression", event.target.value)}>
          {Object.entries(expectedExpressionNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
        </select></label>}
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
        Confirmo que la imagen no es una fotografía de un participante
      </Checkbox>
      {abstract && <Checkbox checked={notProjective} onChange={(event) => setNotProjective(event.target.checked)}>
        Confirmo que es de creación propia o con una licencia que lo permite, y que no es una lámina de una prueba proyectiva publicada
      </Checkbox>}
      <Button variant="primary" type="submit" disabled={busy || !ready}>{busy ? "Agregando…" : "Agregar estímulo"}</Button>
    </form>

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
      {item.can_manage && <div className="inline-actions">
        {!item.approved && <Button disabled={busy} onClick={() => { void change(item, "approve"); }}>Aprobar</Button>}
        {item.active
          ? <Button disabled={busy} onClick={() => { void change(item, "retire"); }}>Retirar</Button>
          : <Button disabled={busy} onClick={() => { void change(item, "restore"); }}>Volver a ofrecer</Button>}
      </div>}
    </li>)}</ul>}
  </section>;
}
