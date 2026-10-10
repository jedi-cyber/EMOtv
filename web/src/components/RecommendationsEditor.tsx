import { useState } from "react";
import { ApiError, apiRequest } from "../api/http";
import type { Activity } from "../api/types";
import { useAuth } from "../auth/useAuth";
import { useExpressionCatalog } from "../expressions/ExpressionCatalog";
import { Callout } from "./Callout";
import { Button } from "./Button";

export interface ExpressionRecommendation {
  expression_key: string;
  activity_ids: string[];
}

// Una recomendación automática siempre tiene dos o más posturas (CLAUDE.md).
export const MIN_RECOMMENDED_STEPS = 2;

function stepCount(activity: Activity) {
  return activity.steps?.length || 1;
}

interface Props {
  recommendations: ExpressionRecommendation[];
  activities: Activity[];
  onSaved: () => Promise<void> | void;
}

/** Edición de qué actividades se recomiendan para cada expresión, en orden de prioridad. */
export function RecommendationsEditor({ recommendations, activities, onSaved }: Props) {
  const { token } = useAuth();
  const { label } = useExpressionCatalog();
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [draft, setDraft] = useState<string[]>([]);
  const [toAdd, setToAdd] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const byId = new Map(activities.map((activity) => [activity.id, activity]));
  const eligible = activities.filter((activity) => stepCount(activity) >= MIN_RECOMMENDED_STEPS && !draft.includes(activity.id));

  function name(activityId: string) {
    return byId.get(activityId)?.name ?? activityId;
  }

  function startEdit(item: ExpressionRecommendation) {
    setEditingKey(item.expression_key); setDraft(item.activity_ids); setToAdd(""); setMessage(""); setError("");
  }

  function move(index: number, offset: number) {
    const next = [...draft];
    const [item] = next.splice(index, 1);
    next.splice(index + offset, 0, item);
    setDraft(next);
  }

  async function save() {
    if (!editingKey) return;
    setSaving(true); setError(""); setMessage("");
    try {
      await apiRequest<ExpressionRecommendation>(`/recommendations/${encodeURIComponent(editingKey)}`, {
        method: "PUT", token, body: JSON.stringify({ activity_ids: draft }),
      });
      setMessage(`Recomendaciones de ${label(editingKey)} guardadas.`);
      setEditingKey(null);
      await onSaved();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "No se pudieron guardar las recomendaciones");
    } finally { setSaving(false); }
  }

  return <section className="card recommendations-editor" aria-labelledby="recommendations-title">
    <h2 id="recommendations-title">Actividades recomendadas por expresión</h2>
    <p className="muted">El orden es la prioridad. Solo se pueden recomendar actividades con al menos {MIN_RECOMMENDED_STEPS} posturas.
      Si una expresión queda sin actividades, el estudiante elige de la lista completa. Estas asociaciones no son una recomendación clínica y deben revisarlas profesionales de Psicología.</p>
    {message && <Callout variant="success">{message}</Callout>}
    {error && <Callout variant="error">{error}</Callout>}
    <div className="table-wrap"><table><thead><tr><th>Expresión</th><th>Actividades (en orden)</th><th><span className="sr-only">Acciones</span></th></tr></thead><tbody>
      {recommendations.map((item) => <tr key={item.expression_key}>
        <td>{label(item.expression_key)}</td>
        <td>{item.activity_ids.length ? item.activity_ids.map(name).join(" → ") : <span className="muted">Sin recomendación automática</span>}</td>
        <td><Button variant="secondary" size="sm" type="button" onClick={() => startEdit(item)} aria-label={`Editar recomendaciones de ${label(item.expression_key)}`}>Editar</Button></td>
      </tr>)}
    </tbody></table></div>
    {editingKey && <div className="form-stack" role="group" aria-label={`Recomendaciones de ${label(editingKey)}`}>
      <h3>Recomendaciones de {label(editingKey)}</h3>
      {draft.length === 0 ? <p className="muted">Sin actividades: no habrá recomendación automática.</p>
        : <ol className="recommendation-order">{draft.map((activityId, index) => <li key={activityId}>
          <span>{name(activityId)}</span>
          <div className="inline-actions">
            <Button variant="secondary" size="sm" type="button" disabled={index === 0} onClick={() => move(index, -1)} aria-label={`Subir ${name(activityId)}`}>↑</Button>
            <Button variant="secondary" size="sm" type="button" disabled={index === draft.length - 1} onClick={() => move(index, 1)} aria-label={`Bajar ${name(activityId)}`}>↓</Button>
            <Button variant="danger" size="sm" type="button" onClick={() => setDraft(draft.filter((id) => id !== activityId))} aria-label={`Quitar ${name(activityId)}`}>Quitar</Button>
          </div>
        </li>)}</ol>}
      {eligible.length > 0 && <div className="inline-actions">
        <label htmlFor="recommendation-add">Añadir actividad</label>
        <select id="recommendation-add" value={toAdd} onChange={(event) => setToAdd(event.target.value)}>
          <option value="">Selecciona…</option>
          {eligible.map((activity) => <option key={activity.id} value={activity.id}>{activity.name}</option>)}
        </select>
        <Button variant="secondary" type="button" disabled={!toAdd} onClick={() => { setDraft([...draft, toAdd]); setToAdd(""); }}>Añadir</Button>
      </div>}
      <div className="inline-actions">
        <Button variant="primary" type="button" disabled={saving} onClick={() => { void save(); }}>{saving ? "Guardando…" : "Guardar recomendaciones"}</Button>
        <Button variant="secondary" type="button" onClick={() => setEditingKey(null)}>Cancelar</Button>
      </div>
    </div>}
  </section>;
}
