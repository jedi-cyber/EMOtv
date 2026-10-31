import { expect, test } from "@playwright/test";
import { acceptCommitment, assignStudent, loginToken, readyAccount, signIn, studentIdOf, withToken } from "./support/api";

test("el Docente solo ve a los usuarios que administración asignó a su grupo", async ({ page }) => {
  const student = await readyAccount("student");
  const studentId = await studentIdOf(student);
  const psychologist = await readyAccount("psychologist");
  await acceptCommitment(psychologist);

  await signIn(page, psychologist.email, psychologist.password);
  await page.goto("/students");
  await expect(page.getByRole("heading", { level: 1, name: "Mi grupo" })).toBeVisible();
  await expect(page.getByText(/Aún no tienes usuarios en tu grupo/)).toBeVisible();
  await expect(page.getByText(student.studentCode!)).toHaveCount(0);

  // El permiso se aplica en FastAPI, no solo en la interfaz.
  const token = await loginToken(psychologist.email, psychologist.password);
  await withToken(token, async (api) => {
    expect((await api.get(`/students/${encodeURIComponent(studentId)}`)).status()).toBe(403);
    expect((await api.get(`/sessions?student_id=${encodeURIComponent(studentId)}`)).status()).toBe(403);
  });

  await assignStudent(psychologist, studentId);
  await page.reload();
  await expect(page.getByText(student.studentCode!, { exact: true })).toBeVisible();
  await page.getByRole("link", { name: `Ver sesiones del usuario ${student.studentCode}` }).click();
  await expect(page.getByRole("heading", { level: 1, name: `Sesiones de ${student.studentCode}` })).toBeVisible();
  await expect(page.getByText("Este usuario todavía no tiene sesiones registradas.")).toBeVisible();
});
