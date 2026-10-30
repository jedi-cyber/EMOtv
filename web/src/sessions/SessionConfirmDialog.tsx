import { useEffect, useState } from "react";
import type { SessionType } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import type { VersionedText } from "../commitment/CommitmentContext";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { Modal } from "../components/Modal";
import { PolicyDocument } from "../components/PolicyDocument";
import { confirmationTexts } from "./labels";

interface SessionConfirmDialogProps {
  open: boolean;
  audience: SessionType;
  busy?: boolean;
  error?: string;
  onCancel(): void;
  /** childNoticeVersion: la versión del aviso sobre menores, si se aceptó aquí por primera vez. */
  onConfirm(childNoticeVersion?: string): void;
}

/**
 * La única confirmación de una sesión, según con quién es. Antes de la primera
 * sesión con un niño o una niña también se acepta el aviso sobre datos de menores.
 * Sin confirmar no hay sesión (el servidor también lo exige).
 */
export function SessionConfirmDialog({ open, audience, busy = false, error, onCancel, onConfirm }: SessionConfirmDialogProps) {
  const child = audience === "infantil";
  const notice = useApiQuery<VersionedText>(open && child ? "/commitment/child-notice" : null);
  const noticePending = child && notice.data != null && !notice.data.accepted;
  const [confirmed, setConfirmed] = useState(false);
  const [noticeRead, setNoticeRead] = useState(false);
  useEffect(() => { if (open) { setConfirmed(false); setNoticeRead(false); } }, [open, audience]);
  const ready = confirmed && (!noticePending || noticeRead) && !(child && notice.loading);

  return <Modal open={open} title="Antes de empezar" onClose={onCancel} busy={busy}
    footer={<>
      <Button variant="secondary" disabled={busy} onClick={onCancel}>Volver</Button>
      <Button variant="primary" disabled={!ready || busy}
        onClick={() => onConfirm(noticePending ? notice.data?.version : undefined)}>
        {busy ? "Preparando…" : "Empezar la sesión"}
      </Button>
    </>}>
    {error && <Callout variant="error">{error}</Callout>}
    {noticePending && notice.data && <>
      <p>Es tu primera sesión con un niño o una niña. Lee este aviso una vez:</p>
      <div className="confirm-notice"><PolicyDocument content={notice.data.content} skipTitle /></div>
      <Checkbox checked={noticeRead} onChange={(event) => setNoticeRead(event.target.checked)}>Leí el aviso sobre datos de menores</Checkbox>
    </>}
    {child && notice.error && <Callout variant="error">{notice.error}</Callout>}
    <Checkbox checked={confirmed} onChange={(event) => setConfirmed(event.target.checked)}>{confirmationTexts[audience]}</Checkbox>
    <p className="muted">Se confirma una sola vez. La sesión no guarda nombres, DNI ni fotos: lleva un código que verás al empezar y al terminar, para anotarlo en el formato firmado.</p>
  </Modal>;
}
