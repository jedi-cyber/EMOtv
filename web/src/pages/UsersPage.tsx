import { useState } from "react";
import { apiRequest } from "../api/http";
import type { CurrentUser, UserRole } from "../auth/types";
import { useAuth } from "../auth/useAuth";
import { roleNames } from "../auth/roles";
import { useApiQuery } from "../api/useApiQuery";
import { Callout } from "../components/Callout";
import { PageState } from "../components/PageState";
import { PageHeader } from "../components/PageHeader";
import { AssignmentsPanel } from "../components/AssignmentsPanel";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Button } from "../components/Button";

type CreatedUser = CurrentUser & { temporary_password: string | null };

/** Papeles que cada cuenta de gestión puede crear (el servidor aplica la misma regla). */
const creatableRoles: Partial<Record<UserRole, UserRole[]>> = {
  superadmin: ["admin"],
  admin: ["student", "psychologist"],
};

export function UsersPage() {
  const { token, user } = useAuth();
  const isSuperadmin = user?.role === "superadmin";
  const options = creatableRoles[user?.role ?? "student"] ?? [];
  const query = useApiQuery<CurrentUser[]>("/users");
  const users = query.data ?? [];
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<UserRole>(options[0] ?? "student");
  const [code, setCode] = useState("");
  const [created, setCreated] = useState<CreatedUser | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [assigning, setAssigning] = useState<CurrentUser | null>(null);
  const [resetting, setResetting] = useState<CurrentUser | null>(null);
  const [toggling, setToggling] = useState<CurrentUser | null>(null);

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setCreated(null);
    try {
      const result = await apiRequest<CreatedUser>("/users", {
        method: "POST", token,
        body: JSON.stringify({ email: email.trim(), role, ...(role === "student" ? { student_code: code.trim() } : {}) }),
      });
      setCreated(result); setEmail(""); setCode("");
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo crear la cuenta."); }
    finally { setBusy(false); }
  }

  async function resetPassword(item: CurrentUser) {
    setBusy(true); setError(""); setCreated(null);
    try {
      const result = await apiRequest<CreatedUser>(`/users/${encodeURIComponent(item.id)}/reset-password`, { method: "POST", token });
      setCreated(result);
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo restablecer la contraseña."); }
    finally { setBusy(false); setResetting(null); }
  }

  async function toggleActive(item: CurrentUser) {
    setBusy(true); setError("");
    try {
      await apiRequest(`/users/${encodeURIComponent(item.id)}`, { method: "PATCH", token, body: JSON.stringify({ is_active: !item.is_active }) });
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo cambiar el estado de la cuenta."); }
    finally { setBusy(false); setToggling(null); }
  }

  return <section>
    <PageHeader title={isSuperadmin ? "Cuenta de administrador" : "Cuentas y grupos"}
      description={isSuperadmin
        ? "La cuenta de administrador es para la persona con cargo superior en la Facultad. Por defecto solo puede haber una activa."
        : "Crea cuentas de docentes y usuarios, y asigna cada usuario a un docente."} />
    {error && <Callout variant="error">{error}</Callout>}
    <form className="card onboarding-card" onSubmit={(event) => { void create(event); }}>
      <h2>Crear cuenta</h2>
      <p>Se generará una contraseña provisional única. La persona deberá cambiarla en su primer acceso.</p>
      <label>Correo electrónico<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
      {options.length > 1 && <label>Papel<select value={role} onChange={(event) => setRole(event.target.value as UserRole)}>
        {options.map((item) => <option key={item} value={item}>{roleNames[item]}</option>)}
      </select></label>}
      {role === "student" && <label>Código de usuario<input value={code} onChange={(event) => setCode(event.target.value)} required /></label>}
      <Button variant="primary" type="submit" disabled={busy}>{busy ? "Creando…" : `Crear cuenta de ${roleNames[role].toLowerCase()}`}</Button>
    </form>
    {created?.temporary_password && <Callout variant="info">
      Contraseña provisional para {created.email} (solo se muestra ahora):
      <code className="temporary-secret">{created.temporary_password}</code>
      Compártela por un canal seguro. Al ingresar, la persona deberá cambiarla.
      <Button variant="secondary" type="button" onClick={() => setCreated(null)}>Ocultar contraseña</Button>
    </Callout>}
    <PageState {...query} empty={!query.loading && !query.error && users.length === 0} emptyMessage="Todavía no hay cuentas." onRetry={query.reload} />
    {users.length > 0 && <div className="table-wrap"><table><thead><tr><th>Correo</th><th>Papel</th><th>Estado</th><th><span className="sr-only">Acciones</span></th></tr></thead><tbody>
      {users.map((item) => <tr key={item.id}>
        <td>{item.email}</td>
        <td>{roleNames[item.role]}</td>
        <td>{!item.is_active ? "Inactiva" : item.must_change_password ? "Debe cambiar contraseña" : "Activa"}</td>
        <td className="inline-actions">
          <Button variant="secondary" type="button" disabled={busy || !item.is_active} onClick={() => setResetting(item)}>Restablecer clave</Button>
          <Button variant="secondary" type="button" disabled={busy} onClick={() => setToggling(item)}>{item.is_active ? "Desactivar" : "Reactivar"}</Button>
          {item.role === "psychologist" && <Button variant="secondary" type="button" onClick={() => setAssigning(item)}>Grupo</Button>}
        </td>
      </tr>)}
    </tbody></table></div>}
    <ConfirmDialog open={resetting != null} title="Restablecer clave"
      message={`¿Restablecer la contraseña de ${resetting?.email ?? ""}? Se cerrarán sus sesiones, verá un aviso al ingresar y el cambio quedará en la auditoría.`}
      confirming={busy} confirmLabel="Restablecer clave" onCancel={() => setResetting(null)}
      onConfirm={() => { if (resetting) void resetPassword(resetting); }} />
    <ConfirmDialog open={toggling != null} title={toggling?.is_active ? "Desactivar cuenta" : "Reactivar cuenta"}
      message={toggling?.is_active ? `¿Desactivar la cuenta de ${toggling.email}? No podrá ingresar hasta que la reactives.` : `¿Reactivar la cuenta de ${toggling?.email ?? ""}?`}
      confirming={busy} confirmLabel={toggling?.is_active ? "Desactivar" : "Reactivar"} onCancel={() => setToggling(null)}
      onConfirm={() => { if (toggling) void toggleActive(toggling); }} />
    {assigning && <AssignmentsPanel key={assigning.id} psychologist={assigning} onClose={() => setAssigning(null)} />}
  </section>;
}
