import { useState } from "react";
import type { FormEvent } from "react";
import type { AuditEntry } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { roleNames } from "../auth/roles";
import type { UserRole } from "../auth/types";
import { Button } from "../components/Button";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip } from "../components/StatusChip";

const actionNames: Record<string, string> = {
  view: "Consulta", create: "Creación", print: "Impresión", approve: "Aprobación", delete: "Eliminación",
  deletion_request: "Solicitud de eliminación", retention_purge: "Retención automática",
  authorization_change: "Cambio de autorización", password_reset: "Restablecimiento de contraseña",
  group_change: "Cambio de grupo", account_create: "Creación de cuenta", account_deactivate: "Desactivación de cuenta",
  account_reactivate: "Reactivación de cuenta", commitment_accept: "Aceptación del compromiso",
  child_notice_accept: "Aviso sobre menores aceptado", login: "Inicio de sesión en el aplicativo",
  logout: "Cierre de sesión en el aplicativo",
};
const resourceNames: Record<string, string> = {
  participant: "Participante", participant_list: "Lista de participantes", mobile_session: "Sesión del aplicativo",
  mobile_summary: "Resumen del aplicativo", stimulus_image: "Imagen de estímulo", deletion_certificate: "Acta de eliminación",
  user: "Cuenta", student: "Usuario", commitment: "Compromiso", child_notice: "Aviso sobre menores",
};
const resultNames = { success: "Correcto", denied: "Denegado", failure: "Fallido" } as const;

/** Auditoría de accesos: solo consulta, sin contenido ni imágenes. */
export function AuditPage() {
  const [action, setAction] = useState("");
  const [resource, setResource] = useState("");
  const [since, setSince] = useState("");
  const [applied, setApplied] = useState("");
  const query = useApiQuery<AuditEntry[]>(`/audit${applied}`);
  const entries = query.data ?? [];

  function apply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const params = new URLSearchParams();
    if (action) params.set("action", action);
    if (resource) params.set("resource_type", resource);
    if (since) params.set("since", new Date(`${since}T00:00:00`).toISOString());
    setApplied(params.toString() ? `?${params.toString()}` : "");
  }

  return <section>
    <PageHeader title="Auditoría" description="Quién hizo qué, sobre qué recurso y con qué resultado. No contiene notas, respuestas ni imágenes, y nadie puede editarla." />
    <form className="filter-bar" onSubmit={apply}>
      <label>Acción<select value={action} onChange={(event) => setAction(event.target.value)}>
        <option value="">Todas</option>
        {Object.entries(actionNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select></label>
      <label>Recurso<select value={resource} onChange={(event) => setResource(event.target.value)}>
        <option value="">Todos</option>
        {Object.entries(resourceNames).map(([key, label]) => <option key={key} value={key}>{label}</option>)}
      </select></label>
      <label>Desde<input type="date" value={since} onChange={(event) => setSince(event.target.value)} /></label>
      <Button variant="secondary" type="submit">Filtrar</Button>
    </form>
    <PageState {...query} empty={!query.loading && !query.error && entries.length === 0} emptyMessage="No hay registros con estos filtros." onRetry={query.reload} />
    {entries.length > 0 && <div className="table-wrap"><table><thead><tr>
      <th>Fecha</th><th>Quién</th><th>Acción</th><th>Recurso</th><th>Resultado</th>
    </tr></thead><tbody>
      {entries.map((item) => <tr key={item.id}>
        <td>{new Date(item.occurred_at).toLocaleString("es-PE")}</td>
        <td>{item.actor_role ? roleNames[item.actor_role as UserRole] ?? "Cuenta" : "Sistema"}<br /><small className="muted">{item.actor_user_id ?? "Tarea automática"}</small></td>
        <td>{actionNames[item.action] ?? item.action}</td>
        <td>{resourceNames[item.resource_type] ?? item.resource_type}{item.resource_id && <><br /><small className="muted">{item.resource_id}</small></>}</td>
        <td><StatusChip tone={item.result === "success" ? "success" : "error"}>{resultNames[item.result]}</StatusChip></td>
      </tr>)}
    </tbody></table></div>}
  </section>;
}
