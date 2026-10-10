import { request } from "@playwright/test";
import { env } from "./support/env";

/** Comprueba antes de empezar que el stack responde y que la cuenta de administración sirve. */
export default async function globalSetup() {
  if (!env.adminEmail || !env.adminPassword) {
    throw new Error("Define E2E_ADMIN_EMAIL y E2E_ADMIN_PASSWORD (cuenta de administración que ya cambió su contraseña provisional). Ver docs/testing/e2e.md.");
  }
  const api = await request.newContext({ baseURL: env.baseURL });
  try {
    const health = await api.get("/health").catch(() => null);
    if (!health?.ok()) throw new Error(`EMOtv no responde en ${env.baseURL}/health. Levanta el stack o ajusta E2E_BASE_URL.`);
    const login = await api.post("/auth/token", { form: { username: env.adminEmail, password: env.adminPassword } });
    if (login.status() === 429) throw new Error("El backend bloqueó los inicios de sesión por demasiados intentos fallidos. Espera la ventana de LOGIN_ATTEMPT_WINDOW_MINUTES.");
    if (!login.ok()) throw new Error(`No se pudo iniciar sesión con E2E_ADMIN_EMAIL (HTTP ${login.status()}).`);
    const { access_token: token } = await login.json() as { access_token: string };
    const me = await api.get("/auth/me", { headers: { Authorization: `Bearer ${token}` } });
    const user = await me.json() as { role: string; must_change_password?: boolean };
    if (user.role !== "admin") throw new Error("E2E_ADMIN_EMAIL no corresponde a una cuenta de administración.");
    if (user.must_change_password) throw new Error("La cuenta de administración aún tiene la contraseña provisional; cámbiala en /first-access.");
  } finally {
    await api.dispose();
  }
}
