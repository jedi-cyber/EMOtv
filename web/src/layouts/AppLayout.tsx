import { useEffect, useRef, useState } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { UserMenu } from "../components/UserMenu";
import { NavIcon } from "../components/NavIcon";
import { useActiveSession } from "../analysis/ActiveSessionContext";
import { paths } from "../routes/paths";
import { navigationByRole } from "../routes/navigation";
import type { UserRole } from "../auth/types";
import { API_RECOVERED_EVENT, API_UNAVAILABLE_EVENT } from "../api/http";

type Crumb = { label: string; to?: string };

export function breadcrumbs(pathname: string, role: UserRole): Crumb[] {
  const parts = pathname.split("/").filter(Boolean);
  const home: Crumb = { label: "Inicio", to: paths.dashboard };
  if (parts.length === 0 || parts[0] === "dashboard") return [{ label: "Inicio" }];
  const sessions = role === "student" ? "Mis sesiones" : "Sesiones";
  if (parts[0] === "activities") return [home, { label: "Actividades", ...(parts[1] ? { to: paths.activities } : {}) }, ...(parts[1] ? [{ label: "Detalle de actividad" }] : [])];
  if (parts[0] === "analysis") return [home, { label: "Actividades", to: paths.activities }, { label: "Analizador" }];
  if (parts[0] === "sessions") return [home, { label: sessions, ...(parts[1] ? { to: paths.sessions } : {}) }, ...(parts[1] ? [{ label: "Detalle de sesión" }] : [])];
  if (parts[0] === "students") return [home, { label: "Estudiantes", ...(parts[1] ? { to: paths.students } : {}) }, ...(parts[1] ? [{ label: "Sesiones del estudiante" }] : [])];
  if (parts[0] === "admin" && parts[1] === "activities") return [home, { label: "Administrar actividades" }];
  const labels: Record<string, string> = { users: "Usuarios", unauthorized: "Acceso denegado", "connection-error": "Error de conexión" };
  return [home, { label: labels[parts[0]] ?? "Página no encontrada" }];
}

export function AppLayout() {
  const { user, logout } = useAuth();
  const { activeSession } = useActiveSession();
  const { pathname } = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [backendUnavailable, setBackendUnavailable] = useState(false);
  const menuButtonRef = useRef<HTMLButtonElement>(null);
  const sidebarRef = useRef<HTMLElement>(null);
  const mainRef = useRef<HTMLElement>(null);
  const previousPathRef = useRef(pathname);
  useEffect(() => {
    setMenuOpen(false);
    if (previousPathRef.current !== pathname) mainRef.current?.focus();
    previousPathRef.current = pathname;
  }, [pathname]);
  useEffect(() => {
    const unavailable = () => setBackendUnavailable(true);
    const recovered = () => setBackendUnavailable(false);
    window.addEventListener(API_UNAVAILABLE_EVENT, unavailable);
    window.addEventListener(API_RECOVERED_EVENT, recovered);
    return () => {
      window.removeEventListener(API_UNAVAILABLE_EVENT, unavailable);
      window.removeEventListener(API_RECOVERED_EVENT, recovered);
    };
  }, []);
  useEffect(() => {
    if (!menuOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    sidebarRef.current?.querySelector<HTMLAnchorElement>("nav a")?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setMenuOpen(false);
        menuButtonRef.current?.focus();
      } else if (event.key === "Tab") {
        const links = Array.from(sidebarRef.current?.querySelectorAll<HTMLAnchorElement>("a") ?? []);
        const first = links[0]; const last = links.at(-1);
        if (first && last && event.shiftKey && document.activeElement === first) {
          event.preventDefault(); last.focus();
        } else if (first && last && !event.shiftKey && document.activeElement === last) {
          event.preventDefault(); first.focus();
        }
      }
    };
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [menuOpen]);
  const items = user ? navigationByRole[user.role] : [];
  const trail = user ? breadcrumbs(pathname, user.role) : [];
  const showBreadcrumbs = /^\/(activities|sessions)\/[^/]+\/?$/.test(pathname)
    || /^\/students\/[^/]+\/sessions\/?$/.test(pathname);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Saltar al contenido</a>
      {menuOpen && <button type="button" className="sidebar-backdrop" aria-label="Cerrar panel de navegación" onClick={() => setMenuOpen(false)} />}
      <aside ref={sidebarRef} className={`sidebar${menuOpen ? " is-open" : ""}`}>
        <Link className="brand" to={paths.dashboard}>EMOtv</Link>
        <nav id="main-navigation" aria-label="Navegación principal" onClick={(event) => { if ((event.target as HTMLElement).closest("a")) setMenuOpen(false); }}>
          {items.map(({ to, label, icon }) => <NavLink key={to} to={to} end={to === paths.dashboard} className={({ isActive }) => isActive ? "active" : undefined}><NavIcon name={icon} /><span>{label}</span></NavLink>)}
          {user?.role === "student" && activeSession && <Link className="active-session-link" to={activeSession.activityId ? paths.analysisForActivity(activeSession.activityId) : paths.analysis}><span className="active-session-dot" aria-hidden="true" />Sesión activa · Volver al análisis</Link>}
        </nav>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <button ref={menuButtonRef} className="button secondary menu-toggle" aria-label={menuOpen ? "Cerrar menú" : "Abrir menú"} aria-controls="main-navigation" aria-expanded={menuOpen} onClick={() => setMenuOpen(!menuOpen)}>{menuOpen ? "Cerrar" : "Menú"}</button>
          <div className="location-summary"><span className="location-caption">Estás en</span><strong>{trail.at(-1)?.label ?? "Inicio"}</strong></div>
          {backendUnavailable && <span className="backend-status" role="status"><Link to={paths.connectionError}>Servicio no disponible</Link></span>}
          {user?.role === "student" && activeSession && <Link className="active-session-mobile" to={activeSession.activityId ? paths.analysisForActivity(activeSession.activityId) : paths.analysis}>Sesión activa · Volver al análisis</Link>}
          {user && <UserMenu user={user} onLogout={() => logout()} />}
        </header>
        <main ref={mainRef} id="main-content" tabIndex={-1} className="content">
          {showBreadcrumbs && <nav aria-label="Ruta de navegación" className="breadcrumbs"><ol>{trail.map((crumb, index) => <li key={`${crumb.label}-${index}`}>{crumb.to ? <Link to={crumb.to}>{crumb.label}</Link> : <span aria-current="page">{crumb.label}</span>}</li>)}</ol></nav>}
          <Outlet />
        </main>
      </div>
    </div>
  );
}
