import type { UserRole } from "../auth/types";
import type { NavIconName } from "../components/NavIcon";
import { paths } from "./paths";

export interface NavigationItem {
  to: string;
  label: string;
  icon: NavIconName;
  /** "footer": abajo y separado del recorrido principal (Consentimiento). */
  placement?: "main" | "footer";
}

export const navigationByRole: Record<UserRole, readonly NavigationItem[]> = {
  // Orden del recorrido (DESIGN.md): Inicio, Analizador, Actividades, Mis sesiones.
  student: [
    { to: paths.dashboard, label: "Inicio", icon: "home" },
    { to: paths.analysis, label: "Analizador", icon: "analysis" },
    { to: paths.activities, label: "Actividades", icon: "activity" },
    { to: paths.sessions, label: "Mis sesiones", icon: "sessions" },
    { to: paths.consent, label: "Consentimiento", icon: "users", placement: "footer" },
  ],
  psychologist: [
    { to: paths.dashboard, label: "Inicio", icon: "home" },
    { to: paths.students, label: "Estudiantes", icon: "students" },
    { to: paths.sessions, label: "Sesiones", icon: "sessions" },
    { to: paths.activities, label: "Actividades", icon: "activity" },
  ],
  admin: [
    { to: paths.dashboard, label: "Inicio", icon: "home" },
    { to: paths.users, label: "Usuarios", icon: "users" },
    { to: paths.students, label: "Estudiantes", icon: "students" },
    { to: paths.adminActivities, label: "Administrar actividades", icon: "manage" },
    { to: paths.adminExpressions, label: "Catálogo de expresiones", icon: "manage" },
    { to: paths.sessions, label: "Sesiones", icon: "sessions" },
  ],
};
