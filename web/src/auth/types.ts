export type UserRole = "student" | "psychologist" | "admin";

export interface CurrentUser {
  id: string;
  email: string;
  role: UserRole;
  is_active: boolean;
}

export interface TokenResponse {
  access_token: string;
  token_type: "bearer";
}
