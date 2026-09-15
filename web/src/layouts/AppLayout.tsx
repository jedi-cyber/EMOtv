import { NavLink, Outlet } from "react-router-dom";
import { useAuth } from "../auth/useAuth";

export function AppLayout() {
  const { user, logout } = useAuth();

  const links = user?.role === "student"
    ? [["/dashboard", "Inicio"], ["/analysis", "Analizador"], ["/activities", "Actividades"], ["/sessions", "Mis sesiones"]]
    : user?.role === "psychologist"
      ? [["/dashboard", "Inicio"], ["/students", "Estudiantes"], ["/sessions", "Sesiones"], ["/activities", "Actividades"]]
      : [["/dashboard", "Inicio"], ["/users", "Usuarios"], ["/admin/activities", "Administrar actividades"], ["/sessions", "Sesiones"]];

  const roleNames = { student: "Estudiante", psychologist: "Psicología", admin: "Administración" };

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Saltar al contenido</a>
      <aside className="sidebar">
        <a className="brand" href="/dashboard">EMOtv</a>
        <nav aria-label="Navegación principal">
          {links.map(([path, label]) => <NavLink key={path} to={path}>{label}</NavLink>)}
        </nav>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div>
            <strong>{user?.email}</strong>
            <span className="role">{user ? roleNames[user.role] : ""}</span>
          </div>
          <button className="button secondary" onClick={() => logout()}>Cerrar sesión</button>
        </header>
        <main id="main-content" tabIndex={-1} className="content"><Outlet /></main>
      </div>
    </div>
  );
}
