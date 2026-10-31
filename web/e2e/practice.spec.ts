import { expect, test, type BrowserContext, type Page } from "@playwright/test";
import { acceptCommitment, acceptConsent, loginToken, readyAccount, signIn, withToken, type Account } from "./support/api";
import { fakeCamera } from "./support/env";

const camera = fakeCamera();

/** Protocolo para adultos con un solo ejercicio de práctica, sin ilustración. */
async function practiceProtocol(account: Account, maxSeconds: number): Promise<string> {
  return withToken(await loginToken(account.email, account.password), async (api) => {
    const response = await api.post("/protocols", { data: {
      name: `Práctica e2e ${Date.now()}`, description: "", for_children: false,
      steps: [{ kind: "practice", target_expression: "happiness", hold_seconds: 2, exposure_seconds: maxSeconds }],
    } });
    expect(response.status(), await response.text()).toBe(201);
    return (await response.json() as { id: string }).id;
  });
}

/** Desde el Analizador, con el protocolo elegido y la única confirmación, hasta la pantalla de quien conduce. */
async function startFromAnalyzer(page: Page, protocolId: string) {
  await page.goto(`/analysis?protocol=${encodeURIComponent(protocolId)}`);
  await expect(page.getByText(/Sigue sus pasos: calibración, 1 ejercicio de práctica\./)).toBeVisible();
  await page.getByRole("button", { name: "Probar cámara" }).first().click();
  const requirements = page.getByRole("list", { name: "Requisitos para empezar" });
  await expect(requirements.getByRole("listitem").filter({ hasText: "Cámara" }).getByText("Listo")).toBeVisible();
  await page.getByRole("button", { name: "Empezar la sesión" }).click();
  const dialog = page.getByRole("dialog", { name: "Antes de empezar" });
  await dialog.getByRole("checkbox", { name: /autorización firmada de la persona adulta/ }).check();
  await dialog.getByRole("button", { name: "Empezar la sesión" }).click();
  await expect(page).toHaveURL(/\/guided\//);
  await expect(page.getByRole("heading", { name: "Sesión con protocolo" })).toBeVisible();
  await expect(page.getByText(/^Código de la sesión:/)).toBeVisible();
}

/** La pantalla de la persona abre en otra ventana y empieza a enviar cuadros de la cámara simulada. */
async function openParticipant(context: BrowserContext, conductor: Page): Promise<Page> {
  const opened = context.waitForEvent("page");
  await conductor.getByRole("button", { name: "Abrir la pantalla de la persona" }).click();
  const participant = await opened;
  await participant.waitForLoadState();
  await expect(participant.getByRole("button", { name: "Quiero parar" })).toBeVisible();
  return participant;
}

async function prepare(page: Page, maxSeconds: number) {
  const student = await readyAccount("student");
  await acceptConsent(student);
  await acceptCommitment(student);
  const protocolId = await practiceProtocol(student, maxSeconds);
  await signIn(page, student.email, student.password);
  await startFromAnalyzer(page, protocolId);
}

test("una sesión con un ejercicio de práctica empieza en el Analizador y se puede terminar", async ({ page, context }) => {
  await prepare(page, 6);
  await expect(page.getByRole("heading", { name: "Calibración neutral" })).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "Mostrar la señal a la persona en los ejercicios de práctica" })).toBeChecked();
  const participant = await openParticipant(context, page);
  await page.getByRole("button", { name: "Terminar la sesión" }).click();
  await expect(page.getByText(/La sesión se detuvo/)).toBeVisible();
  await expect(participant.getByText("La sesión terminó. Gracias.")).toBeVisible({ timeout: 20_000 });
});

test.describe("ejercicio de práctica con la cámara simulada", () => {
  test.skip(!camera.has_face, "Sin imágenes de rostro la calibración no termina: genera el video con scripts/e2e/make_fake_video.py (ver web/e2e/fixtures/README.md).");

  test("recorre la calibración y el ejercicio hasta que la sesión termina", async ({ page, context }) => {
    // Al vencer el tiempo el ejercicio termina igual: no depende de que la imagen muestre alegría.
    const maxSeconds = 6;
    await prepare(page, maxSeconds);
    const participant = await openParticipant(context, page);

    // La calibración necesita el tramo con rostro; si cae en el tramo sin persona, se repite.
    const practiceHeading = page.getByRole("heading", { name: "Expresión pedida: Alegría" });
    await expect(async () => {
      if (await practiceHeading.isVisible()) return;
      const start = page.getByRole("button", { name: "Iniciar calibración" });
      if (await start.isVisible()) await start.click();
      await expect(practiceHeading).toBeVisible({ timeout: 8_000 });
    }).toPass({ timeout: (camera.face_seconds + camera.empty_seconds + 30) * 1000 });

    // La persona ve solo la instrucción y la señal; nunca la expresión detectada ni probabilidades.
    await expect(participant.getByText("Muestra alegría")).toBeVisible();
    await expect(participant.getByRole("meter", { name: "Señal del ejercicio" })).toBeVisible();
    await expect(participant.locator("body")).not.toContainText(/%|confianza|probabilidad/i);
    await expect(page.getByRole("button", { name: "Saltar este ejercicio" })).toBeVisible();

    await expect(page.getByText("La sesión terminó y quedó registrada.")).toBeVisible({ timeout: (maxSeconds + 15) * 1000 });
    const results = page.getByRole("region", { name: "Ejercicios de práctica" }).or(
      page.locator("section").filter({ has: page.getByRole("heading", { name: "Ejercicios de práctica" }) }));
    await expect(results).toContainText(/Logró la expresión pedida en [01] de 1 ejercicio\./);
    await expect(results).toContainText(/Paso 1 · Alegría · /);
    await expect(participant.getByText("La sesión terminó. Gracias.")).toBeVisible({ timeout: 20_000 });
  });
});
