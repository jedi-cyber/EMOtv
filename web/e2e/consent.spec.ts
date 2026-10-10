import { expect, test } from "@playwright/test";
import { loginToken, readyAccount, signIn, withToken } from "./support/api";

test("el estudiante acepta la política vigente y después revoca su consentimiento", async ({ page }) => {
  const student = await readyAccount("student");
  const policy = await withToken(await loginToken(student.email, student.password), async (api) =>
    await (await api.get("/consent-policy")).json() as { mode: string; available: boolean });
  test.skip(policy.mode === "development", "CONSENT_MODE=development no pide consentimiento; usa demo.");
  expect(policy.available, "debe haber una política de consentimiento activa").toBe(true);

  await signIn(page, student.email, student.password);
  await page.goto("/consent");
  const consentCard = page.locator("article").filter({ has: page.getByRole("heading", { name: "Tu consentimiento" }) });
  await expect(consentCard.getByText("Sin aceptar", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Leer y aceptar" }).first().click();
  const dialog = page.getByRole("dialog");
  const accept = dialog.getByRole("button", { name: "Aceptar la política" });
  await expect(accept).toBeDisabled();
  await dialog.getByRole("checkbox", { name: /He leído la política/ }).check();
  await accept.click();
  await expect(page).toHaveURL(/\/analysis$/);
  // Con consentimiento vigente el requisito del analizador queda listo.
  const requirements = page.getByRole("list", { name: "Requisitos para empezar" });
  await expect(requirements.getByRole("listitem").filter({ hasText: "Consentimiento vigente" }).getByText("Listo")).toBeVisible();

  await page.goto("/consent");
  await expect(consentCard.getByText("Activo", { exact: true })).toBeVisible();
  await consentCard.getByRole("button", { name: "Revocar consentimiento" }).click();
  const confirm = page.getByRole("alertdialog", { name: "Revocar consentimiento" });
  await expect(confirm).toContainText("no podrás iniciar nuevos análisis faciales");
  await confirm.getByRole("button", { name: "Revocar" }).click();
  await expect(page.getByText(/Consentimiento revocado/)).toBeVisible();
  await expect(consentCard.getByText("Revocado", { exact: true })).toBeVisible();

  // Sin consentimiento, el analizador no deja empezar.
  await page.goto("/analysis");
  await expect(requirements.getByRole("link", { name: "Revisar consentimiento" })).toBeVisible();
  await expect(page.getByRole("button", { name: "Reconocer mi expresión" })).toBeDisabled();
});
