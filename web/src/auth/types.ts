/** Papeles internos; en pantalla: Usuario, Docente, Administrador y Superadministrador. */
export type UserRole = "student" | "psychologist" | "admin" | "superadmin";

export interface CurrentUser {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  must_change_password?: boolean;
  /** Otra cuenta restableció la contraseña: se avisa en el siguiente ingreso. */
  password_reset?: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}
