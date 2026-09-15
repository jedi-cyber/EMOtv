import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AuthContext } from "../src/auth/AuthContext";
import { ProtectedRoute } from "../src/auth/ProtectedRoute";
import { RoleRoute } from "../src/auth/RoleRoute";
import { AppLayout } from "../src/layouts/AppLayout";
import type { UserRole } from "../src/auth/types";

function renderRole(role: UserRole | null, allowed: UserRole[], loading = false) {
  return render(<AuthContext.Provider value={{ user: role ? { id: "u", email: "u@example.com", role, is_active: true } : null, token: role ? "token" : null, loading, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={["/private"]}><Routes>
      <Route path="/login" element={<p>Login público</p>} /><Route path="/unauthorized" element={<p>Acceso denegado</p>} />
      <Route element={<ProtectedRoute />}><Route path="/private" element={<RoleRoute allowed={allowed}><AppLayout /></RoleRoute>} /></Route>
    </Routes></MemoryRouter>
  </AuthContext.Provider>);
}

describe("rutas y navegación por rol", () => {
  it("redirige al login sin autenticación", () => { renderRole(null, ["admin"]); expect(screen.getByText("Login público")).toBeInTheDocument(); });
  it("espera la consulta de identidad", () => { renderRole(null, ["admin"], true); expect(screen.getByRole("status")).toHaveTextContent("Verificando sesión"); });
  it.each(["student", "psychologist"] as UserRole[])("impide administración a %s", (role) => { renderRole(role, ["admin"]); expect(screen.getByText("Acceso denegado")).toBeInTheDocument(); });
  it.each(["student", "psychologist", "admin"] as UserRole[])("muestra navegación adecuada para %s", (role) => {
    renderRole(role, [role]);
    expect(screen.getByRole("link", { name: "Saltar al contenido" })).toHaveAttribute("href", "#main-content");
    expect(screen.queryByRole("link", { name: "Usuarios" }) !== null).toBe(role === "admin");
    expect(screen.queryByRole("link", { name: "Estudiantes" }) !== null).toBe(role === "psychologist");
    expect(screen.queryByRole("link", { name: "Mis sesiones" }) !== null).toBe(role === "student");
  });
});
