import { expect, test, type APIRequestContext, type Page } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { acceptConsent, adminAccount, assignStudent, createAccount, loginToken, readyAccount, signIn, studentIdOf, withToken } from "./support/api";
import { env } from "./support/env";
import { startFakeN8n } from "./support/fakeN8n";

/**
 * Capturas de cada vista para docs/thesis-evidence/screenshots/. Solo se ejecuta con
 * E2E_SCREENSHOTS=1 y contra el stack aislado: todas las cuentas son ficticias
 * (e2e-…@emotv.local) y la cámara es el video simulado sin persona.
 */
const outDir = fileURLToPath(new URL("../../docs/thesis-evidence/screenshots/", import.meta.url));

/** Acepta por API el compromiso de confidencialidad vigente: sin él no se inician sesiones. */
async function acceptCommitment(api: APIRequestContext) {
  const commitment = await (await api.get("/commitment")).json() as { version: string | null };
  if (commitment.version) await api.post("/commitment/accept", { data: { version: commitment.version } });
}

/** Sesiones propias canceladas, sin cámara: muestran códigos y estados reales sin datos personales. */
async function cancelledSessions(api: APIRequestContext, count: number): Promise<string[]> {
  const ids: string[] = [];
  for (let index = 0; index < count; index++) {
    const response = await api.post("/sessions", { data: { session_type: "propia", authorization_confirmed: true } });
    expect(response.status(), await response.text()).toBe(201);
    const { id } = await response.json() as { id: string };
    await api.post(`/sessions/${id}/cancel`);
    ids.push(id);
  }
  return ids;
}

async function heading(page: Page) {
  await expect(page.getByRole("heading", { level: 1 }).first()).toBeVisible();
}

test.describe("capturas para la tesis", () => {
  test.skip(process.env.E2E_SCREENSHOTS !== "1", "Activa E2E_SCREENSHOTS=1 para regenerar las capturas.");
  test.use({ viewport: { width: 1280, height: 800 } });

  async function shot(page: Page, name: string, fullPage = true) {
    await page.waitForLoadState("networkidle");
    await page.screenshot({ path: `${outDir}${name}.png`, fullPage, animations: "disabled", caret: "hide" });
  }

  test("vistas del estudiante", async ({ page }) => {
    await page.goto("/login");
    await shot(page, "01-login");

    const fresh = await createAccount("student");
    await signIn(page, fresh.email, fresh.password);
    await expect(page.getByRole("heading", { name: "Protege tu cuenta" })).toBeVisible();
    await shot(page, "02-primer-acceso");

    const student = await readyAccount("student");
    await signIn(page, student.email, student.password);
    const commitment = page.getByRole("dialog").filter({ has: page.getByRole("heading", { name: "Compromiso de confidencialidad" }) });
    await expect(commitment).toBeVisible();
    await shot(page, "29-compromiso-confidencialidad", false);
    await commitment.getByRole("checkbox", { name: /Leí el compromiso/ }).check();
    await commitment.getByRole("button", { name: "Aceptar el compromiso" }).click();
    await expect(commitment).toBeHidden();
    await expect(page.getByRole("heading", { level: 1, name: "Hola" })).toBeVisible();
    await shot(page, "03-inicio-sin-consentimiento");

    await page.goto("/consent");
    await expect(page.getByRole("heading", { name: "Tu consentimiento" })).toBeVisible();
    await shot(page, "04-consentimiento");
    await page.getByRole("button", { name: "Leer y aceptar" }).first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await shot(page, "05-consentimiento-modal", false);
    await page.getByRole("dialog").getByRole("checkbox", { name: /He leído la política/ }).check();
    await page.getByRole("dialog").getByRole("button", { name: "Aceptar la política" }).click();
    await expect(page).toHaveURL(/\/analysis$/);
    await shot(page, "06-analizador-requisitos");
    await page.getByRole("button", { name: "Probar cámara" }).first().click();
    await expect(page.getByRole("button", { name: "Apagar cámara" })).toBeVisible();
    await page.waitForTimeout(1_000);
    await shot(page, "07-analizador-camara-simulada");
    await page.getByRole("button", { name: "Apagar cámara" }).click();

    await page.goto("/dashboard");
    await expect(page.getByRole("link", { name: "Empezar análisis" })).toBeVisible();
    await shot(page, "08-inicio-primeros-pasos");

    await page.goto("/activities");
    await expect(page.getByRole("button", { name: /^Ver pasos de / }).first()).toBeVisible();
    await shot(page, "09-actividades");
    await page.getByRole("button", { name: /^Ver pasos de / }).first().click();
    await shot(page, "10-actividad-pasos", false);
    await page.keyboard.press("Escape");

    await page.goto("/sessions");
    await expect(page.getByRole("link", { name: "Nuevo análisis" })).toBeVisible();
    await shot(page, "11-mis-sesiones-vacio");

    const n8n = await startFakeN8n(env.fakeN8nPort, env.fakeN8nKey);
    try {
      await page.goto("/dashboard");
      await page.getByRole("button", { name: "Abrir a Emi" }).click();
      await page.getByLabel("Tu pregunta", { exact: true }).fill("¿Qué es una actividad en EMOtv?");
      await page.getByRole("button", { name: "Enviar" }).click();
      await expect(page.getByRole("log").getByText(/secuencia de posturas/)).toBeVisible();
      await shot(page, "12-emi", false);
    } finally { await n8n.close(); }

    await page.setViewportSize({ width: 360, height: 780 });
    await page.goto("/analysis");
    await shot(page, "13-analizador-360px");
  });

  test("material, sesiones y estadísticas del usuario", async ({ page }) => {
    const student = await readyAccount("student");
    await acceptConsent(student);
    const [first] = await withToken(await loginToken(student.email, student.password), async (api) => {
      await acceptCommitment(api);
      expect((await api.post("/questionnaires/starter")).status()).toBe(201);
      return cancelledSessions(api, 3);
    });

    await signIn(page, student.email, student.password);
    await page.goto("/sessions");
    await heading(page);
    await shot(page, "19-mis-sesiones-con-codigo");
    await page.goto(`/sessions/${first}`);
    await heading(page);
    await shot(page, "20-sesion-detalle");

    await page.goto("/statistics");
    await expect(page.getByRole("list", { name: "Sesiones completadas e interrumpidas" })).toBeVisible();
    await shot(page, "21-estadisticas");

    await page.goto("/questionnaires");
    await heading(page);
    await shot(page, "22-cuestionarios");
    await page.goto("/protocols");
    await heading(page);
    await shot(page, "23-protocolos");
    await page.goto("/images");
    await heading(page);
    await shot(page, "24-imagenes-propias");
    await page.goto("/analysis");
    await heading(page);
    await shot(page, "25-analizador-con-quien");
  });

  test("vistas de Psicología y Administración", async ({ page }) => {
    const student = await readyAccount("student");
    await acceptConsent(student);
    const studentId = await studentIdOf(student);
    // Sesiones canceladas sin expresión: el historial muestra estados reales sin datos personales.
    await withToken(await loginToken(student.email, student.password), async (api) => {
      await acceptCommitment(api);
      await cancelledSessions(api, 2);
    });
    const psychologist = await readyAccount("psychologist");
    await assignStudent(psychologist, studentId);

    await signIn(page, psychologist.email, psychologist.password);
    await withToken(await loginToken(psychologist.email, psychologist.password), async (api) => {
      await acceptCommitment(api);
      expect((await api.post("/exams")).status()).toBe(201);
    });
    await page.goto("/students");
    await heading(page);
    await shot(page, "14-psicologia-estudiantes");
    await page.goto("/sessions");
    await heading(page);
    await shot(page, "15-psicologia-sesiones-del-estudiante");
    await page.goto("/images/review");
    await heading(page);
    await shot(page, "26-docente-imagenes-por-revisar");
    await page.goto("/exams");
    await heading(page);
    await shot(page, "27-docente-examenes");
    await page.goto("/statistics");
    await heading(page);
    await page.getByRole("radio", { name: "Mi grupo" }).check({ force: true });
    await expect(page.getByRole("list", { name: "Sesiones completadas e interrumpidas" })).toBeVisible();
    await shot(page, "28-docente-estadisticas-grupo");

    const admin = await adminAccount();
    await signIn(page, admin.email, admin.password);
    await page.goto("/users");
    await heading(page);
    await shot(page, "16-admin-usuarios");

    await signIn(page, env.adminEmail, env.adminPassword);
    await page.goto("/admin/activities");
    await shot(page, "17-admin-actividades");
    await page.goto("/admin/expressions");
    await shot(page, "18-admin-expresiones");
  });
});
