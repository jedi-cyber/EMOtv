import { useState } from "react";
import { apiRequest } from "../api/http";
import type { Questionnaire } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { ActionsMenu } from "../components/ActionsMenu";
import type { ActionsMenuItem } from "../components/ActionsMenu";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip } from "../components/StatusChip";
import { QuestionnaireEditor, QuestionnairePreview } from "../questionnaires/QuestionnaireEditor";
import { QuestionnaireNote } from "../questionnaires/QuestionnaireForm";
import { toast } from "../components/Toaster";

/** Constructor de cuestionarios para quien conduce la sesión. */
export function QuestionnairesPage() {
  const { token, user } = useAuth();
  const isDocente = user?.role === "psychologist";
  const query = useApiQuery<Questionnaire[]>("/questionnaires");
  const items = query.data ?? [];
  const [editing, setEditing] = useState<Questionnaire | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [preview, setPreview] = useState<Questionnaire | null>(null);
  const [removing, setRemoving] = useState<Questionnaire | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  function openEditor(item: Questionnaire | null) { setEditing(item); setError(""); setEditorOpen(true); }

  async function run(action: () => Promise<string>) {
    setBusy(true); setError("");
    try { toast.success(await action()); await query.reload(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo completar la acción."); }
    finally { setBusy(false); }
  }

  async function remove() {
    const item = removing;
    if (!item) return;
    await run(async () => {
      await apiRequest(`/questionnaires/${encodeURIComponent(item.id)}`, { method: "DELETE", token });
      return `Se eliminó «${item.title}». Las respuestas de las sesiones se conservan.`;
    });
    setRemoving(null);
  }

  function actions(item: Questionnaire): ActionsMenuItem[] {
    const items: ActionsMenuItem[] = [{ label: "Vista previa", onSelect: () => setPreview(item) }];
    if (item.owned_by_me) items.push({ label: "Editar", onSelect: () => openEditor(item) });
    items.push({
      label: item.owned_by_me ? "Duplicar" : "Copiar y modificar", disabled: busy,
      onSelect: () => { void run(async () => {
        await apiRequest(`/questionnaires/${encodeURIComponent(item.id)}/copy`, { method: "POST", token });
        return `Se agregó una copia de «${item.title}» a tus cuestionarios.`;
      }); },
    });
    if (isDocente && item.owned_by_me) items.push({
      label: item.shared_with_group ? "Dejar de compartir" : "Compartir con mi grupo", disabled: busy,
      onSelect: () => { void run(async () => {
        await apiRequest(`/questionnaires/${encodeURIComponent(item.id)}/share`, { method: "PUT", token, body: JSON.stringify({ shared: !item.shared_with_group }) });
        return item.shared_with_group ? "Tu grupo ya no ve este cuestionario como plantilla." : "Tu grupo puede copiar este cuestionario como plantilla.";
      }); },
    });
    if (item.owned_by_me) items.push({ label: "Eliminar", danger: true, disabled: busy, onSelect: () => setRemoving(item) });
    return items;
  }

  return <section>
    <PageHeader title="Cuestionarios"
      description="Cuestionarios que un protocolo aplica antes o después de las imágenes. EMOtv solo los presenta y registra las respuestas."
      actions={<>
        <Button disabled={busy} onClick={() => { void run(async () => {
          await apiRequest("/questionnaires/starter", { method: "POST", token });
          return "Se agregó una copia de la plantilla inicial a tus cuestionarios. Puedes editarla.";
        }); }}>Usar la plantilla inicial</Button>
        <Button variant="primary" onClick={() => openEditor(null)}>Nuevo cuestionario</Button>
      </>} />
    <p className="muted">La plantilla inicial tiene dos preguntas de caritas: cómo te sientes y qué tan tranquilo o inquieto estás.</p>
    {error && <Callout variant="error">{error}</Callout>}

    <QuestionnaireEditor open={editorOpen} editing={editing} onClose={() => setEditorOpen(false)}
      onSaved={(_, text) => { setEditorOpen(false); setEditing(null); toast.success(text); void query.reload(); }} />

    <PageState {...query} empty={!query.loading && !query.error && items.length === 0}
      emptyMessage="Todavía no tienes cuestionarios. Crea uno o usa la plantilla inicial." onRetry={query.reload}
      emptyAction={<Button variant="primary" onClick={() => openEditor(null)}>Nuevo cuestionario</Button>} />
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
        <ActionsMenu name={item.title} items={actions(item)} />
      </div>
      <QuestionnaireNote />
    </li>)}</ul>}

    <QuestionnairePreview questionnaire={preview} onClose={() => setPreview(null)} />
    <ConfirmDialog open={removing !== null} title="Eliminar cuestionario" confirmLabel="Eliminar" confirming={busy}
      message={removing ? `Se eliminará «${removing.title}» de tus cuestionarios. Las respuestas de las sesiones que lo aplicaron se conservan. Si un protocolo lo usa, primero quítalo de ese protocolo.` : ""}
      onConfirm={() => { void remove(); }} onCancel={() => setRemoving(null)} />
  </section>;
}
