import { randomBytes } from "node:crypto";
import { request } from "@playwright/test";
import { env } from "./support/env";
import { codeAt } from "./support/mfa";

const step = () => Math.floor(Date.now() / 30_000);

/**
 * Comprueba antes de empezar que el stack responde y que la cuenta de
 * superadministrador sirve. Si la cuenta aún debe configurar su aplicación
 * autenticadora (recién creada o tras scripts/security/reset_mfa.py), la
 * configura aquí; si tiene la contraseña provisional, la cambia por una
 * aleatoria. La clave y la contraseña pasan a las pruebas solo por variables de
 * entorno de este proceso: no se escriben en archivos ni en la terminal.
 */
export default async function globalSetup() {
  if (!env.adminEmail || !env.adminPassword) {
    throw new Error("Define E2E_ADMIN_EMAIL y E2E_ADMIN_PASSWORD (cuenta de superadministrador). Ver docs/testing/e2e.md.");
  }
  const api = await request.newContext({ baseURL: env.baseURL });
  try {
    const health = await api.get("/health").catch(() => null);
    if (!health?.ok()) throw new Error(`EMOtv no responde en ${env.baseURL}/health. Levanta el stack o ajusta E2E_BASE_URL.`);
    const login = await api.post("/auth/token", { form: { username: env.adminEmail, password: env.adminPassword } });
    if (login.status() === 429) throw new Error("El backend bloqueó los inicios de sesión por demasiados intentos fallidos. Espera la ventana de LOGIN_ATTEMPT_WINDOW_MINUTES.");
    if (!login.ok()) throw new Error(`No se pudo iniciar sesión con E2E_ADMIN_EMAIL (HTTP ${login.status()}).`);
    const body = await login.json() as { mfa?: "setup" | "verify"; mfa_token?: string };
    if (!body.mfa || !body.mfa_token) throw new Error("E2E_ADMIN_EMAIL no corresponde a la cuenta de superadministrador.");

    let secret = process.env.E2E_ADMIN_TOTP_SECRET ?? "";
    if (body.mfa === "setup") {
      const setup = await api.post("/auth/mfa/setup", { data: { mfa_token: body.mfa_token } });
      if (!setup.ok()) throw new Error(`No se pudo configurar el segundo factor (HTTP ${setup.status()}).`);
      secret = (await setup.json() as { secret: string }).secret;
    } else if (!secret) {
      throw new Error("La cuenta de superadministrador ya configuró su aplicación autenticadora. Define E2E_ADMIN_TOTP_SECRET "
        + "o reinícialo con scripts/security/reset_mfa.py (docs/testing/e2e.md).");
    }
    const used = step();
    const verified = await api.post("/auth/mfa/verify", { data: { mfa_token: body.mfa_token, code: codeAt(secret, used) } });
    if (!verified.ok()) throw new Error(`El código del segundo factor no fue aceptado (HTTP ${verified.status()}). Revisa E2E_ADMIN_TOTP_SECRET y la hora del equipo.`);
    const { access_token: token } = await verified.json() as { access_token: string };
    process.env.E2E_ADMIN_TOTP_SECRET = secret;
    process.env.E2E_ADMIN_TOTP_LAST_STEP = String(used);

    const me = await api.get("/auth/me", { headers: { Authorization: `Bearer ${token}` } });
    const user = await me.json() as { role: string; must_change_password?: boolean };
    if (user.role !== "superadmin") throw new Error("E2E_ADMIN_EMAIL no corresponde a la cuenta de superadministrador.");
    if (user.must_change_password) {
      const password = `E2e-${randomBytes(18).toString("base64url")}-9`;
      const changed = await api.post("/auth/change-password", { headers: { Authorization: `Bearer ${token}` },
        data: { current_password: env.adminPassword, new_password: password } });
      if (!changed.ok()) throw new Error(`No se pudo cambiar la contraseña provisional (HTTP ${changed.status()}).`);
      process.env.E2E_ADMIN_PASSWORD = password;
    }
  } finally {
    await api.dispose();
  }
}
