import { useState } from "react";
import { Navigate, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { isConductor } from "../auth/roles";
import { useCommitment } from "../commitment/CommitmentContext";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { PageHeader } from "../components/PageHeader";
import { PolicyDocument } from "../components/PolicyDocument";
import { Spinner } from "../components/Spinner";
import { paths } from "../routes/paths";

export function CommitmentPage() {
  const { user } = useAuth();
  const { state, text, error, accept } = useCommitment();
  const navigate = useNavigate();
  const location = useLocation();
  const [read, setRead] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  if (!isConductor(user?.role)) return <Navigate to={paths.dashboard} replace />;
  if (state === "loading" || !text) return <section><Spinner label="Cargando el compromiso" />{error && <Callout variant="error">{error}</Callout>}</section>;
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname;

  async function submit() {
    if (!text) return;
    setBusy(true); setFailure("");
    try {
      await accept(text.version);
      navigate(from && from !== paths.commitment ? from : user?.role === "student" ? paths.consent : paths.dashboard, { replace: true });
    } catch (reason) {
      setFailure(reason instanceof Error ? reason.message : "No se pudo registrar la aceptación.");
    } finally { setBusy(false); }
  }

  return <section>
    <PageHeader title="Compromiso de confidencialidad"
      description={state === "accepted" ? "Ya aceptaste la versión vigente. Puedes volver a leerla cuando quieras." : "Léelo y acéptalo para registrar participantes e iniciar sesiones. Si cambia su versión, se te pedirá de nuevo."} />
    {text.provisional && <Callout variant="warning">Texto provisional: está pendiente de la revisión de la Facultad.</Callout>}
    {failure && <Callout variant="error">{failure}</Callout>}
    <article className="card"><PolicyDocument content={text.content} skipTitle /></article>
    {state === "required" && <div className="card form-stack">
      <Checkbox checked={read} onChange={(event) => setRead(event.target.checked)}>Leí el compromiso y me comprometo a cumplirlo</Checkbox>
      <p className="muted">Tu aceptación queda registrada en la auditoría con la versión del texto.</p>
      <Button variant="primary" disabled={!read || busy} onClick={() => { void submit(); }}>{busy ? "Registrando…" : "Aceptar el compromiso"}</Button>
    </div>}
  </section>;
}
