import { useState } from "react";
import { apiRequest } from "../api/http";
import type { CurrentUser, UserRole } from "../auth/types";
import { useAuth } from "../auth/useAuth";
import { useApiQuery } from "../api/useApiQuery";
import { Alert } from "../components/Alert";
import { PageState } from "../components/PageState";
import { PageHeader } from "../components/PageHeader";

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
    if (!window.confirm(`¿Restablecer la contraseña de ${item.email}? Cerrará sus sesiones activas.`)) return;
    setBusy(true); setError(""); setCreated(null);
    try {
      const result = await apiRequest<CreatedUser>(`/users/${encodeURIComponent(item.id)}/reset-password`,
        { method: "POST", token });
      setCreated(result);
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo restablecer la contraseña."); }
    finally { setBusy(false); }
  }

  return <section><PageHeader section="Administración" title="Usuarios" description="Crea cuentas y consulta sus roles." />
    {error && <Alert variant="error">{error}</Alert>}
    <form className="card onboarding-card" onSubmit={(event) => { void create(event); }}>
      <h2>Crear cuenta</h2>
      <p>Se generará una contraseña provisional única. La persona deberá cambiarla en su primer acceso.</p>
      <label>Correo electrónico<input type="email" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
      <label>Rol<select value={role} onChange={(event) => setRole(event.target.value as UserRole)}>
        <option value="student">Estudiante</option><option value="psychologist">Psicología</option><option value="admin">Administración</option>
      </select></label>
      {role === "student" && <label>Código de estudiante<input value={studentCode} onChange={(event) => setStudentCode(event.target.value)} required /></label>}
      <button className="button primary" disabled={busy}>{busy ? "Creando…" : "Crear cuenta"}</button>
    </form>
    {created?.temporary_password && <Alert variant="info">
      Cuenta creada para {created.email}. Contraseña provisional (solo se muestra ahora):
      <code className="temporary-secret">{created.temporary_password}</code>
      Compártela por un canal seguro. El consentimiento lo decidirá el estudiante al ingresar.
      <button className="button secondary" onClick={() => setCreated(null)}>Ocultar contraseña</button>
    </Alert>}
    <PageState {...query} empty={!query.loading && !query.error && users.length === 0} onRetry={query.reload} />
    {users.length > 0 && <div className="table-wrap"><table><thead><tr><th>Correo</th><th>Rol</th><th>Estado</th><th>Acción</th></tr></thead><tbody>{users.map((item) => <tr key={item.id}><td>{item.email}</td><td>{roleNames[item.role]}</td><td>{item.must_change_password ? "Debe cambiar contraseña" : item.is_active ? "Activo" : "Inactivo"}</td><td><button className="button secondary" disabled={busy} onClick={() => { void resetPassword(item); }}>Restablecer clave</button></td></tr>)}</tbody></table></div>}
  </section>;
}
