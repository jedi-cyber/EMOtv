import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";

const FOCUSABLE = 'a[href], button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])';

interface ModalProps {
  open: boolean;
  title: string;
  onClose(): void;
  children: ReactNode;
  /** Acciones del pie, a la derecha: secundaria primero y principal al final. */
  footer?: ReactNode;
  /** Con una acción en curso no se cierra con Escape, con el fondo ni con el botón de cerrar. */
  busy?: boolean;
  role?: "dialog" | "alertdialog";
  describedBy?: string;
}

/**
 * Diálogo modal accesible: el foco pasa al título al abrirse, no sale del
 * modal mientras está abierto y vuelve al elemento que lo abrió al cerrarse.
 */
export function Modal({ open, title, onClose, children, footer, busy = false, role = "dialog", describedBy }: ModalProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const titleRef = useRef<HTMLHeadingElement>(null);
  const latest = useRef({ busy, onClose });
  latest.current = { busy, onClose };
  const titleId = useId();

  useEffect(() => {
    if (!open) return;
    const previousFocus = document.activeElement as HTMLElement | null;
    const backdrop = dialogRef.current?.parentElement;
    const siblings = Array.from(document.body.children).filter((node) => node !== backdrop) as HTMLElement[];
    const priorInert = siblings.map((node) => node.inert);
    siblings.forEach((node) => { node.inert = true; });
    const priorOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    titleRef.current?.focus();
    const handleKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        if (!latest.current.busy) latest.current.onClose();
        return;
      }
      if (event.key !== "Tab") return;
      const items = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE) ?? []);
      event.preventDefault();
      if (!items.length) { titleRef.current?.focus(); return; }
      const index = items.indexOf(document.activeElement as HTMLElement);
      const next = event.shiftKey
        ? (index <= 0 ? items[items.length - 1] : items[index - 1])
        : (index === -1 || index === items.length - 1 ? items[0] : items[index + 1]);
      next.focus();
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
  return createPortal(<div className="modal-backdrop" role="presentation" onMouseDown={() => { if (!busy) onClose(); }}>
    <section ref={dialogRef} className="modal" role={role} aria-modal="true" aria-labelledby={titleId}
      aria-describedby={describedBy} onMouseDown={(event) => event.stopPropagation()}>
      <header className="modal-header">
        <h2 ref={titleRef} id={titleId} tabIndex={-1}>{title}</h2>
        <button type="button" className="modal-close" aria-label="Cerrar" disabled={busy} onClick={onClose}>
          <svg aria-hidden="true" focusable="false" viewBox="0 0 20 20" fill="none"><path d="m5 5 10 10M15 5 5 15" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
        </button>
      </header>
      <div className="modal-body">{children}</div>
      {footer && <footer className="modal-footer">{footer}</footer>}
    </section>
  </div>, document.body);
}
