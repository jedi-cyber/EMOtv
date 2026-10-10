import { expect, test } from "@playwright/test";
import { createAccount, loginToken, newPassword, readyAccount, signIn } from "./support/api";
import { env } from "./support/env";

test.describe("inicio de sesión", () => {
  test("con credenciales correctas entra al inicio", async ({ page }) => {
    const student = await readyAccount("student");
    await signIn(page, student.email, student.password);
    await expect(page).toHaveURL(/\/dashboard$/);
    // El saludo nunca usa el correo (solo aparece en el menú de la cuenta).
    await expect(page.getByRole("heading", { level: 1 })).toHaveText("Hola");
  });

  test("con una contraseña incorrecta muestra un error sin revelar si el correo existe", async ({ page }) => {
    const student = await readyAccount("student");
    await signIn(page, student.email, `${student.password}-mal`, { expectFailure: true });
    await expect(page.getByRole("alert")).toHaveText("Correo o contraseña incorrectos");
    await expect(page).toHaveURL(/\/login$/);
  });

  test("bloquea la cuenta tras el límite de intentos fallidos, incluso con la contraseña correcta", async ({ page }) => {
    const student = await readyAccount("student");
    for (let attempt = 0; attempt < env.loginMaxFailures; attempt += 1) {
      await signIn(page, student.email, `incorrecta-${attempt}`, { expectFailure: true });
      await expect(page.getByRole("alert")).toHaveText("Correo o contraseña incorrectos");
    }
    await signIn(page, student.email, student.password, { expectFailure: true });
    await expect(page.getByRole("alert")).toContainText("Demasiados intentos de inicio de sesión");
    await expect(page).toHaveURL(/\/login$/);
  });
});

test("primer acceso: obliga a cambiar la contraseña provisional y lleva al consentimiento", async ({ page }) => {
  const student = await createAccount("student");
  await signIn(page, student.email, student.password);
  await expect(page).toHaveURL(/\/first-access$/);
  await expect(page.getByRole("heading", { name: "Protege tu cuenta" })).toBeVisible();

  await page.getByLabel("Contraseña provisional", { exact: true }).fill(student.password);
  const password = newPassword();
  await page.getByLabel("Contraseña nueva", { exact: true }).fill(password);
  await page.getByLabel("Repite la contraseña nueva", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Cambiar contraseña" }).click();
  await expect(page).toHaveURL(/\/consent$/);
  await expect(page.getByRole("heading", { level: 1, name: "Consentimiento" })).toBeVisible();

  // La contraseña nueva sirve y la provisional ya no.
  expect(await loginToken(student.email, password)).toBeTruthy();
  const old = await page.request.post("/auth/token", { form: { username: student.email, password: student.password } });
  expect(old.status()).toBe(401);
});
