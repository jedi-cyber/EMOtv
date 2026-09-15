import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../api/http";
import { useAuth } from "../auth/useAuth";

export function LoginPage() {
  const { login, notice, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to="/dashboard" replace />;

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await login(email, password);
      const destination = (location.state as { from?: { pathname?: string } } | null)
        ?.from?.pathname ?? "/dashboard";
      navigate(destination, { replace: true });
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "No se pudo conectar con EMOtv");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        <p className="eyebrow">Bienestar y actividades corporales</p>
        <h1 id="login-title">Ingresa a EMOtv</h1>
        <p className="muted">Accede con las credenciales proporcionadas por la institución.</p>
        {notice && <p className="notice" role="status">{notice}</p>}
        <form onSubmit={submit}>
          <label>Correo institucional
            <input type="email" autoComplete="username" required value={email}
              onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label>Contraseña
            <input type="password" autoComplete="current-password" required value={password}
              onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error && <p className="error" role="alert">{error}</p>}
          <button className="button primary" disabled={submitting} type="submit">
            {submitting ? "Ingresando…" : "Ingresar"}
          </button>
        </form>
      </section>
    </main>
  );
}
