import type { UserRole } from "../auth/types";
import type { NavIconName } from "../components/NavIcon";
import { ACTIVITIES_ENABLED } from "./features";
import { paths } from "./paths";

export interface NavigationItem {
  to: string;
  label: string;
  icon: NavIconName;
  /** "footer": abajo y separado del recorrido principal (Consentimiento). */
  placement?: "main" | "footer";
  /** Sección plegable del menú a la que pertenece (por ejemplo, "Mi material"). */
  group?: string;
  /** Contador junto al nombre: imágenes pendientes de revisión del docente. */
  counter?: "imageReview" | "reviews";
}

/** Cuestionarios y protocolos: lo que cada cuenta prepara para usar en el Analizador. */
const material: readonly NavigationItem[] = [
  { to: paths.questionnaires, label: "Cuestionarios", icon: "document", group: "Mi material" },
  { to: paths.protocols, label: "Protocolos", icon: "document", group: "Mi material" },
];

/** Actividades corporales: congeladas, fuera del menú (routes/features.ts). */
const activitiesItem: readonly NavigationItem[] = ACTIVITIES_ENABLED
  ? [{ to: paths.activities, label: "Actividades", icon: "activity" }]
  : [];

/** Guía de uso: la ven todas las cuentas, con los temas de su papel. */
const guideItem: NavigationItem = { to: paths.guide, label: "Guía de uso", icon: "document", placement: "footer" };

export const navigationByRole: Record<UserRole, readonly NavigationItem[]> = {
  // Toda sesión empieza en el Analizador, con un protocolo o sin él.
  student: [
    { to: paths.dashboard, label: "Inicio", icon: "home" },
    { to: paths.analysis, label: "Analizador", icon: "analysis" },
    { to: paths.sessions, label: "Mis sesiones", icon: "sessions" },
    { to: paths.statistics, label: "Estadísticas", icon: "statistics" },
    ...activitiesItem,
    ...material,
    { to: paths.images, label: "Imágenes", icon: "document", group: "Mi material" },
    { to: paths.consent, label: "Consentimiento", icon: "users", placement: "footer" },
    guideItem,
  ],
  // El docente supervisa a su grupo después de cada sesión; sus sesiones son de demostración.
  psychologist: [
    { to: paths.dashboard, label: "Inicio", icon: "home" },
    { to: paths.reviews, label: "Por revisar", icon: "document", counter: "reviews" },
    { to: paths.analysis, label: "Analizador", icon: "analysis" },
    { to: paths.sessions, label: "Sesiones", icon: "sessions" },
    { to: paths.students, label: "Mi grupo", icon: "users" },
    { to: paths.statistics, label: "Estadísticas", icon: "statistics" },
    ...activitiesItem,
    { to: paths.stimuli, label: "Estímulos", icon: "manage" },
    { to: paths.imageReview, label: "Imágenes por revisar", icon: "shield", counter: "imageReview" },
    ...material,
    guideItem,
  ],
  // Cuentas, grupos, estímulos institucionales y auditoría; nunca sesiones ni resultados.
  admin: [
    { to: paths.dashboard, label: "Inicio", icon: "home" },
    { to: paths.users, label: "Cuentas y grupos", icon: "users" },
    { to: paths.stimuli, label: "Estímulos institucionales", icon: "manage" },
    { to: paths.audit, label: "Auditoría", icon: "shield" },
    guideItem,
  ],
  // Soporte técnico: modelos, catálogos, la cuenta de administrador y auditoría.
  superadmin: [
    { to: paths.dashboard, label: "Inicio", icon: "home" },
    { to: paths.adminModels, label: "Modelos", icon: "manage" },
    ...(ACTIVITIES_ENABLED ? [{ to: paths.adminActivities, label: "Administrar actividades", icon: "manage" } as const] : []),
    { to: paths.adminExpressions, label: "Catálogo de expresiones", icon: "manage" },
    { to: paths.users, label: "Cuenta de administrador", icon: "users" },
    { to: paths.audit, label: "Auditoría", icon: "shield" },
    guideItem,
  ],
};
