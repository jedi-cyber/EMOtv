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
    { to: paths.guided, label: "Sesión guiada", icon: "guided" },
    { to: paths.participants, label: "Participantes", icon: "students" },
    { to: paths.questionnaires, label: "Cuestionarios", icon: "document" },
    { to: paths.protocols, label: "Protocolos", icon: "document" },
    { to: paths.activities, label: "Actividades", icon: "activity" },
    { to: paths.sessions, label: "Mis sesiones", icon: "sessions" },
    { to: paths.consent, label: "Consentimiento", icon: "users", placement: "footer" },
  ],
  // El docente conduce sesiones propias y revisa las de su grupo.
  psychologist: [
    { to: paths.dashboard, label: "Inicio", icon: "home" },
    { to: paths.analysis, label: "Analizador", icon: "analysis" },
    { to: paths.guided, label: "Sesión guiada", icon: "guided" },
    { to: paths.participants, label: "Participantes", icon: "students" },
    { to: paths.questionnaires, label: "Cuestionarios", icon: "document" },
    { to: paths.protocols, label: "Protocolos", icon: "document" },
    { to: paths.stimuli, label: "Estímulos", icon: "manage" },
    { to: paths.students, label: "Mi grupo", icon: "users" },
    { to: paths.sessions, label: "Sesiones", icon: "sessions" },
    { to: paths.activities, label: "Actividades", icon: "activity" },
  ],
  // Cuentas, grupos, estímulos institucionales y auditoría; nunca participantes ni resultados.
  admin: [
    { to: paths.dashboard, label: "Inicio", icon: "home" },
    { to: paths.users, label: "Cuentas y grupos", icon: "users" },
    { to: paths.stimuli, label: "Estímulos institucionales", icon: "manage" },
    { to: paths.audit, label: "Auditoría", icon: "shield" },
  ],
  // Soporte técnico: modelos, catálogos, la cuenta de administrador y auditoría.
  superadmin: [
    { to: paths.dashboard, label: "Inicio", icon: "home" },
    { to: paths.adminModels, label: "Modelos", icon: "manage" },
    { to: paths.adminActivities, label: "Administrar actividades", icon: "manage" },
    { to: paths.adminExpressions, label: "Catálogo de expresiones", icon: "manage" },
    { to: paths.users, label: "Cuenta de administrador", icon: "users" },
    { to: paths.audit, label: "Auditoría", icon: "shield" },
  ],
};
