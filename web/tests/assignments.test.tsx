import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AssignmentsPanel } from "../src/components/AssignmentsPanel";
import { StudentsPage } from "../src/pages/StudentsPage";
import { AuthContext } from "../src/auth/AuthContext";
import { apiRequest } from "../src/api/http";
import type { UserRole } from "../src/auth/types";

const { data } = vi.hoisted(() => ({ data: { value: {} as Record<string, unknown> } }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string) => ({ data: data.value[path] ?? null, loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn() }));

const psychologist = { id: "psy-1", email: "psicologia@ejemplo.local", role: "psychologist" as const, is_active: true };

function withUser(role: UserRole, children: React.ReactNode) {
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@ejemplo.local", role, is_active: true }, token: "test", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter>{children}</MemoryRouter>
  </AuthContext.Provider>);
}

beforeEach(() => {
  vi.mocked(apiRequest).mockReset().mockResolvedValue(undefined as never);
  data.value = {
    "/users/psy-1/assigned-students": [{ id: "st-1", user_id: "u1", student_code: "PRUEBA-01", assigned_at: "2026-10-06T12:00:00Z" }],
    "/students": [
      { id: "st-1", user_id: "u1", student_code: "PRUEBA-01" },
      { id: "st-2", user_id: "u2", student_code: "PRUEBA-02" },
    ],
  };
});

describe("asignación de estudiantes a psicología", () => {
  it("muestra los asignados y ofrece solo los no asignados", () => {
    withUser("admin", <AssignmentsPanel psychologist={psychologist} onClose={vi.fn()} />);
    expect(screen.getByText("PRUEBA-01")).toBeInTheDocument();
    const options = screen.getAllByRole("option").map((option) => option.textContent);
    expect(options).toEqual(["Selecciona un estudiante", "PRUEBA-02"]);
  });

  it("asigna y quita estudiantes con la API de administración", async () => {
    withUser("admin", <AssignmentsPanel psychologist={psychologist} onClose={vi.fn()} />);
    expect(screen.getByRole("button", { name: "Asignar" })).toBeDisabled();
    await userEvent.selectOptions(screen.getByRole("combobox"), "st-2");
    await userEvent.click(screen.getByRole("button", { name: "Asignar" }));
    expect(apiRequest).toHaveBeenCalledWith("/users/psy-1/assigned-students/st-2", expect.objectContaining({ method: "PUT" }));
    await userEvent.click(screen.getByRole("button", { name: "Quitar PRUEBA-01" }));
    expect(apiRequest).toHaveBeenCalledWith("/users/psy-1/assigned-students/st-1", expect.objectContaining({ method: "DELETE" }));
  });

  it("explica al psicólogo sin asignaciones por qué no ve estudiantes", () => {
    data.value["/students"] = [];
    withUser("psychologist", <StudentsPage />);
    expect(screen.getByText(/Aún no tienes estudiantes asignados/)).toBeInTheDocument();
  });

  it("mantiene el mensaje general para administración", () => {
    data.value["/students"] = [];
    withUser("admin", <StudentsPage />);
    expect(screen.getByText("Todavía no hay estudiantes registrados.")).toBeInTheDocument();
  });
});
