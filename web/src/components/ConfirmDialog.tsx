import { useEffect, useId, useRef } from "react";
import { createPortal } from "react-dom";

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirming?: boolean;
  confirmLabel?: string;
  onConfirm(): void;
  onCancel(): void;
}

export function ConfirmDialog({ open, title, message, confirming, confirmLabel = "Confirmar", onConfirm, onCancel }: ConfirmDialogProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const actions = useRef({ confirming, onCancel });
  actions.current = { confirming, onCancel };
  const titleId = useId();
  const messageId = useId();
  useEffect(() => {
    if (!open) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const backdrop = dialogRef.current?.parentElement;
    const siblings = Array.from(document.body.children).filter((node) => node !== backdrop) as HTMLElement[];
    const priorInert = siblings.map((node) => node.inert);
    siblings.forEach((node) => { node.inert = true; });
    const priorOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    dialogRef.current?.querySelector<HTMLButtonElement>("button")?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (!actions.current.confirming) actions.current.onCancel();
      }
      if (event.key === "Tab") {
        const buttons = Array.from(dialogRef.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? []);
        if (!buttons.length) { event.preventDefault(); dialogRef.current?.focus(); return; }
        const first = buttons[0]; const last = buttons[buttons.length - 1];
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("keydown", handleKey);
      siblings.forEach((node, index) => { node.inert = priorInert[index]; });
      document.body.style.overflow = priorOverflow;
      if (previousFocus?.isConnected) previousFocus.focus();
    };
  }, [open]);
  if (!open) return null;
  return createPortal(<div className="dialog-backdrop" role="presentation" onMouseDown={() => { if (!confirming) onCancel(); }}>
    <section ref={dialogRef} tabIndex={-1} className="dialog" role="alertdialog" aria-modal="true" aria-labelledby={titleId} aria-describedby={messageId} onMouseDown={(event) => event.stopPropagation()}>
      <h2 id={titleId}>{title}</h2><p id={messageId}>{message}</p>
      <div className="dialog-actions"><button className="button secondary" disabled={confirming} onClick={onCancel}>Cancelar</button><button className="button danger" disabled={confirming} onClick={onConfirm}>{confirming ? "Procesando…" : confirmLabel}</button></div>
    </section>
  </div>, document.body);
}
