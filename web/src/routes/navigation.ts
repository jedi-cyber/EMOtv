import type { UserRole } from "../auth/types";
import type { NavIconName } from "../components/NavIcon";
import { paths } from "./paths";

export interface NavigationItem {
  to: string;
  label: string;
  icon: NavIconName;
}

export const navigationByRole: Record<UserRole, readonly NavigationItem[]> = {
  student: [
    { to: paths.dashboard, label: "Inicio", icon: "home" },
    { to: paths.activities, label: "Actividades", icon: "activity" },
    { to: paths.analysis, label: "Analizador", icon: "analysis" },
    { to: paths.consent, label: "Consentimiento", icon: "users" },
    { to: paths.sessions, label: "Mis sesiones", icon: "sessions" },
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
    { to: paths.sessions, label: "Sesiones", icon: "sessions" },
  ],
};
