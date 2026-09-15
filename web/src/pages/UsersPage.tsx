import type { CurrentUser } from "../auth/types";
import { useApiQuery } from "../api/useApiQuery";
import { PageState } from "../components/PageState";

const roleNames = { student: "Estudiante", psychologist: "Psicología", admin: "Administración" };

export function UsersPage() {
  const query = useApiQuery<CurrentUser[]>("/auth/users");
  const users = query.data ?? [];
  return <section><p className="eyebrow">Administración</p><h1>Usuarios</h1><p className="lead">Cuentas registradas y roles asignados.</p>
    <PageState {...query} empty={!query.loading && !query.error && users.length === 0} onRetry={query.reload} />
    {users.length > 0 && <div className="table-wrap"><table><thead><tr><th>Correo</th><th>Rol</th><th>Estado</th></tr></thead><tbody>{users.map((item) => <tr key={item.id}><td>{item.email}</td><td>{roleNames[item.role]}</td><td>{item.is_active ? "Activo" : "Inactivo"}</td></tr>)}</tbody></table></div>}
  </section>;
}
