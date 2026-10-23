import { useState } from "react";
import type { FormEvent } from "react";
import { apiRequest } from "../api/http";
import type { Question, QuestionKind, Questionnaire } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { Modal } from "../components/Modal";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip } from "../components/StatusChip";
import { QuestionnaireForm, QuestionnaireNote } from "../questionnaires/QuestionnaireForm";

const kindNames: Record<QuestionKind, string> = {
  scale: "Escala",
  single_choice: "Opción única",
  multiple_choice: "Opción múltiple",
  short_text: "Respuesta breve",
  faces: "Escala de caritas",
};

interface Draft { title: string; instructions: string; questions: Question[] }
const emptyDraft: Draft = { title: "", instructions: "", questions: [] };

function newId() {
  return typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `q-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

function blankQuestion(kind: QuestionKind): Question {
  return {
    id: newId(), kind, text: "", required: false,
    options: kind === "single_choice" || kind === "multiple_choice" ? ["", ""] : [],
    scale_points: kind === "scale" ? 5 : null, min_label: null, max_label: null,
  };
}

/** Constructor de cuestionarios para quien conduce la sesión. */
export function QuestionnairesPage() {
  const { token, user } = useAuth();
  const isDocente = user?.role === "psychologist";
  const query = useApiQuery<Questionnaire[]>("/questionnaires");
  const items = query.data ?? [];
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [editing, setEditing] = useState<Questionnaire | null>(null);
  const [newKind, setNewKind] = useState<QuestionKind>("faces");
  const [preview, setPreview] = useState<Pick<Questionnaire, "title" | "instructions" | "questions"> | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  function update(changes: Partial<Draft>) { setDraft((current) => ({ ...current, ...changes })); }
  function updateQuestion(index: number, changes: Partial<Question>) {
    update({ questions: draft.questions.map((item, position) => position === index ? { ...item, ...changes } : item) });
  }
  function move(index: number, offset: number) {
    const questions = [...draft.questions];
    const [item] = questions.splice(index, 1);
    questions.splice(index + offset, 0, item);
    update({ questions });
  }
  function startEditing(item: Questionnaire) {
    setEditing(item); setMessage(""); setError("");
    setDraft({ title: item.title, instructions: item.instructions, questions: item.questions });
  }
  function reset() { setEditing(null); setDraft(emptyDraft); }

  async function run(action: () => Promise<string>) {
    setBusy(true); setError(""); setMessage("");
    try { setMessage(await action()); await query.reload(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo completar la acción."); }
    finally { setBusy(false); }
  }

  function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void run(async () => {
      const body = JSON.stringify({ ...draft, questions: draft.questions.map((item) => ({
        ...item, options: item.options.map((option) => option.trim()).filter(Boolean),
        min_label: item.min_label?.trim() || null, max_label: item.max_label?.trim() || null,
      })) });
      const saved = await apiRequest<Questionnaire>(editing ? `/questionnaires/${encodeURIComponent(editing.id)}` : "/questionnaires",
        { method: editing ? "PUT" : "POST", token, body });
      const text = editing && saved.id !== editing.id
        ? `Se creó la versión ${saved.version}: la anterior ya se usó en una sesión y se conserva sin cambios.`
        : editing ? "Cuestionario actualizado." : "Cuestionario creado.";
      reset();
      return text;
    });
  }

  const draftReady = draft.title.trim() && draft.questions.length > 0 && draft.questions.every((item) => item.text.trim());

  return <section>
    <PageHeader title="Cuestionarios"
      description="Cuestionarios que quien conduce la sesión aplica antes de iniciar el analizador. EMOtv solo los presenta y registra las respuestas." />
    {message && <Callout variant="success">{message}</Callout>}
    {error && <Callout variant="error">{error}</Callout>}

    <form className="card form-stack" onSubmit={save}>
      <h2>{editing ? `Editar «${editing.title}»` : "Nuevo cuestionario"}</h2>
      {editing?.used && <Callout variant="info" role="note">
        Este cuestionario ya se usó en una sesión: al guardar se crea la versión {editing.version + 1} y la actual se conserva.
      </Callout>}
      {!editing && <div className="inline-actions">
        <Button disabled={busy} onClick={() => { void run(async () => {
          await apiRequest("/questionnaires/starter", { method: "POST", token });
          return "Se agregó una copia de la plantilla inicial a tus cuestionarios. Puedes editarla.";
        }); }}>Usar la plantilla inicial</Button>
        <span className="muted">Dos preguntas de caritas: cómo te sientes y qué tan tranquilo o inquieto estás.</span>
      </div>}
      <label>Título<input value={draft.title} maxLength={120} required onChange={(event) => update({ title: event.target.value })} /></label>
      <label>Indicaciones<textarea rows={2} maxLength={2000} value={draft.instructions} onChange={(event) => update({ instructions: event.target.value })} /></label>

      <h3>Preguntas</h3>
      {draft.questions.length === 0 && <p className="muted">Agrega al menos una pregunta.</p>}
      <ol className="card-list">{draft.questions.map((item, index) => <li key={item.id} className="card question-editor">
        <p className="muted">{index + 1}. {kindNames[item.kind]}</p>
        <label>Pregunta<input value={item.text} maxLength={300} required onChange={(event) => updateQuestion(index, { text: event.target.value })} /></label>
        {item.kind === "scale" && <label>Puntos de la escala<select value={item.scale_points ?? 5}
          onChange={(event) => updateQuestion(index, { scale_points: Number(event.target.value) })}>
          {[2, 3, 4, 5, 6, 7].map((points) => <option key={points} value={points}>{points}</option>)}
        </select></label>}
        {(item.kind === "scale" || item.kind === "faces") && <div className="inline-actions">
          <label>Etiqueta del extremo inicial{item.kind === "faces" ? " (opcional)" : ""}<input value={item.min_label ?? ""} maxLength={60}
            required={item.kind === "scale"} onChange={(event) => updateQuestion(index, { min_label: event.target.value })} /></label>
          <label>Etiqueta del extremo final{item.kind === "faces" ? " (opcional)" : ""}<input value={item.max_label ?? ""} maxLength={60}
            required={item.kind === "scale"} onChange={(event) => updateQuestion(index, { max_label: event.target.value })} /></label>
        </div>}
        {(item.kind === "single_choice" || item.kind === "multiple_choice") && <div className="form-stack">
          {item.options.map((option, position) => <div key={position} className="inline-actions">
            <label>Opción {position + 1}<input value={option} maxLength={120} required
              onChange={(event) => updateQuestion(index, { options: item.options.map((value, at) => at === position ? event.target.value : value) })} /></label>
            {item.options.length > 2 && <Button size="sm" variant="ghost"
              onClick={() => updateQuestion(index, { options: item.options.filter((_, at) => at !== position) })}>Quitar opción</Button>}
          </div>)}
          {item.options.length < 10 && <Button size="sm" onClick={() => updateQuestion(index, { options: [...item.options, ""] })}>Agregar opción</Button>}
        </div>}
        <Checkbox checked={item.required} onChange={(event) => updateQuestion(index, { required: event.target.checked })}>Obligatoria</Checkbox>
        <div className="inline-actions">
          <Button size="sm" disabled={index === 0} onClick={() => move(index, -1)}>Subir</Button>
          <Button size="sm" disabled={index === draft.questions.length - 1} onClick={() => move(index, 1)}>Bajar</Button>
          <Button size="sm" variant="ghost" onClick={() => update({ questions: draft.questions.filter((_, at) => at !== index) })}>Quitar pregunta</Button>
        </div>
      </li>)}</ol>
      <div className="inline-actions">
        <label>Tipo de pregunta<select value={newKind} onChange={(event) => setNewKind(event.target.value as QuestionKind)}>
          {(Object.keys(kindNames) as QuestionKind[]).map((kind) => <option key={kind} value={kind}>{kindNames[kind]}</option>)}
        </select></label>
        <Button disabled={draft.questions.length >= 40} onClick={() => update({ questions: [...draft.questions, blankQuestion(newKind)] })}>Agregar pregunta</Button>
      </div>
      <div className="inline-actions">
        <Button disabled={!draftReady} onClick={() => setPreview(draft)}>Vista previa</Button>
        <Button variant="primary" type="submit" disabled={busy || !draftReady}>{busy ? "Guardando…" : editing ? "Guardar cambios" : "Guardar cuestionario"}</Button>
        {editing && <Button onClick={reset}>Cancelar</Button>}
      </div>
      <QuestionnaireNote />
    </form>

    <PageState {...query} empty={!query.loading && !query.error && items.length === 0}
      emptyMessage="Todavía no tienes cuestionarios. Crea uno o usa la plantilla inicial." onRetry={query.reload} />
    {items.length > 0 && <ul className="card-list">{items.map((item) => <li key={item.id} className="card">
      <div className="row-card">
        <div>
          <strong>{item.title}</strong>
          <span>Versión {item.version} · {item.questions.length} {item.questions.length === 1 ? "pregunta" : "preguntas"}</span>
          <span className="inline-actions">
            {!item.owned_by_me && <StatusChip tone="neutral">Plantilla de tu docente</StatusChip>}
            {item.owned_by_me && item.shared_with_group && <StatusChip tone="progress">Compartido con tu grupo</StatusChip>}
            {item.used && <StatusChip tone="neutral">Usado en sesiones</StatusChip>}
          </span>
        </div>
        <div className="inline-actions">
          <Button onClick={() => setPreview(item)}>Vista previa</Button>
          {item.owned_by_me && <Button onClick={() => startEditing(item)}>Editar</Button>}
          <Button disabled={busy} onClick={() => { void run(async () => {
            await apiRequest(`/questionnaires/${encodeURIComponent(item.id)}/copy`, { method: "POST", token });
            return `Se agregó una copia de «${item.title}» a tus cuestionarios.`;
          }); }}>{item.owned_by_me ? "Duplicar" : "Copiar y modificar"}</Button>
          {isDocente && item.owned_by_me && <Button disabled={busy} onClick={() => { void run(async () => {
            await apiRequest(`/questionnaires/${encodeURIComponent(item.id)}/share`, { method: "PUT", token, body: JSON.stringify({ shared: !item.shared_with_group }) });
            return item.shared_with_group ? "Tu grupo ya no ve este cuestionario como plantilla." : "Tu grupo puede copiar este cuestionario como plantilla.";
          }); }}>{item.shared_with_group ? "Dejar de compartir" : "Compartir con mi grupo"}</Button>}
        </div>
      </div>
      <QuestionnaireNote />
    </li>)}</ul>}

    {preview && <Modal open title="Vista previa" onClose={() => setPreview(null)}
      footer={<div className="inline-actions"><Button onClick={() => setPreview(null)}>Cerrar</Button></div>}>
      <p className="muted">Así lo verá quien responda. Puedes probarlo: la vista previa no guarda respuestas.</p>
      <QuestionnaireForm questionnaire={preview} onSubmit={() => undefined} submitLabel="Comprobar (no se guarda)" />
    </Modal>}
  </section>;
}
