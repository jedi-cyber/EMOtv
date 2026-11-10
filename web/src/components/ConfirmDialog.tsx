import { useId } from "react";
import type { ReactNode } from "react";
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
  /** Campos adicionales bajo el mensaje (por ejemplo, el código de confirmación). */
  children?: ReactNode;
  confirmDisabled?: boolean;
  onConfirm(): void;
  onCancel(): void;
}

/** Confirmación de una acción (por defecto, destructiva) sobre el Modal compartido. */
export function ConfirmDialog({ open, title, message, confirming = false, confirmLabel = "Confirmar", confirmVariant = "danger", children, confirmDisabled = false, onConfirm, onCancel }: ConfirmDialogProps) {
  const messageId = useId();
  return <Modal open={open} title={title} onClose={onCancel} busy={confirming} role="alertdialog" describedBy={messageId}
    footer={<>
      <Button variant="secondary" disabled={confirming} onClick={onCancel}>Cancelar</Button>
      <Button variant={confirmVariant} disabled={confirming || confirmDisabled} onClick={onConfirm}>{confirming ? "Procesando…" : confirmLabel}</Button>
    </>}>
    <p id={messageId}>{message}</p>
    {children}
  </Modal>;
}
