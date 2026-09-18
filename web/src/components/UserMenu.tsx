import { useEffect, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import type { CurrentUser } from "../auth/types";

const roleNames = { student: "Estudiante", psychologist: "Psicología", admin: "Administración" };

interface UserMenuProps {
  user: CurrentUser;
  onLogout(): void;
}

export function UserMenu({ user, onLogout }: UserMenuProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const { pathname } = useLocation();

  useEffect(() => { setOpen(false); }, [pathname]);
  useEffect(() => {
    if (!open) return;
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

  return <div className="user-menu" ref={rootRef}>
    <button ref={triggerRef} type="button" className="user-menu-trigger" aria-label="Menú de usuario" aria-describedby="current-user-role" aria-expanded={open} aria-controls="user-menu-panel" onClick={() => setOpen(!open)}>
      <span className="user-avatar" aria-hidden="true">{user.email.charAt(0).toUpperCase()}</span>
      <span className="user-menu-label"><strong>{user.email}</strong></span>
      <span id="current-user-role" className="user-role-badge">{roleNames[user.role]}</span>
      <svg className="user-menu-chevron" aria-hidden="true" focusable="false" viewBox="0 0 20 20" fill="none"><path d="m5 7 5 5 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
    </button>
    {open && <div id="user-menu-panel" className="user-menu-panel">
      <p className="user-menu-caption">Sesión iniciada como</p>
      <strong className="user-menu-email">{user.email}</strong>
      <span className="user-menu-role">{roleNames[user.role]}</span>
      <button type="button" className="button secondary user-menu-logout" onClick={() => { setOpen(false); onLogout(); }}>Cerrar sesión</button>
    </div>}
  </div>;
}
