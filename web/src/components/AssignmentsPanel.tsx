import { useState } from "react";
import { ApiError, apiRequest } from "../api/http";
import type { AssignedStudent, Student } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import type { CurrentUser } from "../auth/types";
import { useAuth } from "../auth/useAuth";
import { Callout } from "./Callout";
import { PageState } from "./PageState";
import { Button } from "./Button";
import { Checkbox } from "./Checkbox";
import { Modal } from "./Modal";

interface Props {
  psychologist: CurrentUser;
  /** Cuentas que ya lista la página, para mostrar el correo de cada usuario. */
  accounts: CurrentUser[];
  onClose(): void;
}

/** El administrador arma el grupo de un docente. Un usuario tiene un solo docente:
 * agregarlo aquí lo mueve si estaba en otro grupo, y el cambio queda en la auditoría. */
export function AssignmentsPanel({ psychologist, accounts, onClose }: Props) {
  const { token } = useAuth();
  const base = `/users/${encodeURIComponent(psychologist.id)}/assigned-students`;
  const assignedQuery = useApiQuery<AssignedStudent[]>(base);
  const studentsQuery = useApiQuery<Student[]>("/students");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [filter, setFilter] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const emails = new Map(accounts.map((item) => [item.id, item.email]));
  const label = (item: Student) => emails.get(item.user_id) ?? item.student_code;
  const assigned = assignedQuery.data ?? [];
  const assignedIds = new Set(assigned.map((item) => item.id));
  const available = (studentsQuery.data ?? []).filter((item) => !assignedIds.has(item.id));
  const term = filter.trim().toLowerCase();
  const visible = term
    ? available.filter((item) => `${label(item)} ${item.student_code}`.toLowerCase().includes(term))
    : available;
  const allVisibleSelected = visible.length > 0 && visible.every((item) => selected.has(item.id));

  function toggle(ids: string[], checked: boolean) {
    setSelected((current) => {
      const next = new Set(current);
      ids.forEach((id) => { if (checked) next.add(id); else next.delete(id); });
      return next;
    });
  }

  async function assign() {
    setBusy(true); setError("");
    const failed: Student[] = [];
    // Una petición por usuario: el servidor valida y audita cada asignación por separado.
    for (const item of available.filter((student) => selected.has(student.id))) {
      try {
        await apiRequest(`${base}/${encodeURIComponent(item.id)}`, { method: "PUT", token });
      } catch {
        failed.push(item);
      }
    }
    // Quedan marcados solo los que fallaron, para reintentarlos.
    setSelected(new Set(failed.map((item) => item.id)));
    if (failed.length) setError(`No se pudo asignar a: ${failed.map(label).join(", ")}.`);
    await assignedQuery.reload();
    setBusy(false);
  }

  async function remove(studentId: string) {
    setBusy(true); setError("");
    try {
      await apiRequest(`${base}/${encodeURIComponent(studentId)}`, { method: "DELETE", token });
      await assignedQuery.reload();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "No se pudo actualizar el grupo.");
    } finally { setBusy(false); }
  }

  const count = available.filter((item) => selected.has(item.id)).length;
  return <Modal open title={`Grupo de ${psychologist.email}`} onClose={onClose} busy={busy}
    footer={<>
      <Button variant="secondary" type="button" disabled={busy} onClick={onClose}>Cerrar</Button>
      <Button variant="primary" type="button" disabled={busy || count === 0} onClick={() => { void assign(); }}>
        {busy ? "Asignando…" : count > 0 ? `Asignar ${count} ${count === 1 ? "usuario" : "usuarios"}` : "Asignar"}
      </Button>
    </>}>
    <div className="form-stack">
      <p>El docente verá los participantes y resultados de los usuarios de su grupo. Si eliges un usuario que ya tiene otro docente, pasará a este grupo.</p>
      {error && <Callout variant="error">{error}</Callout>}
      <h3>En el grupo</h3>
      <PageState {...assignedQuery} empty={!assignedQuery.loading && !assignedQuery.error && assigned.length === 0}
        emptyMessage="Todavía no tiene usuarios en su grupo." onRetry={assignedQuery.reload} />
      {assigned.length > 0 && <ul className="card-list">{assigned.map((item) =>
        <li className="card row-card" key={item.id}>
          <div><strong>{label(item)}</strong><span>{item.student_code}</span></div>
          <Button variant="secondary" size="sm" type="button" disabled={busy} aria-label={`Quitar ${label(item)}`}
            onClick={() => { void remove(item.id); }}>Quitar</Button>
        </li>)}</ul>}
      <fieldset>
        <legend>Agregar usuarios</legend>
        {available.length === 0
          ? <p className="muted">No hay más usuarios para agregar.</p>
          : <div className="form-stack">
            <label>Buscar por correo o código<input type="search" value={filter} onChange={(event) => setFilter(event.target.value)} /></label>
            <Checkbox checked={allVisibleSelected} disabled={busy || visible.length === 0}
              onChange={(event) => toggle(visible.map((item) => item.id), event.target.checked)}>
              Seleccionar {term ? "los resultados" : "todos"}
            </Checkbox>
            {visible.length === 0 && <p className="muted">Ningún usuario coincide con la búsqueda.</p>}
            {visible.map((item) => <Checkbox key={item.id} checked={selected.has(item.id)} disabled={busy}
              onChange={(event) => toggle([item.id], event.target.checked)}>
              {label(item)} <span className="muted">({item.student_code})</span>
            </Checkbox>)}
          </div>}
      </fieldset>
    </div>
  </Modal>;
}
