import { randomBytes } from "node:crypto";
import { expect, request, type APIRequestContext, type Page } from "@playwright/test";
import { env } from "./env";

export type Role = "student" | "psychologist" | "admin";

export interface Account {
  id: string;
  email: string;
  role: Role;
  password: string;
  studentCode?: string;
}

const suffix = () => randomBytes(4).toString("hex");

/** Contraseña aleatoria por ejecución: nunca se escribe en archivos. */
export const newPassword = () => `E2e-${randomBytes(12).toString("base64url")}-9`;

async function context(token?: string): Promise<APIRequestContext> {
  return request.newContext({
    baseURL: env.baseURL,
    extraHTTPHeaders: token ? { Authorization: `Bearer ${token}` } : {},
  });
}

export async function loginToken(email: string, password: string): Promise<string> {
  const api = await context();
  const response = await api.post("/auth/token", { form: { username: email, password } });
  expect(response.status(), `inicio de sesión de ${email}`).toBe(200);
  const { access_token: token } = await response.json() as { access_token: string };
  await api.dispose();
  return token;
}

export async function withToken<T>(token: string, run: (api: APIRequestContext) => Promise<T>): Promise<T> {
  const api = await context(token);
  try { return await run(api); } finally { await api.dispose(); }
}

export async function adminToken(): Promise<string> {
  return loginToken(env.adminEmail, env.adminPassword);
}

/** Crea una cuenta con contraseña provisional (debe cambiarla en el primer acceso). */
export async function createAccount(role: Exclude<Role, "admin">): Promise<Account> {
  const id = suffix();
  const email = `e2e-${role}-${id}@emotv.local`;
  const studentCode = role === "student" ? `E2E-${id.toUpperCase()}` : undefined;
  const created = await withToken(await adminToken(), async (api) => {
    const response = await api.post("/users", { data: { email, role, ...(studentCode ? { student_code: studentCode } : {}) } });
    expect(response.status(), await response.text()).toBe(201);
    return await response.json() as { id: string; temporary_password: string };
  });
  return { id: created.id, email, role, password: created.temporary_password, studentCode };
}

/** Cambia la contraseña provisional por API; devuelve la cuenta lista para usar. */
export async function activate(account: Account): Promise<Account> {
  const token = await loginToken(account.email, account.password);
  const password = newPassword();
  await withToken(token, async (api) => {
    const response = await api.post("/auth/change-password", { data: { current_password: account.password, new_password: password } });
    expect(response.status(), await response.text()).toBe(200);
  });
  return { ...account, password };
}

export async function readyAccount(role: Exclude<Role, "admin">): Promise<Account> {
  return activate(await createAccount(role));
}

export async function studentIdOf(account: Account): Promise<string> {
  return withToken(await loginToken(account.email, account.password), async (api) => {
    const students = await (await api.get("/students")).json() as { id: string }[];
    expect(students).toHaveLength(1);
    return students[0].id;
  });
}

/** Acepta por API la política vigente (no se usa en la prueba de consentimiento, que va por la interfaz). */
export async function acceptConsent(account: Account): Promise<void> {
  const studentId = await studentIdOf(account);
  await withToken(await loginToken(account.email, account.password), async (api) => {
    const policy = await (await api.get("/consent-policy")).json() as { id?: string | null; version: string | null; mode: string; available: boolean };
    if (policy.mode === "development" || !policy.available) return;
    const response = await api.post(`/students/${encodeURIComponent(studentId)}/consents`, { data: { policy_version: policy.id ?? policy.version } });
    expect(response.status(), await response.text()).toBe(201);
  });
}

export async function assignStudent(psychologist: Account, studentId: string): Promise<void> {
  await withToken(await adminToken(), async (api) => {
    const response = await api.put(`/users/${encodeURIComponent(psychologist.id)}/assigned-students/${encodeURIComponent(studentId)}`);
    expect(response.status(), await response.text()).toBe(200);
  });
}

/**
 * Inicio de sesión por la interfaz. Por defecto espera a salir de /login (la sesión
 * queda guardada); con `expectFailure` se queda en la página para comprobar el error.
 */
export async function signIn(page: Page, email: string, password: string, { expectFailure = false } = {}): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("Correo institucional", { exact: true }).fill(email);
  await page.getByLabel("Contraseña", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  if (!expectFailure) await page.waitForURL((url) => !url.pathname.endsWith("/login"));
}
