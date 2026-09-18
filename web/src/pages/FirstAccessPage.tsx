import { useState } from "react";
import { Navigate, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { Alert } from "../components/Alert";
import { paths } from "../routes/paths";

export function FirstAccessPage() {
  const { user, changePassword, logout } = useAuth();
  const navigate = useNavigate();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  if (!user?.must_change_password) return <Navigate to={paths.dashboard} replace />;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (next.length < 12) { setError("Usa una contraseña de al menos 12 caracteres."); return; }
    if (next !== repeat) { setError("Las contraseñas nuevas no coinciden."); return; }
    setBusy(true); setError("");
    try {
      await changePassword(current, next);
      navigate(user?.role === "student" ? paths.consent : paths.dashboard, { replace: true });
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo cambiar la contraseña.");
    } finally { setBusy(false); }
  }

  return <main className="centered"><section className="card onboarding-card">
    <h1>Protege tu cuenta</h1>
    <p>Esta cuenta tiene una contraseña provisional. Cámbiala antes de continuar.</p>
    {error && <Alert variant="error">{error}</Alert>}
    <form onSubmit={(event) => { void submit(event); }}>
      <label>Contraseña provisional<input type="password" autoComplete="current-password" value={current} onChange={(event) => setCurrent(event.target.value)} required /></label>
      <label>Contraseña nueva<input type="password" autoComplete="new-password" value={next} onChange={(event) => setNext(event.target.value)} minLength={12} required /></label>
      <label>Repite la contraseña nueva<input type="password" autoComplete="new-password" value={repeat} onChange={(event) => setRepeat(event.target.value)} required /></label>
      <button className="button primary" disabled={busy}>{busy ? "Guardando…" : "Cambiar contraseña"}</button>
    </form>
    <button className="button secondary" onClick={() => logout()}>Cerrar sesión</button>
  </section></main>;
}
