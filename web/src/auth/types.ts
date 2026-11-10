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
  /** Falta mientras una cuenta de gestión no escriba el código de su aplicación. */
  access_token?: string;
  token_type: "bearer";
  /** Superadmin y admin: configurar la aplicación autenticadora o escribir su código. */
  mfa?: "setup" | "verify";
  mfa_token?: string;
}

/** Segundo paso del ingreso de una cuenta de gestión. */
export interface MfaChallenge {
  step: "setup" | "verify";
  mfaToken: string;
}

export interface MfaSetup {
  secret: string;
  otpauth_uri: string;
}

/** Encabezado con el código del momento para las acciones que cambian cuentas o grupos. */
export const CONFIRMATION_HEADER = "X-Confirmation-Code";
