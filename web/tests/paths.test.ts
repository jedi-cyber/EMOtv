import { describe, expect, it } from "vitest";
import { paths } from "../src/routes/paths";

describe("rutas canónicas del frontend", () => {
  it("construye detalles y consultas sin alterar la jerarquía", () => {
    expect(paths.activity("brazo/izquierdo")).toBe("/activities/brazo%2Fizquierdo");
    expect(paths.session("sesión 1")).toBe("/sessions/sesi%C3%B3n%201");
    expect(paths.studentSessions("alumno 1")).toBe("/students/alumno%201/sessions");
    expect(paths.analysisForActivity("brazos arriba")).toBe("/analysis?activity=brazos%20arriba");
  });
});
