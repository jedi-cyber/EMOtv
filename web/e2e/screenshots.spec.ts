import { expect, test, type Page } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { acceptConsent, assignStudent, createAccount, loginToken, readyAccount, signIn, studentIdOf, withToken } from "./support/api";
import { env } from "./support/env";
import { startFakeN8n } from "./support/fakeN8n";

/**
 * Capturas de cada vista para docs/thesis-evidence/screenshots/. Solo se ejecuta con
 * E2E_SCREENSHOTS=1 y contra el stack aislado: todas las cuentas son ficticias
 * (e2e-…@emotv.local) y la cámara es el video simulado sin persona.
 */
const outDir = fileURLToPath(new URL("../../docs/thesis-evidence/screenshots/", import.meta.url));

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

  test("vistas de Psicología y Administración", async ({ page }) => {
    const student = await readyAccount("student");
    await acceptConsent(student);
    const studentId = await studentIdOf(student);
    // Una sesión cancelada sin expresión: el historial muestra un estado real sin datos personales.
    await withToken(await loginToken(student.email, student.password), async (api) => {
      const created = await (await api.post("/sessions", { data: {} })).json() as { id: string };
      await api.post(`/sessions/${created.id}/cancel`);
    });
    const psychologist = await readyAccount("psychologist");
    await assignStudent(psychologist, studentId);

    await signIn(page, psychologist.email, psychologist.password);
    await page.goto("/students");
    await expect(page.getByText(student.studentCode!, { exact: true })).toBeVisible();
    await shot(page, "14-psicologia-estudiantes");
    await page.getByRole("link", { name: `Ver sesiones del estudiante ${student.studentCode}` }).click();
    await shot(page, "15-psicologia-sesiones-del-estudiante");

    await signIn(page, env.adminEmail, env.adminPassword);
    await page.goto("/users");
    await shot(page, "16-admin-usuarios");
    await page.goto("/admin/activities");
    await shot(page, "17-admin-actividades");
    await page.goto("/admin/expressions");
    await shot(page, "18-admin-expresiones");
  });
});
