export type UserRole = "student" | "psychologist" | "admin";

export interface CurrentUser {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  must_change_password?: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}
