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
          : path === "/auth/users" ? [{ id: "user-1", email: "admin@example.com", role: "admin", is_active: true }]
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
    await userEvent.click(screen.getByRole("link", { name: "Abrir analizador" }));
    expect(screen.getByRole("heading", { level: 1, name: "Reconoce tu expresión y recibe una actividad" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Probar cámara" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reconocer mi expresión" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Usuarios" })).not.toBeInTheDocument();
  });

  it("lleva a Psicología del inicio al estudiante y sus sesiones", async () => {
    renderAs("psychologist");
    await userEvent.click(screen.getByRole("link", { name: "Ver estudiantes" }));
    expect(screen.getByRole("heading", { level: 1, name: "Seguimiento de estudiantes" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("link", { name: /E001/ }));
    expect(screen.getByRole("heading", { level: 1, name: "Sesiones del estudiante" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Volver a estudiantes/ })).toHaveAttribute("href", "/students");
  });

  it("permite a Administración ir a usuarios y actividades administrables", async () => {
    renderAs("admin");
    await userEvent.click(screen.getByRole("link", { name: "Ver usuarios" }));
    expect(screen.getByRole("heading", { level: 1, name: "Usuarios" })).toBeInTheDocument();
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
