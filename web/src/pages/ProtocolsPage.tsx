import { useState } from "react";
import type { FormEvent } from "react";
import { apiRequest } from "../api/http";
import type { Protocol, ProtocolStep, Questionnaire, Stimulus } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { Modal } from "../components/Modal";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip } from "../components/StatusChip";
import { stimulusSummary } from "../stimuli/labels";

interface Draft {
  name: string;
  description: string;
  for_children: boolean;
  steps: ProtocolStep[];
  pre_questionnaire_id: string;
  post_questionnaire_id: string;
}

const emptyDraft: Draft = { name: "", description: "", for_children: false, steps: [], pre_questionnaire_id: "", post_questionnaire_id: "" };

function suitableForChildren(item: Stimulus) {
  return item.active && item.approved && item.intensity === "mild";
}

/** Protocolos: secuencias de estímulos. Con niños se usan solo con la aprobación del docente. */
export function ProtocolsPage() {
  const { token, user } = useAuth();
  const isDocente = user?.role === "psychologist";
  const query = useApiQuery<Protocol[]>("/protocols");
  const stimuliQuery = useApiQuery<Stimulus[]>("/stimuli");
  const questionnairesQuery = useApiQuery<Questionnaire[]>("/questionnaires");
  const questionnaires = questionnairesQuery.data ?? [];
  const protocols = query.data ?? [];
  const stimuli = stimuliQuery.data ?? [];
  const byId = new Map(stimuli.map((item) => [item.id, item]));
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [editing, setEditing] = useState<Protocol | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [choice, setChoice] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const offered = stimuli.filter((item) => item.active && (!draft.for_children || suitableForChildren(item)));

  function update(changes: Partial<Draft>) { setDraft((current) => ({ ...current, ...changes })); }
  function updateStep(index: number, changes: Partial<ProtocolStep>) {
    update({ steps: draft.steps.map((step, position) => position === index ? { ...step, ...changes } : step) });
  }
  function move(index: number, offset: number) {
    const steps = [...draft.steps];
    const [step] = steps.splice(index, 1);
    steps.splice(index + offset, 0, step);
    update({ steps });
  }
  function addStep() {
    if (!choice) return;
    update({ steps: [...draft.steps, { stimulus_id: choice, exposure_seconds: 8, capture_after_seconds: 4, record_verbal_response: false, shown_before_analyzer: false }] });
    setChoice("");
  }
  function startEditing(item: Protocol) {
    setEditing(item); setEditorOpen(true);
    setDraft({ name: item.name, description: item.description, for_children: item.for_children, steps: item.steps,
      pre_questionnaire_id: item.pre_questionnaire_id ?? "", post_questionnaire_id: item.post_questionnaire_id ?? "" });
    setMessage(""); setError("");
  }
  function reset() { setEditing(null); setDraft(emptyDraft); setChoice(""); setEditorOpen(false); }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError(""); setMessage("");
    try {
      const saved = await apiRequest<Protocol>(editing ? `/protocols/${encodeURIComponent(editing.id)}` : "/protocols", {
        method: editing ? "PUT" : "POST", token, body: JSON.stringify({ ...draft, pre_questionnaire_id: draft.pre_questionnaire_id || null,
          post_questionnaire_id: draft.post_questionnaire_id || null }),
      });
      setMessage(editing && saved.id !== editing.id
        ? `Se creó la versión ${saved.version}: la anterior ya se usó en una sesión y se conserva sin cambios.`
        : editing ? "Protocolo actualizado." : "Protocolo creado.");
      if (saved.for_children && !saved.approved) setMessage((text) => `${text} Para usarlo con niños, tu docente debe aprobarlo.`);
      reset();
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo guardar el protocolo."); }
    finally { setBusy(false); }
  }

  async function approve(item: Protocol) {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiRequest(`/protocols/${encodeURIComponent(item.id)}/approve`, { method: "POST", token });
      setMessage(`Aprobaste «${item.name}» para usarlo con niños.`);
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo aprobar el protocolo."); }
    finally { setBusy(false); }
  }

  return <section>
    <PageHeader title="Protocolos"
      description={isDocente
        ? "Secuencias de estímulos para tus sesiones. Aquí apruebas las de tu grupo que se usarán con niños."
        : "Secuencias de estímulos para tus sesiones. Con niños se usan solo cuando tu docente las aprueba."}
      actions={<Button variant="primary" onClick={() => { reset(); setMessage(""); setError(""); setEditorOpen(true); }}>Nuevo protocolo</Button>} />
    {message && <Callout variant="success">{message}</Callout>}
    {error && !editorOpen && <Callout variant="error">{error}</Callout>}

    <Modal open={editorOpen} title={editing ? `Editar «${editing.name}»` : "Nuevo protocolo"} onClose={reset} busy={busy}
      footer={<>
        <Button disabled={busy} onClick={reset}>Cancelar</Button>
        <Button variant="primary" type="submit" form="protocol-editor" disabled={busy || draft.steps.length === 0 || !draft.name.trim()}>
          {busy ? "Guardando…" : editing ? "Guardar cambios" : "Crear protocolo"}
        </Button>
      </>}>
    <form id="protocol-editor" className="form-stack" onSubmit={(event) => { void submit(event); }}>
      {error && <Callout variant="error">{error}</Callout>}
      {editing?.used && <Callout variant="info" role="note">
        Este protocolo ya se usó en una sesión: al guardar se crea la versión {editing.version + 1} y la actual se conserva.
      </Callout>}
      <label>Nombre<input value={draft.name} maxLength={120} required onChange={(event) => update({ name: event.target.value })} /></label>
      <label>Descripción<textarea rows={2} maxLength={2000} value={draft.description}
        onChange={(event) => update({ description: event.target.value })} /></label>
      <Checkbox checked={draft.for_children} onChange={(event) => update({ for_children: event.target.checked })}>
        Para usar con niños (solo estímulos leves y aprobados; requiere la aprobación del docente)
      </Checkbox>
      <div className="inline-actions">
        <label>Cuestionario previo (opcional)<select value={draft.pre_questionnaire_id} onChange={(event) => update({ pre_questionnaire_id: event.target.value })}>
          <option value="">Sin cuestionario</option>
          {questionnaires.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
        </select></label>
        <label>Cuestionario posterior (opcional)<select value={draft.post_questionnaire_id} onChange={(event) => update({ post_questionnaire_id: event.target.value })}>
          <option value="">Sin cuestionario</option>
          {questionnaires.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
        </select></label>
      </div>
      <p className="muted">El previo se responde antes de iniciar el analizador; el posterior, al terminar. Se aplica la versión vigente de cada cuestionario.</p>

      <h3>Estímulos en orden</h3>
      {draft.steps.length === 0 && <p className="muted">Agrega al menos un estímulo.</p>}
      <ol className="card-list">{draft.steps.map((step, index) => {
        const stimulus = byId.get(step.stimulus_id);
        const unsuitable = draft.for_children && stimulus != null && !suitableForChildren(stimulus);
        return <li key={`${step.stimulus_id}-${index}`} className="row-card protocol-step">
          <div>
            <strong>{index + 1}. {stimulus?.title ?? "Estímulo no disponible"}</strong>
            {stimulus && <span>{stimulusSummary(stimulus)}</span>}
            {unsuitable && <span>No se puede usar con niños: elige uno leve y aprobado.</span>}
          </div>
          <div className="inline-actions">
            <label>Exposición (s)<input type="number" min={1} max={120} value={step.exposure_seconds}
              onChange={(event) => updateStep(index, { exposure_seconds: Number(event.target.value) })} /></label>
            <label>Captura a los (s)<input type="number" min={0} max={step.exposure_seconds} value={step.capture_after_seconds}
              onChange={(event) => updateStep(index, { capture_after_seconds: Number(event.target.value) })} /></label>
            {stimulus?.kind === "abstract" && <Checkbox checked={step.record_verbal_response}
              onChange={(event) => updateStep(index, { record_verbal_response: event.target.checked })}>Registrar lo que dice ver</Checkbox>}
            {stimulus?.kind === "abstract" && <Checkbox checked={step.shown_before_analyzer}
              onChange={(event) => updateStep(index, { shown_before_analyzer: event.target.checked })}>Mostrar antes del analizador (sin capturas)</Checkbox>}
            <Button size="sm" disabled={index === 0} onClick={() => move(index, -1)}>Subir</Button>
            <Button size="sm" disabled={index === draft.steps.length - 1} onClick={() => move(index, 1)}>Bajar</Button>
            <Button size="sm" variant="ghost" onClick={() => update({ steps: draft.steps.filter((_, position) => position !== index) })}>Quitar</Button>
          </div>
        </li>;
      })}</ol>
      <div className="inline-actions">
        <label>Estímulo<select value={choice} onChange={(event) => setChoice(event.target.value)}>
          <option value="">Elige un estímulo</option>
          {offered.map((item) => <option key={item.id} value={item.id}>{item.title} — {stimulusSummary(item)}</option>)}
        </select></label>
        <Button disabled={!choice} onClick={addStep}>Agregar al protocolo</Button>
      </div>
    </form>
    </Modal>

    <PageState {...query} empty={!query.loading && !query.error && protocols.length === 0}
      emptyMessage="Todavía no hay protocolos." onRetry={query.reload} />
    {protocols.length > 0 && <ul className="card-list">{protocols.map((item) => <li key={item.id} className="card row-card">
      <div>
        <strong>{item.name}</strong>
        <span>Versión {item.version} · {item.steps.length} {item.steps.length === 1 ? "estímulo" : "estímulos"}
          {isDocente && !item.owned_by_me ? " · De un usuario de tu grupo" : ""}</span>
        <span className="inline-actions">
          {item.for_children
            ? item.approved ? <StatusChip tone="success">Aprobado para niños</StatusChip> : <StatusChip tone="progress">Pendiente de aprobación</StatusChip>
            : <StatusChip tone="neutral">Para adultos</StatusChip>}
          {item.used && <StatusChip tone="neutral">Usado en sesiones</StatusChip>}
        </span>
      </div>
      <div className="inline-actions">
        {item.owned_by_me && <Button onClick={() => startEditing(item)}>Editar</Button>}
        {item.can_approve && item.for_children && !item.approved &&
          <Button disabled={busy} onClick={() => { void approve(item); }}>Aprobar para niños</Button>}
      </div>
    </li>)}</ul>}
  </section>;
}
