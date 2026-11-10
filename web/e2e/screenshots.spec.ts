import { expect, test, type APIRequestContext, type Locator, type Page } from "@playwright/test";
import { fileURLToPath } from "node:url";
import { acceptConsent, adminAccount, adminToken, assignStudent, createAccount, loginToken, readyAccount, signIn, studentIdOf, withToken } from "./support/api";
import { env, fakeCamera } from "./support/env";
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
  // Las capturas se versionan: la cámara simulada no puede mostrar a ninguna persona.
  test.skip(fakeCamera().has_face, "Las capturas usan el video sin persona: genera e2e/fixtures/generated/empty.y4m con "
    + "make_fake_video.py --empty-only y apunta E2E_FAKE_VIDEO a él (docs/thesis-evidence/README.md).");
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

    // Las actividades de posturas están congeladas (ACTIVITIES_ENABLED=false): sus capturas 09 y 10 no se regeneran.

    await page.goto("/sessions");
    await expect(page.getByRole("link", { name: "Nuevo análisis" })).toBeVisible();
    await shot(page, "11-mis-sesiones-vacio");

    const n8n = await startFakeN8n(env.fakeN8nPort, env.fakeN8nKey);
    try {
      await page.goto("/dashboard");
      await page.getByRole("button", { name: "Abrir a Emi" }).click();
      await page.getByLabel("Tu pregunta", { exact: true }).fill("¿Qué es un protocolo en EMOtv?");
      await page.getByRole("button", { name: "Enviar" }).click();
      await expect(page.getByRole("log").getByText(/receta guardada/)).toBeVisible();
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
    await page.goto("/statistics");
    await heading(page);
    // El docente ve las estadísticas de su grupo sin elegir nada.
    await expect(page.getByRole("list", { name: "Sesiones completadas e interrumpidas" })).toBeVisible();
    await shot(page, "28-docente-estadisticas-grupo");

    const admin = await adminAccount();
    await signIn(page, admin.email, admin.password);
    await page.goto("/users");
    await heading(page);
    await shot(page, "16-admin-usuarios");

    await signIn(page, env.adminEmail, env.adminPassword);
    await page.goto("/admin/expressions");
    await shot(page, "18-admin-expresiones");
  });

  test("sesión de psicoeducación con un niño, reporte y Por revisar", async ({ page, context }) => {
    test.setTimeout(240_000);
    // El banco inicial de dibujos lo agrega el administrador; la plantilla de partida lo usa.
    await withToken(await adminToken(), async (api) => { await api.post("/stimuli/initial-bank"); });
    const student = await readyAccount("student");
    await acceptConsent(student);
    const studentId = await studentIdOf(student);
    const psychologist = await readyAccount("psychologist");
    await assignStudent(psychologist, studentId);
    const protocolId = await withToken(await loginToken(student.email, student.password), async (api) => {
      await acceptCommitment(api);
      const starter = await api.post("/protocols/starter");
      expect(starter.status(), await starter.text()).toBe(201);
      const drawings = (await starter.json() as { steps: { stimulus_id: string | null }[] }).steps
        .map((step) => step.stimulus_id).filter((id): id is string => !!id);
      const response = await api.post("/protocols", { data: {
        name: "Emociones en casa y en el colegio", for_children: true,
        description: "Reconocer emociones en dibujos, dibujar una cara y emparejar emociones.",
        steps: [
          { kind: "recognition", stimulus_id: drawings[0], exposure_seconds: 60, option_count: 3 },
          { kind: "recognition", stimulus_id: drawings[1], exposure_seconds: 60, option_count: 3,
            situation: "Se le cayó el helado al suelo." },
          { kind: "drawing", exposure_seconds: 120 },
          { kind: "game", game_type: "matching", rounds: 2, exposure_seconds: 60 },
        ],
        supports: { pictograms: true, large_controls: true, read_aloud: true, no_time_limit: false, pause: "normal" },
      } });
      expect(response.status(), await response.text()).toBe(201);
      return (await response.json() as { id: string }).id;
    });

    await signIn(page, student.email, student.password);
    await page.goto("/protocols");
    await heading(page);
    await page.locator("li.row-card").filter({ hasText: "Emociones en casa y en el colegio" })
      .getByRole("button", { name: "Editar" }).first().click();
    await expect(page.getByRole("dialog")).toBeVisible();
    await shot(page, "30-protocolo-ninos-apoyos", false);
    await page.keyboard.press("Escape");

    await page.goto(`/analysis?protocol=${encodeURIComponent(protocolId)}`);
    await expect(page.getByText(/Sigue sus pasos:/)).toBeVisible();
    await shot(page, "31-analizador-protocolo-ninos");
    await page.getByRole("button", { name: "Empezar la sesión" }).click();
    const dialog = page.getByRole("dialog", { name: "Antes de empezar" });
    // La primera sesión con un niño muestra una sola vez el aviso sobre datos de menores.
    const authorization = dialog.getByRole("checkbox", { name: /tutor autorizó por escrito/ });
    await authorization.waitFor();
    const notice = dialog.getByRole("checkbox", { name: "Leí el aviso sobre datos de menores" });
    if (await notice.isVisible()) await notice.check();
    await authorization.check();
    await expect(dialog.getByRole("button", { name: "Empezar la sesión" })).toBeEnabled();
    await dialog.getByRole("button", { name: "Empezar la sesión" }).click();
    await expect(page).toHaveURL(/\/guided\//);
    const sessionId = decodeURIComponent(page.url().split("/guided/")[1].split(/[?#/]/)[0]);

    const opened = context.waitForEvent("page");
    await page.getByRole("button", { name: "Abrir la pantalla de la persona" }).click();
    const person = await opened;
    await person.setViewportSize({ width: 1280, height: 800 });
    await person.waitForLoadState();
    // Con la pantalla de la persona abierta, quien conduce empieza la sesión.
    await page.getByRole("button", { name: "Empezar", exact: true }).click();

    // La persona responde con los botones; cada tipo de paso se captura la primera vez que aparece.
    const taken = new Set<string>();
    const once = async (target: Page, name: string, ready: Locator) => {
      if (taken.has(name) || !(await ready.first().isVisible())) return;
      taken.add(name);
      await target.waitForTimeout(600);
      await target.screenshot({ path: `${outDir}${name}.png`, animations: "disabled", caret: "hide" });
    };
    const options = person.locator("button.recognition-option:enabled");
    const canvas = person.locator("canvas.drawing-canvas");
    const finished = person.getByText("La sesión terminó. Gracias.");
    const deadline = Date.now() + 180_000;
    while (!(await finished.isVisible()) && Date.now() < deadline) {
      await once(person, "32-persona-reconocimiento", person.locator(".recognition-options"));
      await once(page, "33-conductor-reconocimiento", page.getByRole("heading", { name: /^¿Qué emoción/ }));
      await once(person, "34-persona-juego", person.locator(".matching-game"));
      const done = person.getByRole("button", { name: "Terminé" });
      if (await canvas.isVisible() && await done.isVisible() && await done.isDisabled()) {
        const box = (await canvas.boundingBox())!;
        const cx = box.x + box.width / 2, cy = box.y + box.height / 2, r = Math.min(box.width, box.height) / 3;
        await person.mouse.move(cx + r, cy);
        await person.mouse.down();
        for (let a = 0; a <= 40; a++) await person.mouse.move(cx + r * Math.cos(a * Math.PI / 20), cy + r * Math.sin(a * Math.PI / 20));
        await person.mouse.up();
        for (const [dx, dy] of [[-r / 3, -r / 4], [r / 3, -r / 4]]) {
          await person.mouse.move(cx + dx, cy + dy); await person.mouse.down();
          await person.mouse.move(cx + dx + 4, cy + dy + 4); await person.mouse.up();
        }
        await person.mouse.move(cx - r / 2, cy + r / 4); await person.mouse.down();
        for (let a = 0; a <= 20; a++) await person.mouse.move(cx + (r / 2) * Math.cos(Math.PI - a * Math.PI / 20), cy + r / 4 + (r / 4) * Math.sin(a * Math.PI / 20));
        await person.mouse.up();
        await once(person, "35-persona-dibujo", canvas);
        await done.click();
        continue;
      }
      const next = person.getByRole("button", { name: /^(Siguiente|Terminar el juego)$/ });
      if (await next.isVisible() && await next.isEnabled()) { await next.click(); continue; }
      if (await options.count()) { await options.first().click(); await person.waitForTimeout(400); continue; }
      const help = person.getByRole("button", { name: "Ayuda" });
      if (await help.isVisible() && await help.isEnabled()) { await help.click(); continue; }
      await person.waitForTimeout(500);
    }
    await expect(finished).toBeVisible();
    await expect(page.getByText("La sesión terminó y quedó registrada.")).toBeVisible({ timeout: 20_000 });
    await page.evaluate(() => { (document.activeElement as HTMLElement | null)?.blur(); window.scrollTo(0, 0); });
    await shot(page, "36-conductor-sesion-terminada");

    await page.goto(`/sessions/${encodeURIComponent(sessionId)}`);
    await heading(page);
    await shot(page, "37-sesion-resultados-educativos");

    await withToken(await loginToken(student.email, student.password), async (api) => {
      const created = await api.post(`/sessions/${sessionId}/report`);
      expect(created.status(), await created.text()).toBe(201);
      const { id } = await created.json() as { id: string };
      await api.put(`/reports/${id}`, { data: { narrative:
        "La sesión se realizó con el tutor presente. Se aplicaron los cuatro pasos del protocolo sin interrupciones." } });
      expect((await api.post(`/reports/${id}/submit`)).status()).toBe(200);
    });
    await page.goto(`/sessions/${encodeURIComponent(sessionId)}/report`);
    await heading(page);
    await shot(page, "38-reporte");

    await signIn(page, psychologist.email, psychologist.password);
    await withToken(await loginToken(psychologist.email, psychologist.password), async (api) => { await acceptCommitment(api); });
    await page.goto("/reviews");
    await heading(page);
    await shot(page, "39-docente-por-revisar");
  });
});
