import { useId } from "react";
import { Button } from "./Button";
import type { ButtonVariant } from "./Button";
import { Modal } from "./Modal";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirming?: boolean;
  confirmLabel?: string;
  /** "danger" por defecto; "primary" cuando la acción no destruye nada. */
  confirmVariant?: ButtonVariant;
  onConfirm(): void;
  onCancel(): void;
}

/** Confirmación de una acción (por defecto, destructiva) sobre el Modal compartido. */
export function ConfirmDialog({ open, title, message, confirming = false, confirmLabel = "Confirmar", confirmVariant = "danger", onConfirm, onCancel }: ConfirmDialogProps) {
  const messageId = useId();
  return <Modal open={open} title={title} onClose={onCancel} busy={confirming} role="alertdialog" describedBy={messageId}
    footer={<>
      <Button variant="secondary" disabled={confirming} onClick={onCancel}>Cancelar</Button>
      <Button variant={confirmVariant} disabled={confirming} onClick={onConfirm}>{confirming ? "Procesando…" : confirmLabel}</Button>
    </>}>
    <p id={messageId}>{message}</p>
  </Modal>;
}
