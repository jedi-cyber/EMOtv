import { useState } from "react";
import { ApiError, apiRequest } from "../api/http";
import type { AssignedStudent, Student } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import type { CurrentUser } from "../auth/types";
import { useAuth } from "../auth/useAuth";
import { Callout } from "./Callout";
import { PageState } from "./PageState";
import { Button } from "./Button";

interface Props {
  psychologist: CurrentUser;
  onClose(): void;
}

/** Administración elige qué estudiantes puede consultar una cuenta de psicología. */
export function AssignmentsPanel({ psychologist, onClose }: Props) {
  const { token } = useAuth();
  const base = `/users/${encodeURIComponent(psychologist.id)}/assigned-students`;
  const assignedQuery = useApiQuery<AssignedStudent[]>(base);
  const studentsQuery = useApiQuery<Student[]>("/students");
  const [selected, setSelected] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const assigned = assignedQuery.data ?? [];
  const assignedIds = new Set(assigned.map((item) => item.id));
  const available = (studentsQuery.data ?? []).filter((item) => !assignedIds.has(item.id));

  async function change(method: "PUT" | "DELETE", studentId: string) {
    setBusy(true); setError("");
    try {
      await apiRequest(`${base}/${encodeURIComponent(studentId)}`, { method, token });
      if (method === "PUT") setSelected("");
      await assignedQuery.reload();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "No se pudo actualizar la asignación.");
    } finally { setBusy(false); }
  }

  return <section className="card onboarding-card" aria-label={`Estudiantes asignados a ${psychologist.email}`}>
    <h2>Estudiantes asignados a {psychologist.email}</h2>
    <p>Esta cuenta solo podrá consultar las sesiones y consentimientos de los estudiantes asignados.</p>
    {error && <Callout variant="error">{error}</Callout>}
    <PageState {...assignedQuery} empty={!assignedQuery.loading && !assignedQuery.error && assigned.length === 0}
      emptyMessage="Todavía no tiene estudiantes asignados." onRetry={assignedQuery.reload} />
    {assigned.length > 0 && <ul className="card-list">{assigned.map((item) =>
      <li className="card row-card" key={item.id}>
        <strong>{item.student_code}</strong>
        <Button variant="secondary" type="submit" disabled={busy}
          onClick={() => { void change("DELETE", item.id); }}>Quitar {item.student_code}</Button>
      </li>)}</ul>}
    <form className="inline-actions" onSubmit={(event) => { event.preventDefault(); if (selected) void change("PUT", selected); }}>
      <label>Asignar estudiante<select value={selected} onChange={(event) => setSelected(event.target.value)}>
        <option value="">Selecciona un estudiante</option>
        {available.map((item) => <option key={item.id} value={item.id}>{item.student_code}</option>)}
      </select></label>
      <Button variant="primary" type="submit" disabled={busy || !selected}>Asignar</Button>
      <Button variant="secondary" type="button" onClick={onClose}>Cerrar</Button>
    </form>
  </section>;
}
