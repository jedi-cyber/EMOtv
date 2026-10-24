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

const accounts = ["uno", "dos", "tres"].map((name, index) =>
  ({ id: `u${index + 1}`, email: `${name}@ejemplo.local`, role: "student" as const, is_active: true }));

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
      { id: "st-3", user_id: "u3", student_code: "PRUEBA-03" },
    ],
  };
});

describe("grupos de docentes", () => {
  it("muestra los asignados por correo y ofrece casillas solo para los no asignados", () => {
    withUser("admin", <AssignmentsPanel psychologist={psychologist} accounts={accounts} onClose={vi.fn()} />);
    const dialog = screen.getByRole("dialog", { name: "Grupo de psicologia@ejemplo.local" });
    expect(dialog).toHaveTextContent("uno@ejemplo.local");
    const boxes = screen.getAllByRole("checkbox").map((box) => box.closest("label")?.textContent);
    expect(boxes).toEqual(["Seleccionar todos", "dos@ejemplo.local (PRUEBA-02)", "tres@ejemplo.local (PRUEBA-03)"]);
  });

  it("asigna varios usuarios a la vez y quita uno del grupo", async () => {
    withUser("admin", <AssignmentsPanel psychologist={psychologist} accounts={accounts} onClose={vi.fn()} />);
    expect(screen.getByText(/pasará a este grupo/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Asignar" })).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: "Seleccionar todos" }));
    await userEvent.click(screen.getByRole("button", { name: "Asignar 2 usuarios" }));
    expect(apiRequest).toHaveBeenCalledWith("/users/psy-1/assigned-students/st-2", expect.objectContaining({ method: "PUT" }));
    expect(apiRequest).toHaveBeenCalledWith("/users/psy-1/assigned-students/st-3", expect.objectContaining({ method: "PUT" }));
    await userEvent.click(screen.getByRole("button", { name: "Quitar uno@ejemplo.local" }));
    expect(apiRequest).toHaveBeenCalledWith("/users/psy-1/assigned-students/st-1", expect.objectContaining({ method: "DELETE" }));
  });

  it("filtra por correo y deja marcados los que fallaron", async () => {
    vi.mocked(apiRequest).mockRejectedValueOnce(new Error("falló"));
    withUser("admin", <AssignmentsPanel psychologist={psychologist} accounts={accounts} onClose={vi.fn()} />);
    await userEvent.type(screen.getByRole("searchbox", { name: "Buscar por correo o código" }), "tres");
    expect(screen.queryByRole("checkbox", { name: /dos@/ })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: /tres@/ }));
    await userEvent.click(screen.getByRole("button", { name: "Asignar 1 usuario" }));
    expect(screen.getByText("No se pudo asignar a: tres@ejemplo.local.")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: /tres@/ })).toBeChecked();
  });

  it("explica al docente sin grupo por qué no ve usuarios", () => {
    data.value["/students"] = [];
    withUser("psychologist", <StudentsPage />);
    expect(screen.getByText(/Aún no tienes usuarios en tu grupo/)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/estudiante/i);
  });
});
