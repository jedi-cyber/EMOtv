import { useState } from "react";
import { apiRequest } from "../api/http";
import type { Questionnaire } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip } from "../components/StatusChip";
import { QuestionnaireEditor, QuestionnairePreview } from "../questionnaires/QuestionnaireEditor";
import { QuestionnaireNote } from "../questionnaires/QuestionnaireForm";

/** Constructor de cuestionarios para quien conduce la sesión. */
export function QuestionnairesPage() {
  const { token, user } = useAuth();
  const isDocente = user?.role === "psychologist";
  const query = useApiQuery<Questionnaire[]>("/questionnaires");
  const items = query.data ?? [];
  const [editing, setEditing] = useState<Questionnaire | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [preview, setPreview] = useState<Questionnaire | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  function openEditor(item: Questionnaire | null) { setEditing(item); setMessage(""); setError(""); setEditorOpen(true); }

  async function run(action: () => Promise<string>) {
    setBusy(true); setError(""); setMessage("");
    try { setMessage(await action()); await query.reload(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo completar la acción."); }
    finally { setBusy(false); }
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
    {message && <Callout variant="success">{message}</Callout>}
    {error && <Callout variant="error">{error}</Callout>}

    <QuestionnaireEditor open={editorOpen} editing={editing} onClose={() => setEditorOpen(false)}
      onSaved={(_, text) => { setEditorOpen(false); setEditing(null); setMessage(text); void query.reload(); }} />

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
        <div className="inline-actions">
          <Button onClick={() => setPreview(item)}>Vista previa</Button>
          {item.owned_by_me && <Button onClick={() => openEditor(item)}>Editar</Button>}
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

    <QuestionnairePreview questionnaire={preview} onClose={() => setPreview(null)} />
  </section>;
}
