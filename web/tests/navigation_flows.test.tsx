import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { App } from "../src/App";
import { AuthContext } from "../src/auth/AuthContext";
import type { UserRole } from "../src/auth/types";

vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({
    data: path === "/activities" ? [{ id: "arms_up_5s", name: "Brazos arriba", description: "Levanta los brazos", required_posture: "arms_up", duration_seconds: 5, repetitions: 1 }]
      : path?.startsWith("/activities/") ? { id: "arms_up_5s", name: "Brazos arriba", description: "Levanta los brazos", required_posture: "arms_up", duration_seconds: 5, repetitions: 1 }
        : path === "/students" ? [{ id: "student-1", user_id: "user-1", student_code: "E001" }]
          : path === "/users" ? [{ id: "user-1", email: "docente@example.com", role: "psychologist", is_active: true }]
            : path === "/analysis/models" ? [{ model_id: "ferplus_onnx", state: "SUPPORTED", reasons: [] }]
              : [],
    loading: false, error: "", connectionError: false, reload: vi.fn(),
  }),
}));

function renderAs(role: UserRole, path = "/dashboard") {
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "persona@example.com", role, is_active: true }, token: "token", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={[path]}><App /></MemoryRouter>
  </AuthContext.Provider>);
}

describe("recorridos principales por rol", () => {
  it("lleva al estudiante directamente del inicio al reconocimiento facial", async () => {
    renderAs("student");
    expect(screen.queryByRole("link", { name: "Abrir analizador" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: "Analizador" }));
    expect(screen.getByRole("heading", { level: 1, name: "Analizador" })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Probar cámara" }).length).toBeGreaterThan(0);
    expect(screen.getByRole("button", { name: "Reconocer mi expresión" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Cuentas y grupos" })).not.toBeInTheDocument();
  });

  it("lleva al docente de su grupo a las sesiones de un usuario", async () => {
    renderAs("psychologist");
    await userEvent.click(screen.getByRole("link", { name: "Mi grupo" }));
    expect(screen.getByRole("heading", { level: 1, name: "Mi grupo" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: /E001/ }));
    expect(screen.getByRole("heading", { level: 1, name: /^Sesiones (de E001|del usuario)$/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Volver a mi grupo/ })).toHaveAttribute("href", "/students");
  });

  it("el docente también abre el analizador para sus sesiones propias", async () => {
    renderAs("psychologist");
    await userEvent.click(screen.getByRole("link", { name: "Analizador" }));
    expect(screen.getByRole("heading", { level: 1, name: "Analizador" })).toBeInTheDocument();
  });

  it("lleva al administrador a cuentas y grupos, sin acceso a sesiones", async () => {
    renderAs("admin");
    await userEvent.click(screen.getByRole("link", { name: "Gestionar cuentas" }));
    expect(screen.getByRole("heading", { level: 1, name: "Cuentas y grupos" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Grupo" })).toBeInTheDocument();
    renderAs("admin", "/sessions");
    expect(await screen.findByRole("heading", { name: "No tienes acceso a esta página" })).toBeInTheDocument();
  });

  it("lleva al superadministrador a las actividades administrables", async () => {
    renderAs("superadmin");
    await userEvent.click(screen.getByRole("navigation", { name: "Navegación principal" }).querySelector('a[href="/admin/activities"]')!);
    expect(screen.getByRole("heading", { level: 1, name: "Administrar actividades" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Crear actividad" })).toBeInTheDocument();
  });

  it("muestra una salida útil para una ruta inexistente", () => {
    renderAs("student", "/modulo-inexistente");
    expect(screen.getByRole("heading", { name: "Página no encontrada" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Volver al inicio" })).toHaveAttribute("href", "/dashboard");
  });
});
