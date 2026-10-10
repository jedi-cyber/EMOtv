import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError, apiRequest } from "../api/http";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Callout } from "../components/Callout";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { Checkbox } from "../components/Checkbox";
import { StatusChip } from "../components/StatusChip";
import { useExpressionCatalog } from "../expressions/ExpressionCatalog";
import type { ExpressionInfo } from "../expressions/ExpressionCatalog";
import { Button } from "../components/Button";

const TEXT_MIN = 20;
const TEXT_MAX = 1200;
const LABEL_MAX = 60;

type TextField = "what_it_is" | "why_it_occurs" | "facial_cues" | "practice_tip" | "limitation_note";
const textFields: { key: TextField; label: string; help: string }[] = [
  { key: "what_it_is", label: "¿Qué es?", help: "Descripción general de la emoción." },
  { key: "why_it_occurs", label: "¿Por qué suele presentarse?", help: "Función y situaciones habituales en las personas en general; nunca sobre quien usa el sistema." },
  { key: "facial_cues", label: "¿Cómo se reconoce en el rostro?", help: "Cejas, ojos, boca y duración típica." },
  { key: "practice_tip", label: "Para practicar", help: "Sugerencia breve para reconocerla o producirla." },
  { key: "limitation_note", label: "Limitación", help: "Incluye cultura, contexto, iluminación y ángulo; habla de «expresión compatible con»." },
];

type Form = Pick<ExpressionInfo, "label_es" | TextField> & { reviewed: boolean };

function toForm(info: ExpressionInfo): Form {
  return {
    label_es: info.label_es, what_it_is: info.what_it_is, why_it_occurs: info.why_it_occurs,
    facial_cues: info.facial_cues, practice_tip: info.practice_tip, limitation_note: info.limitation_note,
    reviewed: info.review_status === "reviewed",
  };
}

export function AdminExpressionsPage() {
  const { token } = useAuth();
  const catalog = useExpressionCatalog();
  const query = useApiQuery<ExpressionInfo[]>("/expressions");
  const items = query.data ?? [];
  const [selectedKey, setSelectedKey] = useState("");
  const [form, setForm] = useState<Form | null>(null);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const selected = items.find((item) => item.expression_key === selectedKey) ?? null;

  function edit(info: ExpressionInfo) {
    setSelectedKey(info.expression_key); setForm(toForm(info)); setMessage(""); setError("");
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!form || !selected) return;
    const label = form.label_es.trim();
    if (!label || label.length > LABEL_MAX) { setError(`La etiqueta debe tener entre 1 y ${LABEL_MAX} caracteres.`); return; }
    const invalid = textFields.find(({ key }) => form[key].trim().length < TEXT_MIN || form[key].trim().length > TEXT_MAX);
    if (invalid) { setError(`«${invalid.label}» debe tener entre ${TEXT_MIN} y ${TEXT_MAX} caracteres.`); return; }
    setSaving(true); setError(""); setMessage("");
    try {
      const { reviewed, ...texts } = form;
      const body = Object.fromEntries(Object.entries(texts).map(([key, value]) => [key, value.trim()]));
      const updated = await apiRequest<ExpressionInfo>(`/expressions/${encodeURIComponent(selected.expression_key)}`, {
        method: "PUT", token, body: JSON.stringify({ ...body, review_status: reviewed ? "reviewed" : "draft" }),
      });
      setMessage(updated.review_status === "reviewed" ? "Texto guardado y marcado como revisado." : "Texto guardado como borrador.");
      setForm(toForm(updated));
      await Promise.all([query.reload(), catalog.reload()]);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "No se pudo guardar el texto");
    } finally { setSaving(false); }
  }

  return <section>
    <PageHeader title="Catálogo de expresiones"
      description="Textos fijos que ve el estudiante tras registrar una expresión. Los revisan profesionales de Psicología; nunca los genera el chatbot." />
    {message && <Callout variant="success">{message}</Callout>}
    {error && <Callout variant="error">{error}</Callout>}
    <PageState {...query} empty={!query.loading && !query.error && items.length === 0} emptyMessage="El catálogo de expresiones está vacío. Revisa que el servidor haya cargado los textos iniciales." onRetry={query.reload} />
    {items.length > 0 && <div className="table-wrap"><table><thead><tr><th>Expresión</th><th>Estado</th><th>Revisado</th><th><span className="sr-only">Acciones</span></th></tr></thead><tbody>
      {items.map((item) => <tr key={item.expression_key}>
        <td>{item.label_es}</td>
        <td><StatusChip tone={item.review_status === "reviewed" ? "success" : "neutral"}>{item.review_status === "reviewed" ? "Revisado" : "Borrador"}</StatusChip></td>
        <td>{item.reviewed_at ? new Date(item.reviewed_at).toLocaleString("es-PE") : "—"}</td>
        <td><Button variant="secondary" type="button" onClick={() => edit(item)} aria-label={`Editar ${item.label_es}`}>Editar</Button></td>
      </tr>)}
    </tbody></table></div>}
    {form && selected && <form className="card form-stack" onSubmit={save} aria-label={`Editar ${selected.label_es}`}>
      <h2>Editar: {selected.label_es}</h2>
      <label>Etiqueta en español<input value={form.label_es} maxLength={LABEL_MAX} required
        onChange={(event) => setForm({ ...form, label_es: event.target.value })} /></label>
      {textFields.map(({ key, label, help }) => <div key={key} className="form-field">
        <label htmlFor={`expression-${key}`}>{label}</label>
        <textarea id={`expression-${key}`} value={form[key]} rows={4} maxLength={TEXT_MAX} required aria-describedby={`help-${key}`}
          onChange={(event) => setForm({ ...form, [key]: event.target.value })} />
        <small id={`help-${key}`} className="muted">{help} {form[key].trim().length}/{TEXT_MAX}</small>
      </div>)}
      <Checkbox checked={form.reviewed}
        onChange={(event) => setForm({ ...form, reviewed: event.target.checked })}>Marcar como revisado por Psicología (se registra quién y cuándo)</Checkbox>
      <p className="muted">Guardar sin marcar deja el texto como borrador y elimina una revisión anterior.</p>
      <div className="inline-actions">
        <Button variant="primary" type="submit" disabled={saving}>{saving ? "Guardando…" : "Guardar"}</Button>
        <Button variant="secondary" type="button" onClick={() => { setForm(null); setSelectedKey(""); }}>Cerrar</Button>
      </div>
    </form>}
  </section>;
}
