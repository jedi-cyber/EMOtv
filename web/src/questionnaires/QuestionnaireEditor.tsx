import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { apiRequest } from "../api/http";
import type { Question, QuestionKind, Questionnaire } from "../api/types";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { Modal } from "../components/Modal";
import { QuestionnaireForm, QuestionnaireNote } from "./QuestionnaireForm";

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

interface QuestionnaireEditorProps {
  open: boolean;
  /** Sin editing, crea un cuestionario nuevo. */
  editing?: Questionnaire | null;
  onClose(): void;
  /** message: qué pasó (versión nueva, actualizado o creado). */
  onSaved(saved: Questionnaire, message: string): void;
}

/** Editor de cuestionarios en una ventana: en Cuestionarios y, sin salir, desde Protocolos. */
export function QuestionnaireEditor({ open, editing = null, onClose, onSaved }: QuestionnaireEditorProps) {
  const { token } = useAuth();
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [newKind, setNewKind] = useState<QuestionKind>("faces");
  const [preview, setPreview] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!open) return;
    setError(""); setPreview(false);
    setDraft(editing ? { title: editing.title, instructions: editing.instructions, questions: editing.questions } : emptyDraft);
  }, [open, editing]);

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

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true); setError("");
    try {
      const body = JSON.stringify({ ...draft, questions: draft.questions.map((item) => ({
        ...item, options: item.options.map((option) => option.trim()).filter(Boolean),
        min_label: item.min_label?.trim() || null, max_label: item.max_label?.trim() || null,
      })) });
      const saved = await apiRequest<Questionnaire>(editing ? `/questionnaires/${encodeURIComponent(editing.id)}` : "/questionnaires",
        { method: editing ? "PUT" : "POST", token, body });
      onSaved(saved, editing && saved.id !== editing.id
        ? `Se creó la versión ${saved.version}: la anterior ya se usó en una sesión y se conserva sin cambios.`
        : editing ? "Cuestionario actualizado." : "Cuestionario creado.");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo guardar el cuestionario."); }
    finally { setBusy(false); }
  }

  const draftReady = draft.title.trim() && draft.questions.length > 0 && draft.questions.every((item) => item.text.trim());

  return <>
    <Modal open={open} title={editing ? `Editar «${editing.title}»` : "Nuevo cuestionario"} onClose={onClose} busy={busy}
      footer={<>
        <Button disabled={busy} onClick={onClose}>Cancelar</Button>
        <Button disabled={!draftReady} onClick={() => setPreview(true)}>Vista previa</Button>
        <Button variant="primary" type="submit" form="questionnaire-editor" disabled={busy || !draftReady}>{busy ? "Guardando…" : editing ? "Guardar cambios" : "Guardar cuestionario"}</Button>
      </>}>
    <form id="questionnaire-editor" className="form-stack" onSubmit={(event) => { void save(event); }}>
      {error && <Callout variant="error">{error}</Callout>}
      {editing?.used && <Callout variant="info" role="note">
        Este cuestionario ya se usó en una sesión: al guardar se crea la versión {editing.version + 1} y la actual se conserva.
      </Callout>}
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
      <QuestionnaireNote />
    </form>
    </Modal>
    <QuestionnairePreview questionnaire={preview ? draft : null} onClose={() => setPreview(false)} />
  </>;
}

/** Así lo verá quien responda; la vista previa no guarda respuestas. */
export function QuestionnairePreview({ questionnaire, onClose }: {
  questionnaire: Pick<Questionnaire, "title" | "instructions" | "questions"> | null; onClose(): void;
}) {
  if (!questionnaire) return null;
  return <Modal open title="Vista previa" onClose={onClose}
    footer={<div className="inline-actions"><Button onClick={onClose}>Cerrar</Button></div>}>
    <p className="muted">Así lo verá quien responda. Puedes probarlo: la vista previa no guarda respuestas.</p>
    <QuestionnaireForm questionnaire={questionnaire} onSubmit={() => undefined} submitLabel="Comprobar (no se guarda)" />
  </Modal>;
}
