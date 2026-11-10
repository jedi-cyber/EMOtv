import { randomBytes } from "node:crypto";
import { expect, request, type APIRequestContext, type Page } from "@playwright/test";
import { env } from "./env";
import { confirmationHeaders, loginCode, registerSecret } from "./mfa";

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

interface TokenBody { access_token?: string; mfa?: "setup" | "verify"; mfa_token?: string }

/**
 * Tokens de las cuentas de gestión: cada ingreso gasta un código y el siguiente
 * debe esperar otro intervalo de 30 s, así que se reutilizan mientras duren
 * (15 minutos), con margen.
 */
const managementTokens = new Map<string, { token: string; expires: number }>();
const TOKEN_MARGIN_MS = 2 * 60_000;

function remember(email: string, token: string): void {
  const payload = JSON.parse(Buffer.from(token.split(".")[1], "base64url").toString("utf-8")) as { exp: number };
  managementTokens.set(email, { token, expires: payload.exp * 1000 });
}

/** Superadmin y admin: la contraseña da un token de paso; la primera vez se configura la aplicación. */
async function secondFactor(api: APIRequestContext, email: string, body: TokenBody): Promise<string> {
  if (body.mfa === "setup") {
    const setup = await api.post("/auth/mfa/setup", { data: { mfa_token: body.mfa_token } });
    expect(setup.status(), await setup.text()).toBe(200);
    registerSecret(email, (await setup.json() as { secret: string }).secret);
  }
  const verified = await api.post("/auth/mfa/verify", { data: { mfa_token: body.mfa_token, code: await loginCode(email) } });
  expect(verified.status(), `segundo factor de ${email}: ${await verified.text()}`).toBe(200);
  const token = (await verified.json() as TokenBody).access_token ?? "";
  remember(email, token);
  return token;
}

export async function loginToken(email: string, password: string): Promise<string> {
  const cached = managementTokens.get(email);
  if (cached && cached.expires - Date.now() > TOKEN_MARGIN_MS) return cached.token;
  const api = await context();
  try {
    const response = await api.post("/auth/token", { form: { username: email, password } });
    expect(response.status(), `inicio de sesión de ${email}`).toBe(200);
    const body = await response.json() as TokenBody;
    return body.mfa ? await secondFactor(api, email, body) : body.access_token ?? "";
  } finally {
    await api.dispose();
  }
}

export async function withToken<T>(token: string, run: (api: APIRequestContext) => Promise<T>): Promise<T> {
  const api = await context(token);
  try { return await run(api); } finally { await api.dispose(); }
}

/** La cuenta de E2E_ADMIN_EMAIL es la de superadministrador (soporte técnico). */
export async function superadminToken(): Promise<string> {
  return loginToken(env.adminEmail, env.adminPassword);
}

const ORG_ADMIN_PREFIX = "e2e-admin-org";
let orgAdmin: Promise<Account> | undefined;

/**
 * Cuenta de administrador de la Facultad: crea cuentas de Usuario y Docente y arma los grupos.
 * Su segundo factor no se puede quitar desde la aplicación, así que cada proceso
 * de pruebas desactiva la de la ejecución anterior y crea una nueva (solo puede
 * haber una activa), que configura su aplicación en el primer ingreso.
 */
export function adminAccount(): Promise<Account> {
  orgAdmin ??= (async () => {
    const email = `${ORG_ADMIN_PREFIX}-${suffix()}@emotv.local`;
    const prepared = await withToken(await superadminToken(), async (api) => {
      const users = await (await api.get("/users")).json() as { id: string; email: string; is_active: boolean }[];
      for (const previous of users.filter((item) => item.is_active && item.email.startsWith(ORG_ADMIN_PREFIX))) {
        const deactivated = await api.delete(`/users/${encodeURIComponent(previous.id)}`,
          { headers: confirmationHeaders(env.adminEmail) });
        expect(deactivated.ok(), await deactivated.text()).toBe(true);
      }
      const response = await api.post("/users", { data: { email, role: "admin" }, headers: confirmationHeaders(env.adminEmail) });
      expect(response.ok(), await response.text()).toBe(true);
      return await response.json() as { id: string; temporary_password: string };
    });
    return activate({ id: prepared.id, email, role: "admin", password: prepared.temporary_password });
  })();
  return orgAdmin;
}

export async function adminToken(): Promise<string> {
  const admin = await adminAccount();
  return loginToken(admin.email, admin.password);
}

/** Crea una cuenta con contraseña provisional (debe cambiarla en el primer acceso). */
export async function createAccount(role: Exclude<Role, "admin">): Promise<Account> {
  const id = suffix();
  const email = `e2e-${role}-${id}@emotv.local`;
  const studentCode = role === "student" ? `E2E-${id.toUpperCase()}` : undefined;
  const created = await withToken(await adminToken(), async (api) => {
    const response = await api.post("/users", { data: { email, role, ...(studentCode ? { student_code: studentCode } : {}) },
      headers: confirmationHeaders((await adminAccount()).email) });
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
    // El cambio cierra las sesiones anteriores: una cuenta de gestión guarda el token nuevo.
    if (managementTokens.has(account.email)) remember(account.email, (await response.json() as TokenBody).access_token ?? "");
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
    const response = await api.put(`/users/${encodeURIComponent(psychologist.id)}/assigned-students/${encodeURIComponent(studentId)}`,
      { headers: confirmationHeaders((await adminAccount()).email) });
    expect(response.status(), await response.text()).toBe(200);
  });
}

/**
 * Inicio de sesión por la interfaz. Por defecto espera a salir de /login (la sesión
 * queda guardada); con `expectFailure` se queda en la página para comprobar el error.
 */
export async function signIn(page: Page, email: string, password: string, { expectFailure = false } = {}): Promise<void> {
  // Si la página ya tenía una sesión, el login redirigiría: se cierra antes de entrar con otra cuenta.
  await page.goto("/login");
  await page.evaluate(() => window.sessionStorage.clear());
  await page.goto("/login");
  await page.getByLabel("Correo institucional", { exact: true }).fill(email);
  await page.getByLabel("Contraseña", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Ingresar" }).click();
  if (expectFailure) return;
  // Superadmin y admin escriben después el código de su aplicación autenticadora.
  const code = page.getByLabel("Código de tu aplicación autenticadora", { exact: true });
  await Promise.race([page.waitForURL((url) => !url.pathname.endsWith("/login")), code.waitFor()]);
  if (await code.isVisible()) {
    await code.fill(await loginCode(email));
    await page.getByRole("button", { name: "Entrar" }).click();
  }
  await page.waitForURL((url) => !url.pathname.endsWith("/login"));
}

/**
 * Acepta por API el compromiso de confidencialidad vigente. Sin él, la interfaz de
 * Usuarios y Docentes muestra su modal y no se inician sesiones con otras personas.
 * screenshots.spec.ts lo acepta por la interfaz para capturar el modal.
 */
export async function acceptCommitment(account: Account): Promise<void> {
  await withToken(await loginToken(account.email, account.password), async (api) => {
    const text = await (await api.get("/commitment")).json() as { version: string; required: boolean };
    if (!text.required) return;
    const response = await api.post("/commitment/accept", { data: { version: text.version } });
    expect(response.ok(), await response.text()).toBe(true);
  });
}
