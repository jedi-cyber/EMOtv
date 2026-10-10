import { expect, test } from "@playwright/test";
import { readyAccount, signIn } from "./support/api";
import { env } from "./support/env";
import { IN_SCOPE_ANSWER, OUT_OF_SCOPE_ANSWER, startFakeN8n, triggers, type FakeN8n } from "./support/fakeN8n";

test.describe("Emi con el workflow de n8n simulado", () => {
  test.skip(!env.fakeN8n, "Activa E2E_FAKE_N8N=1 y apunta N8N_WEBHOOK_URL del backend al n8n falso (docs/testing/e2e.md).");

  let n8n: FakeN8n;
  test.beforeAll(async () => { n8n = await startFakeN8n(env.fakeN8nPort, env.fakeN8nKey); });
  test.afterAll(async () => { await n8n?.close(); });

  test("responde dentro y fuera del alcance, y explica cuando el modelo de lenguaje no está disponible", async ({ page }) => {
    const student = await readyAccount("student");
    await signIn(page, student.email, student.password);
    await expect(page).toHaveURL(/\/dashboard$/);
    await page.getByRole("button", { name: "Abrir a Emi" }).click();
    const log = page.getByRole("log", { name: "Conversación con Emi" });
    const question = page.getByLabel("Tu pregunta", { exact: true });
    const send = page.getByRole("button", { name: "Enviar" });

    await question.fill("¿Qué es una actividad en EMOtv?");
    await send.click();
    await expect(log.getByText(IN_SCOPE_ANSWER)).toBeVisible();
    const first = n8n.requests.at(-1)!;
    expect(first.key).toBeTruthy();
    expect(first.body.question).toBe("¿Qué es una actividad en EMOtv?");
    expect(first.body.request_id).toBeTruthy();
    expect(Array.isArray(first.body.history)).toBe(true);
    // Los resultados personales no se envían al LLM.
    const sent = JSON.stringify(first.body);
    expect(sent).not.toContain(student.email);
    expect(sent).not.toContain(student.studentCode!);

    await question.fill(`¿Me das una ${triggers.outOfScope} de cocina?`);
    await send.click();
    await expect(log.getByText(OUT_OF_SCOPE_ANSWER)).toBeVisible();
    expect(n8n.requests.at(-1)!.body.history.map((item) => item.content)).toContain(IN_SCOPE_ANSWER);

    const failing = `${triggers.llmDown}: ¿cómo funciona Emi?`;
    await question.fill(failing);
    await send.click();
    await expect(page.getByRole("alert")).toContainText("no está disponible");
    // La pregunta no se pierde: vuelve al campo para reenviarla.
    await expect(question).toHaveValue(failing);
    await expect(log.getByText(failing)).toHaveCount(0);
  });
});
