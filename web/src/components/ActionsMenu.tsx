import { useEffect, useId, useRef, useState } from "react";

export interface ActionsMenuItem {
  label: string;
  onSelect(): void;
  /** Acción destructiva (Eliminar): se muestra en rojo y al final. */
  danger?: boolean;
  disabled?: boolean;
}

interface ActionsMenuProps {
  /** Nombre de lo que se gestiona, para el lector de pantalla: «Más acciones para «X»». */
  name: string;
  items: ActionsMenuItem[];
}

/** Botón de tres puntos que despliega las acciones de un elemento de una lista. */
export function ActionsMenu({ name, items }: ActionsMenuProps) {
  const [open, setOpen] = useState(false);
  // Si el botón queda cerca del borde izquierdo (pantallas angostas), el menú se abre hacia la derecha.
  const [alignStart, setAlignStart] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const panelId = useId();

  useEffect(() => {
    if (!open) return;
    const panelWidth = panelRef.current?.offsetWidth ?? 0;
    setAlignStart((rootRef.current?.getBoundingClientRect().right ?? panelWidth) < panelWidth);
    panelRef.current?.querySelector<HTMLButtonElement>("button:not(:disabled)")?.focus();
    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setOpen(false);
        triggerRef.current?.focus();
      }
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  function move(event: React.KeyboardEvent<HTMLDivElement>) {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const buttons = [...(panelRef.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? [])];
    if (!buttons.length) return;
    const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
    const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1
      : (current + (event.key === "ArrowDown" ? 1 : -1) + buttons.length) % buttons.length;
    buttons[next].focus();
  }

  return <div className="actions-menu" ref={rootRef}>
    <button ref={triggerRef} type="button" className="actions-menu-trigger" aria-label={`Más acciones para «${name}»`}
      aria-haspopup="menu" aria-expanded={open} aria-controls={open ? panelId : undefined} onClick={() => setOpen(!open)}>
      <svg aria-hidden="true" focusable="false" viewBox="0 0 20 20" fill="currentColor">
        <circle cx="10" cy="4" r="1.7" /><circle cx="10" cy="10" r="1.7" /><circle cx="10" cy="16" r="1.7" />
      </svg>
    </button>
    {open && <div id={panelId} ref={panelRef} className={alignStart ? "actions-menu-panel align-start" : "actions-menu-panel"} role="menu" aria-label={`Acciones para «${name}»`} onKeyDown={move}>
      {items.map((item) => <button key={item.label} type="button" role="menuitem" disabled={item.disabled}
        className={item.danger ? "actions-menu-item danger" : "actions-menu-item"}
        onClick={() => { setOpen(false); item.onSelect(); }}>{item.label}</button>)}
    </div>}
  </div>;
}
