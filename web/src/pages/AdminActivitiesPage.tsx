import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError, apiRequest } from "../api/http";
import type { Activity } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Alert } from "../components/Alert";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { PageState } from "../components/PageState";

const emptyForm = { id: "", name: "", description: "", required_posture: "arms_up", duration_seconds: 5, repetitions: 1 };

export function AdminActivitiesPage() {
  const { token } = useAuth();
  const query = useApiQuery<Activity[]>("/activities");
  const [form, setForm] = useState(emptyForm);
  const [editing, setEditing] = useState(false);
  const [selected, setSelected] = useState<Activity | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const activities = query.data ?? [];

  function edit(activity: Activity) {
    setForm(activity); setEditing(true); setMessage(""); setError("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = {
      ...form,
      id: form.id.trim(),
      name: form.name.trim(),
      description: form.description.trim(),
    };
    if (!/^[a-z0-9][a-z0-9_-]*$/.test(normalized.id)) {
      setError("El ID solo puede contener minúsculas, números, guiones y guion bajo.");
      return;
    }
    if (!normalized.name || !normalized.description) {
      setError("El nombre y la descripción no pueden quedar vacíos.");
      return;
    }
    if (normalized.duration_seconds <= 0 || normalized.repetitions < 1) {
      setError("La duración y las repeticiones deben ser mayores que cero.");
      return;
    }
    setSaving(true); setError(""); setMessage("");
    try {
      await apiRequest<Activity>(editing ? `/activities/${encodeURIComponent(normalized.id)}` : "/activities", { method: editing ? "PUT" : "POST", body: JSON.stringify(normalized), token });
      setMessage(editing ? "Actividad actualizada correctamente." : "Actividad creada correctamente.");
      setForm(emptyForm); setEditing(false); await query.reload();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "No se pudo guardar la actividad"); }
    finally { setSaving(false); }
  }

  async function remove() {
    if (!selected) return;
    setDeleting(true); setError("");
    try {
      await apiRequest<void>(`/activities/${encodeURIComponent(selected.id)}`, { method: "DELETE", token });
      setMessage("Actividad eliminada."); setSelected(null); await query.reload();
    } catch (reason) { setError(reason instanceof ApiError ? reason.message : "No se pudo eliminar la actividad"); }
    finally { setDeleting(false); }
  }

  return <section><p className="eyebrow">Administración</p><h1>Administrar actividades</h1><p className="lead">Crea y actualiza las actividades corporales del catálogo local.</p>
    {message && <Alert variant="success">{message}</Alert>}{error && <Alert variant="error">{error}</Alert>}
    <form className="editor card" onSubmit={save}><div className="form-grid"><label>ID<input required maxLength={128} disabled={editing} value={form.id} onChange={(e) => setForm({ ...form, id: e.target.value.toLowerCase() })} /></label><label>Nombre<input required maxLength={200} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label><label className="wide">Descripción<input required maxLength={1000} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></label><label>Postura<select value={form.required_posture} onChange={(e) => setForm({ ...form, required_posture: e.target.value })}><option value="arms_up">Brazos arriba</option><option value="arms_open">Brazos abiertos</option><option value="hands_on_hips">Manos en las caderas</option><option value="arms_forward">Brazos al frente</option><option value="squat">Sentadilla</option></select></label><label>Duración (s)<input type="number" min="0.1" step="0.1" required value={form.duration_seconds} onChange={(e) => setForm({ ...form, duration_seconds: Number(e.target.value) })} /></label><label>Repeticiones<input type="number" min="1" step="1" required value={form.repetitions} onChange={(e) => setForm({ ...form, repetitions: Number(e.target.value) })} /></label></div><div className="inline-actions"><button className="button primary" disabled={saving}>{saving ? "Guardando…" : editing ? "Guardar cambios" : "Crear actividad"}</button>{editing && <button className="button secondary" type="button" onClick={() => { setEditing(false); setForm(emptyForm); }}>Cancelar edición</button>}</div></form>
    <PageState {...query} empty={!query.loading && !query.error && activities.length === 0} onRetry={query.reload} />
    {activities.length > 0 && <div className="table-wrap"><table><thead><tr><th>Actividad</th><th>Postura</th><th>Duración</th><th>Acciones</th></tr></thead><tbody>{activities.map((activity) => <tr key={activity.id}><td><strong>{activity.name}</strong><small>{activity.id}</small></td><td>{activity.required_posture}</td><td>{activity.duration_seconds} s</td><td><div className="inline-actions"><button className="button secondary compact" onClick={() => edit(activity)}>Editar</button><button className="button danger compact" onClick={() => setSelected(activity)}>Eliminar</button></div></td></tr>)}</tbody></table></div>}
    <ConfirmDialog open={selected != null} title="Eliminar actividad" message={`¿Deseas eliminar “${selected?.name ?? ""}”? Esta acción no se puede deshacer.`} confirming={deleting} confirmLabel="Eliminar" onCancel={() => setSelected(null)} onConfirm={remove} />
  </section>;
}
