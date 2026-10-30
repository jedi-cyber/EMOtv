import { useState } from "react";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { Modal } from "../components/Modal";
import { PolicyDocument } from "../components/PolicyDocument";
import { useCommitment } from "./CommitmentContext";

/** El compromiso de confidencialidad se acepta una vez, en esta ventana, al entrar. */
export function CommitmentModal() {
  const { logout } = useAuth();
  const { text, accept } = useCommitment();
  const [read, setRead] = useState(false);
  const [busy, setBusy] = useState(false);
  const [failure, setFailure] = useState("");
  if (!text) return null;

  async function submit() {
    if (!text) return;
    setBusy(true); setFailure("");
    try {
      await accept(text.version);
    } catch (reason) {
      setFailure(reason instanceof Error ? reason.message : "No se pudo registrar la aceptación.");
    } finally { setBusy(false); }
  }

  return <Modal open title="Compromiso de confidencialidad" onClose={() => undefined} dismissible={false} busy={busy}
    footer={<>
      <Button variant="secondary" disabled={busy} onClick={() => logout()}>Salir</Button>
      <Button variant="primary" disabled={!read || busy} onClick={() => { void submit(); }}>
        {busy ? "Registrando…" : "Aceptar el compromiso"}
      </Button>
    </>}>
    <p>Léelo y acéptalo una vez para iniciar sesiones. Si cambia su versión, se te pedirá de nuevo.</p>
    {text.provisional && <Callout variant="warning">Texto provisional: está pendiente de la revisión de la Facultad.</Callout>}
    {failure && <Callout variant="error">{failure}</Callout>}
    <PolicyDocument content={text.content} skipTitle />
    <Checkbox checked={read} onChange={(event) => setRead(event.target.checked)}>Leí el compromiso y me comprometo a cumplirlo</Checkbox>
    <p className="muted">Tu aceptación queda registrada en la auditoría con la versión del texto.</p>
  </Modal>;
}
