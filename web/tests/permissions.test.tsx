import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AuthContext } from "../src/auth/AuthContext";
import { ProtectedRoute } from "../src/auth/ProtectedRoute";
import { RoleRoute } from "../src/auth/RoleRoute";
import { AppLayout, breadcrumbs } from "../src/layouts/AppLayout";
import { App } from "../src/App";
import type { UserRole } from "../src/auth/types";
import { navigationByRole } from "../src/routes/navigation";
import { API_RECOVERED_EVENT, API_UNAVAILABLE_EVENT } from "../src/api/http";

function renderRole(role: UserRole | null, allowed: UserRole[], loading = false) {
  return render(<AuthContext.Provider value={{ user: role ? { id: "u", email: "u@example.com", role, is_active: true } : null, token: role ? "token" : null, loading, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={["/private"]}><Routes>
      <Route path="/login" element={<p>Login público</p>} /><Route path="/unauthorized" element={<p>Acceso denegado</p>} />
      <Route element={<ProtectedRoute />}><Route path="/private" element={<RoleRoute allowed={allowed}><AppLayout /></RoleRoute>} /></Route>
    </Routes></MemoryRouter>
  </AuthContext.Provider>);
}

describe("rutas y navegación por rol", () => {
  it("obliga a reemplazar la clave provisional antes de abrir módulos", () => {
    render(<AuthContext.Provider value={{ user: { id: "u", email: "student@example.com", role: "student", is_active: true, must_change_password: true }, token: "token", loading: false, notice: "", login: vi.fn(), changePassword: vi.fn(), logout: vi.fn() }}>
      <MemoryRouter initialEntries={["/analysis"]}><App /></MemoryRouter>
    </AuthContext.Provider>);
    expect(screen.getByRole("heading", { name: "Protege tu cuenta" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: /Reconoce tu expresión/ })).not.toBeInTheDocument();
  });
  it("mantiene los módulos en una configuración por rol", () => {
    expect(navigationByRole.student.map((item) => item.to)).toEqual(["/dashboard", "/activities", "/analysis", "/consent", "/sessions"]);
    expect(navigationByRole.psychologist.some((item) => item.to === "/users")).toBe(false);
    expect(navigationByRole.admin.some((item) => item.to === "/admin/activities")).toBe(true);
  });
  it("redirige al login sin autenticación", () => { renderRole(null, ["admin"]); expect(screen.getByText("Login público")).toBeInTheDocument(); });
  it("espera la consulta de identidad", () => { renderRole(null, ["admin"], true); expect(screen.getByRole("status")).toHaveTextContent("Verificando sesión"); });
  it.each(["student", "psychologist"] as UserRole[])("impide administración a %s", (role) => { renderRole(role, ["admin"]); expect(screen.getByText("Acceso denegado")).toBeInTheDocument(); });
  it.each(["student", "psychologist", "admin"] as UserRole[])("muestra navegación adecuada para %s", (role) => {
    renderRole(role, [role]);
    expect(screen.getByRole("link", { name: "Saltar al contenido" })).toHaveAttribute("href", "#main-content");
    expect(screen.queryByRole("link", { name: "Usuarios" }) !== null).toBe(role === "admin");
    expect(screen.queryByRole("link", { name: "Estudiantes" }) !== null).toBe(role !== "student");
    expect(screen.queryByRole("link", { name: "Mis sesiones" }) !== null).toBe(role === "student");
    expect(screen.getByText("u@example.com")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Menú de usuario" })).toHaveAttribute("aria-expanded", "false");
    expect(screen.getByRole("button", { name: "Menú de usuario" }).querySelector(".user-menu-chevron")).toHaveAttribute("aria-hidden", "true");
    const homeLink = screen.getByRole("navigation", { name: "Navegación principal" }).querySelector('a[href="/dashboard"]');
    expect(homeLink).toHaveTextContent("Inicio");
    expect(homeLink?.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
    const roleBadge = screen.getByRole("button", { name: "Menú de usuario" }).querySelector(".user-role-badge");
    expect(roleBadge).toHaveTextContent(role === "student" ? "Estudiante" : role === "psychologist" ? "Psicología" : "Administración");
    expect(screen.queryByRole("button", { name: "Cerrar sesión" })).not.toBeInTheDocument();
  });
  it("no muestra funciones fuera del rol y ofrece alumnos a administración", () => {
    renderRole("student", ["student"]);
    expect(screen.queryByRole("link", { name: "Usuarios" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Estudiantes" })).not.toBeInTheDocument();
  });
  it("muestra breadcrumbs jerárquicos sin identificadores privados", () => {
    expect(breadcrumbs("/sessions/secret-id", "student")).toEqual([
      { label: "Inicio", to: "/dashboard" },
      { label: "Mis sesiones", to: "/sessions" },
      { label: "Detalle de sesión" },
    ]);
    expect(breadcrumbs("/students/123/sessions", "psychologist").at(-1)?.label).toBe("Sesiones del estudiante");
  });
  it("marca el módulo activo y ofrece regreso contextual en el detalle", () => {
    render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "token", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
      <MemoryRouter initialEntries={["/sessions/secret-id"]}><Routes>
        <Route element={<AppLayout />}><Route path="sessions/:sessionId" element={<p>Detalle</p>} /></Route>
      </Routes></MemoryRouter>
    </AuthContext.Provider>);
    const mainNav = screen.getByRole("navigation", { name: "Navegación principal" });
    expect(mainNav.querySelector('a[href="/sessions"]')).toHaveAttribute("aria-current", "page");
    const crumbs = screen.getByRole("navigation", { name: "Ruta de navegación" });
    expect(crumbs.querySelector('a[href="/sessions"]')).toHaveTextContent("Mis sesiones");
    expect(crumbs.querySelector('[aria-current="page"]')).toHaveTextContent("Detalle de sesión");
  });
  it("abre y cierra el menú adaptable", async () => {
    renderRole("admin", ["admin"]);
    const open = screen.getByRole("button", { name: "Abrir menú" });
    expect(open).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(open);
    expect(screen.getByRole("button", { name: "Cerrar menú" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "Estudiantes" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cerrar panel de navegación" })).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "Abrir menú" })).toHaveFocus();
    expect(screen.queryByRole("button", { name: "Cerrar panel de navegación" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Abrir menú" }));
    await userEvent.click(screen.getByRole("button", { name: "Cerrar panel de navegación" }));
    expect(screen.getByRole("button", { name: "Abrir menú" })).toHaveAttribute("aria-expanded", "false");
  });
  it("mantiene el foco dentro del menú móvil y lo lleva al contenido tras navegar", async () => {
    render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "token", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
      <MemoryRouter initialEntries={["/dashboard"]}><Routes>
        <Route element={<AppLayout />}><Route path="dashboard" element={<p>Inicio</p>} /><Route path="activities" element={<p>Listado de actividades</p>} /></Route>
      </Routes></MemoryRouter>
    </AuthContext.Provider>);
    await userEvent.click(screen.getByRole("button", { name: "Abrir menú" }));
    const brand = screen.getByRole("link", { name: "EMOtv" });
    brand.focus();
    await userEvent.tab({ shift: true });
    expect(screen.getByRole("link", { name: "Mis sesiones" })).toHaveFocus();
    await userEvent.click(screen.getByRole("link", { name: "Actividades" }));
    expect(screen.getByRole("main")).toHaveFocus();
    expect(screen.getByText("Listado de actividades")).toBeInTheDocument();
  });
  it("muestra el estado del servicio solo después de un fallo y lo retira al recuperarse", () => {
    renderRole("student", ["student"]);
    expect(screen.queryByText("Servicio no disponible")).not.toBeInTheDocument();
    act(() => window.dispatchEvent(new Event(API_UNAVAILABLE_EVENT)));
    expect(screen.getByRole("link", { name: "Servicio no disponible" })).toHaveAttribute("href", "/connection-error");
    act(() => window.dispatchEvent(new Event(API_RECOVERED_EVENT)));
    expect(screen.queryByText("Servicio no disponible")).not.toBeInTheDocument();
  });
  it("abre el menú de usuario, muestra identidad y permite cerrar sesión", async () => {
    const logout = vi.fn();
    render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "psychologist", is_active: true }, token: "token", loading: false, notice: "", login: vi.fn(), logout }}>
      <MemoryRouter initialEntries={["/dashboard"]}><Routes><Route element={<AppLayout />}><Route path="dashboard" element={<p>Inicio</p>} /></Route></Routes></MemoryRouter>
    </AuthContext.Provider>);
    const trigger = screen.getByRole("button", { name: "Menú de usuario" });
    await userEvent.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Sesión iniciada como")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cerrar sesión" })).toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(trigger).toHaveFocus();
    await userEvent.click(trigger);
    await userEvent.click(screen.getByRole("button", { name: "Cerrar sesión" }));
    expect(logout).toHaveBeenCalledOnce();
    expect(screen.queryByRole("button", { name: "Cerrar sesión" })).not.toBeInTheDocument();
  });
  it("cierra el menú de usuario al pulsar fuera", async () => {
    renderRole("admin", ["admin"]);
    const trigger = screen.getByRole("button", { name: "Menú de usuario" });
    await userEvent.click(trigger);
    await userEvent.click(screen.getByRole("main"));
    expect(trigger).toHaveAttribute("aria-expanded", "false");
  });
  it("mantiene el layout compartido también en una ruta desconocida", () => {
    render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "token", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
      <MemoryRouter initialEntries={["/ruta-inexistente"]}><App /></MemoryRouter>
    </AuthContext.Provider>);
    expect(screen.getByRole("navigation", { name: "Navegación principal" })).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Ruta de navegación" })).not.toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Página no encontrada" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Volver al inicio" })).toHaveAttribute("href", "/dashboard");
    expect(screen.getByText("u@example.com")).toBeInTheDocument();
  });
  it("explica el acceso restringido sin detalles técnicos", async () => {
    render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "token", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
      <MemoryRouter initialEntries={["/users"]}><App /></MemoryRouter>
    </AuthContext.Provider>);
    expect(await screen.findByRole("heading", { name: "No tienes acceso a esta página" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Volver al inicio" })).toHaveAttribute("href", "/dashboard");
  });
  it("omite breadcrumbs en páginas principales y listados", () => {
    render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "token", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
      <MemoryRouter initialEntries={["/sessions"]}><Routes>
        <Route element={<AppLayout />}><Route path="sessions" element={<p>Listado de sesiones</p>} /></Route>
      </Routes></MemoryRouter>
    </AuthContext.Provider>);
    expect(screen.getByText("Listado de sesiones")).toBeInTheDocument();
    expect(screen.queryByRole("navigation", { name: "Ruta de navegación" })).not.toBeInTheDocument();
  });
});
