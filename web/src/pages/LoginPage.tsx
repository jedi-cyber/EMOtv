import { FormEvent, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError, isConnectionError } from "../api/http";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";

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
      setError(isConnectionError(reason) ? "No podemos conectar con EMOtv en este momento. Inténtalo más tarde."
        : reason instanceof ApiError ? reason.message : "No se pudo completar el ingreso.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="login-title">
        
        <h1 id="login-title">Ingresa a EMOtv</h1>
        <p className="muted">Accede con las credenciales proporcionadas por la institución.</p>
        {notice && <Callout variant="info">{notice}</Callout>}
        <form onSubmit={submit}>
          <label>Correo institucional
            <input type="email" autoComplete="username" required value={email}
              onChange={(event) => setEmail(event.target.value)} />
          </label>
          <label>Contraseña
            <input type="password" autoComplete="current-password" required value={password}
              onChange={(event) => setPassword(event.target.value)} />
          </label>
          {error && <Callout variant="error">{error}</Callout>}
          <Button variant="primary" disabled={submitting} type="submit">
            {submitting ? "Ingresando…" : "Ingresar"}
          </Button>
        </form>
      </section>
    </main>
  );
}
