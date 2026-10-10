import { useState } from "react";
import { apiRequest } from "../api/http";
import type { CurrentUser, UserRole } from "../auth/types";
import { useAuth } from "../auth/useAuth";
import { useApiQuery } from "../api/useApiQuery";
import { Callout } from "../components/Callout";
import { PageState } from "../components/PageState";
import { PageHeader } from "../components/PageHeader";
import { AssignmentsPanel } from "../components/AssignmentsPanel";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Button } from "../components/Button";

const roleNames = { student: "Estudiante", psychologist: "Psicología", admin: "Administración" };
type CreatedUser = CurrentUser & { temporary_password: string | null };

export function UsersPage() {
  const { token } = useAuth();
  const query = useApiQuery<CurrentUser[]>("/auth/users");
  const users = query.data ?? [];
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<UserRole>("student");
  const [studentCode, setStudentCode] = useState("");
  const [created, setCreated] = useState<CreatedUser | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [assigning, setAssigning] = useState<CurrentUser | null>(null);
  const [resetting, setResetting] = useState<CurrentUser | null>(null);

  async function create(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(""); setCreated(null);
    try {
      const result = await apiRequest<CreatedUser>("/users", {
        method: "POST", token,
        body: JSON.stringify({ email: email.trim(), role,
          ...(role === "student" ? { student_code: studentCode.trim() } : {}) }),
      });
      setCreated(result); setEmail(""); setStudentCode("");
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo crear la cuenta."); }
    finally { setBusy(false); }
  }

  async function resetPassword(item: CurrentUser) {
    setBusy(true); setError(""); setCreated(null);
    try {
      const result = await apiRequest<CreatedUser>(`/users/${encodeURIComponent(item.id)}/reset-password`,
        { method: "POST", token });
      setCreated(result);
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo restablecer la contraseña."); }
    finally { setBusy(false); setResetting(null); }
  }

  return <section><PageHeader title="Usuarios" description="Crea cuentas y consulta sus roles." />
    {error && <Callout variant="error">{error}</Callout>}
    <form className="card onboarding-card" onSubmit={(event) => { void create(event); }}>
      <h2>Crear cuenta</h2>
      <p>Se generará una contraseña provisional única. La persona deberá cambiarla en su primer acceso.</p>
      <label>Correo electrónico<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
      <label>Rol<select value={role} onChange={(event) => setRole(event.target.value as UserRole)}>
        <option value="student">Estudiante</option><option value="psychologist">Psicología</option><option value="admin">Administración</option>
      </select></label>
      {role === "student" && <label>Código de estudiante<input value={studentCode} onChange={(event) => setStudentCode(event.target.value)} required /></label>}
      <Button variant="primary" type="submit" disabled={busy}>{busy ? "Creando…" : "Crear cuenta"}</Button>
    </form>
    {created?.temporary_password && <Callout variant="info">
      Cuenta creada para {created.email}. Contraseña provisional (solo se muestra ahora):
      <code className="temporary-secret">{created.temporary_password}</code>
      Compártela por un canal seguro. El consentimiento lo decidirá el estudiante al ingresar.
      <Button variant="secondary" type="submit" onClick={() => setCreated(null)}>Ocultar contraseña</Button>
    </Callout>}
    <PageState {...query} empty={!query.loading && !query.error && users.length === 0} onRetry={query.reload} />
    {users.length > 0 && <div className="table-wrap"><table><thead><tr><th>Correo</th><th>Rol</th><th>Estado</th><th>Acción</th></tr></thead><tbody>{users.map((item) => <tr key={item.id}><td>{item.email}</td><td>{roleNames[item.role]}</td><td>{item.must_change_password ? "Debe cambiar contraseña" : item.is_active ? "Activo" : "Inactivo"}</td><td className="inline-actions"><Button variant="secondary" type="submit" disabled={busy} onClick={() => setResetting(item)}>Restablecer clave</Button>{item.role === "psychologist" && <Button variant="secondary" type="submit" onClick={() => setAssigning(item)}>Estudiantes asignados</Button>}</td></tr>)}</tbody></table></div>}
    <ConfirmDialog open={resetting != null} title="Restablecer clave"
      message={`¿Restablecer la contraseña de ${resetting?.email ?? ""}? Cerrará sus sesiones activas.`}
      confirming={busy} confirmLabel="Restablecer clave" onCancel={() => setResetting(null)}
      onConfirm={() => { if (resetting) void resetPassword(resetting); }} />
    {assigning && <AssignmentsPanel key={assigning.id} psychologist={assigning} onClose={() => setAssigning(null)} />}
  </section>;
}
