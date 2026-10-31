import { expect, test, type Page } from "@playwright/test";
import { acceptCommitment, acceptConsent, readyAccount, signIn, superadminToken, withToken } from "./support/api";
import { fakeCamera } from "./support/env";

const camera = fakeCamera();

test("la cámara simulada abre en el analizador y cumple el requisito de cámara", async ({ page }) => {
  const student = await readyAccount("student");
  await acceptConsent(student);
  await acceptCommitment(student);
  await signIn(page, student.email, student.password);
  await page.goto("/analysis");
  await page.getByRole("button", { name: "Probar cámara" }).first().click();
  const requirements = page.getByRole("list", { name: "Requisitos para empezar" });
  await expect(requirements.getByRole("listitem").filter({ hasText: "Cámara" }).getByText("Listo")).toBeVisible();
  await expect.poll(() => page.locator("video").evaluate((video: HTMLVideoElement) => video.readyState)).toBeGreaterThanOrEqual(2);
  // Sin protocolo se elige con quién es la sesión antes de empezar.
  await expect(page.getByRole("button", { name: "Empezar el análisis" })).toBeDisabled();
  await page.getByText("Conmigo", { exact: true }).click();
  await expect(page.getByRole("radio", { name: /Conmigo/ })).toBeChecked();
  await expect(page.getByRole("button", { name: "Empezar el análisis" })).toBeEnabled();
  await page.getByRole("button", { name: "Apagar cámara" }).click();
  await expect(page.locator("video")).toHaveJSProperty("srcObject", null);
});

test.describe("análisis con la cámara simulada", () => {
  test.skip(!camera.has_face, "Sin imágenes de rostro: genera el video con scripts/e2e/make_fake_video.py (ver web/e2e/fixtures/README.md).");

  let labels: string[] = [];
  test.beforeAll(async () => {
    labels = await withToken(await superadminToken(), async (api) =>
      (await (await api.get("/expressions")).json() as { label_es: string }[]).map((item) => item.label_es));
  });

  async function openAnalyzer(page: Page) {
    const student = await readyAccount("student");
    await acceptConsent(student);
    await acceptCommitment(student);
    await signIn(page, student.email, student.password);
    await expect(page).toHaveURL(/\/dashboard$/);
    await page.goto("/analysis");
    return student;
  }

  /** Prueba la cámara, empieza y registra la expresión mientras el video muestra el rostro. */
  async function recognize(page: Page) {
    await page.getByRole("button", { name: "Probar cámara" }).first().click();
    await page.getByText("Conmigo", { exact: true }).click();
    await expect(page.getByRole("radio", { name: /Conmigo/ })).toBeChecked();
    const start = page.getByRole("button", { name: "Empezar el análisis" });
    await expect(start).toBeEnabled();
    await start.click();
    // La única confirmación de la sesión, según su público.
    const dialog = page.getByRole("dialog", { name: "Antes de empezar" });
    await dialog.getByRole("checkbox", { name: /Es una sesión mía/ }).check();
    await dialog.getByRole("button", { name: "Empezar la sesión" }).click();
    const register = page.getByRole("button", { name: "Registrar esta expresión" });
    await expect(register).toBeEnabled({ timeout: camera.face_seconds * 1000 });
    await register.click();
    const result = page.getByRole("article").filter({ has: page.locator("#expression-result-title") });
    await expect(result).toBeVisible();
    return result;
  }

  test("llega a un resultado con la expresión en español, la confianza, la información y la limitación", async ({ page }) => {
    await openAnalyzer(page);
    const result = await recognize(page);
    const name = (await result.locator("#expression-result-title").textContent())?.trim() ?? "";
    expect(labels, "la etiqueta viene del catálogo en español").toContain(name);
    expect(name).not.toMatch(/^[a-z_]+$/);
    await expect(result.getByText(/^Confianza del modelo: \d{1,3} %$/)).toBeVisible();
    await expect(result.getByRole("heading", { name: "¿Qué es?" })).toBeVisible();
    await expect(result.getByRole("heading", { name: "¿Cómo se reconoce en el rostro?" })).toBeVisible();
    await expect(result.getByRole("note")).toContainText(/no determina/);
  });

  test("finaliza sin actividad y el historial conserva la expresión registrada", async ({ page }) => {
    await openAnalyzer(page);
    const result = await recognize(page);
    const name = (await result.locator("#expression-result-title").textContent())?.trim() ?? "";
    await page.getByRole("button", { name: "Finalizar sin actividad" }).click();
    await expect(page.getByText("Sesión finalizada sin actividad. Tu expresión quedó registrada.").first()).toBeVisible();

    await page.goto("/sessions");
    const row = page.getByRole("row").filter({ hasText: name });
    await expect(row).toHaveCount(1);
    await expect(row).toContainText("Omitida");
    await expect(row).toContainText(/\d{1,3} %/);
  });

  test("la actividad no avanza de paso cuando nadie está frente a la cámara", async ({ page }) => {
    await openAnalyzer(page);
    await recognize(page);
    const recommended = page.getByRole("button", { name: "Realizar actividad" });
    if (await recommended.isVisible()) await recommended.click();
    else await page.getByRole("button", { name: "Continuar con la actividad" }).click();

    await expect(page.getByText(/^Paso 1 de \d+:/)).toBeVisible();
    // El video pasa al tramo sin persona: el servidor avisa que no ve a nadie.
    await expect(page.getByRole("status").filter({ hasText: "No se te ve en la cámara" }))
      .toBeVisible({ timeout: (camera.face_seconds + 20) * 1000 });
    const progress = page.locator(".progress-label").filter({ hasText: "Progreso" });
    await expect(progress).toContainText("0 %");
    await page.waitForTimeout(8_000);
    await expect(page.getByText(/^Paso 1 de \d+:/)).toBeVisible();
    await expect(progress).toContainText("0 %");

    // Cancelar apaga la cámara y conserva la expresión.
    await page.getByRole("button", { name: "Cancelar análisis" }).click();
    await page.getByRole("alertdialog").getByRole("button", { name: "Cancelar sesión" }).click();
    await expect(page.getByText("Actividad cancelada. Tu expresión quedó registrada.")).toBeVisible();
  });
});
