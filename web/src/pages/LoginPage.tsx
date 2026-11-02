import { FormEvent, useEffect, useRef, useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError, apiRequest, isConnectionError } from "../api/http";
import type { MfaChallenge, MfaSetup } from "../auth/types";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { ConfirmationCodeField, isConfirmationCode } from "../components/ConfirmationCodeField";

function errorText(reason: unknown) {
  return isConnectionError(reason) ? "No podemos conectar con EMOtv en este momento. Inténtalo más tarde."
    : reason instanceof ApiError ? reason.message : "No se pudo completar el ingreso.";
}

export function LoginPage() {
  const { login, notice, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [challenge, setChallenge] = useState<MfaChallenge | null>(null);

  if (user) return <Navigate to="/dashboard" replace />;

  function enter() {
    const destination = (location.state as { from?: { pathname?: string } } | null)
      ?.from?.pathname ?? "/dashboard";
    navigate(destination, { replace: true });
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      const next = await login(email, password);
      if (next) { setPassword(""); setChallenge(next); } else enter();
    } catch (reason) {
      setError(errorText(reason));
    } finally {
      setSubmitting(false);
    }
  }

  if (challenge) {
    return <SecondFactor challenge={challenge} onDone={enter}
      onRestart={(message) => { setChallenge(null); setError(message); }} />;
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

/** La clave en grupos de cuatro, para copiarla a mano sin perderse. */
function grouped(secret: string) {
  return secret.match(/.{1,4}/g)?.join(" ") ?? secret;
}

/**
 * Segundo paso de superadmin y admin. La primera vez muestra la clave para la
 * aplicación autenticadora (una sola vez); después solo pide el código.
 */
function SecondFactor({ challenge, onDone, onRestart }: {
  challenge: MfaChallenge; onDone(): void; onRestart(message: string): void;
}) {
  const { completeMfa } = useAuth();
  const [setup, setSetup] = useState<MfaSetup | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const configuring = challenge.step === "setup";
  // La clave se pide una sola vez: pedirla de nuevo generaría otra distinta.
  const restart = useRef(onRestart);
  restart.current = onRestart;

  useEffect(() => {
    if (!configuring) return;
    let active = true;
    apiRequest<MfaSetup>("/auth/mfa/setup", { method: "POST", body: JSON.stringify({ mfa_token: challenge.mfaToken }) })
      .then((result) => { if (active) setSetup(result); })
      .catch((reason: unknown) => { if (active) restart.current(errorText(reason)); });
    return () => { active = false; };
  }, [configuring, challenge.mfaToken]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError("");
    try {
      await completeMfa(challenge.mfaToken, code);
      onDone();
    } catch (reason) {
      // El token de paso venció: se vuelve a la contraseña.
      if (reason instanceof ApiError && reason.status === 401 && reason.message.startsWith("El ingreso venció")) {
        onRestart(reason.message);
        return;
      }
      setError(errorText(reason));
      setCode("");
      setSubmitting(false);
    }
  }

  return (
    <main className="login-page">
      <section className="login-card" aria-labelledby="mfa-title">
        <h1 id="mfa-title">{configuring ? "Protege tu cuenta" : "Código de verificación"}</h1>
        {configuring
          ? <>
            <p className="muted">Tu cuenta gestiona otras cuentas, así que además de la contraseña pide un código de una aplicación autenticadora (Google Authenticator, Microsoft Authenticator u otra).</p>
            {!setup ? <p className="muted">Preparando la clave…</p> : <>
              <p>En la aplicación, agrega una cuenta y escribe esta clave (o ábrela desde este enlace en el celular):</p>
              <code className="temporary-secret">{grouped(setup.secret)}</code>
              <p><a href={setup.otpauth_uri}>Abrir en la aplicación autenticadora</a></p>
              <Callout variant="info">La clave solo se muestra ahora. Si pierdes el celular, el soporte técnico deberá reiniciar este paso.</Callout>
            </>}
          </>
          : <p className="muted">Escribe el código de 6 dígitos que muestra ahora tu aplicación autenticadora.</p>}
        <form onSubmit={submit}>
          <ConfirmationCodeField value={code} onChange={setCode} disabled={submitting || (configuring && !setup)} />
          {error && <Callout variant="error">{error}</Callout>}
          <Button variant="primary" type="submit" disabled={submitting || !isConfirmationCode(code)}>
            {submitting ? "Verificando…" : configuring ? "Confirmar y entrar" : "Entrar"}
          </Button>
        </form>
      </section>
    </main>
  );
}
