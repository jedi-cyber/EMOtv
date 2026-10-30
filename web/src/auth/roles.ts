import type { UserRole } from "./types";

/** Nombres visibles de los papeles; la clave técnica nunca se muestra. */
export const roleNames: Record<UserRole, string> = {
  student: "Usuario",
  psychologist: "Docente",
  admin: "Administrador",
  superadmin: "Superadministrador",
};

/** Papeles que conducen sesiones y aceptan el compromiso de confidencialidad. */
export const conductorRoles: readonly UserRole[] = ["student", "psychologist"];
/** Papeles de gestión: nunca ven sesiones ni resultados. */
export const managementRoles: readonly UserRole[] = ["admin", "superadmin"];

export function isConductor(role: UserRole | undefined): boolean {
  return role != null && conductorRoles.includes(role);
}
