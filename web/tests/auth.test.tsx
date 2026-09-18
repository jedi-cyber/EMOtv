import { render, screen, waitFor, act } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, expect, it, vi } from "vitest";
import { AuthProvider } from "../src/auth/AuthContext";
import { useAuth } from "../src/auth/useAuth";
import { tokenStorage } from "../src/auth/tokenStorage";
import { AUTH_UNAUTHORIZED_EVENT } from "../src/api/http";
import { MemoryRouter } from "react-router-dom";
import { App } from "../src/App";

const user = { id: "u", email: "u@example.com", role: "student", is_active: true };
const token = (exp: number) => `test.${btoa(JSON.stringify({ exp }))}.signature`;
function Probe() {
  const auth = useAuth();
  return <><span>{auth.user?.email ?? "Anónimo"}</span><span>{auth.notice}</span><span>{auth.connectionError ? "Sin conexión" : "Conectado"}</span><button onClick={() => { void auth.login("u@example.com", "password-123"); }}>Ingresar</button><button onClick={() => auth.logout()}>Salir</button></>;
}
beforeEach(() => sessionStorage.clear());

it("integra login, consulta de identidad y cierre sin conservar el token", async () => {
  const jwt = token(Math.floor(Date.now() / 1000) + 600);
  const fetcher = vi.fn().mockImplementation(async (path: string) => new Response(JSON.stringify(path === "/auth/token" ? { access_token: jwt, token_type: "bearer" } : user)));
  vi.stubGlobal("fetch", fetcher);
  render(<AuthProvider><Probe /></AuthProvider>);
  await userEvent.click(screen.getByRole("button", { name: "Ingresar" }));
  expect(await screen.findByText(user.email)).toBeInTheDocument();
  expect(tokenStorage.get()).toBe(jwt);
  expect(fetcher).toHaveBeenCalledWith("/auth/me", expect.objectContaining({ headers: expect.objectContaining({ Authorization: `Bearer ${jwt}` }) }));
  await userEvent.click(screen.getByRole("button", { name: "Salir" }));
  expect(screen.getByText("Anónimo")).toBeInTheDocument(); expect(tokenStorage.get()).toBeNull();
});

it("no restaura una identidad si /auth/me llega después del cierre", async () => {
  tokenStorage.set(token(Math.floor(Date.now() / 1000) + 600));
  let resolve!: (response: Response) => void;
  const fetcher = vi.fn().mockReturnValue(new Promise((done) => { resolve = done; }));
  vi.stubGlobal("fetch", fetcher);
  render(<AuthProvider><Probe /></AuthProvider>);
  await waitFor(() => expect(fetcher).toHaveBeenCalled());
  await userEvent.click(screen.getByRole("button", { name: "Salir" }));
  await act(async () => { resolve(new Response(JSON.stringify(user))); });
  expect(screen.getByText("Anónimo")).toBeInTheDocument(); expect(tokenStorage.get()).toBeNull();
});

it("descarta un token ya vencido y responde a un 401", async () => {
  tokenStorage.set(token(Math.floor(Date.now() / 1000) - 60));
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(user))));
  render(<AuthProvider><Probe /></AuthProvider>);
  await waitFor(() => expect(tokenStorage.get()).toBeNull());
  expect(screen.getByText("Anónimo")).toBeInTheDocument();
  act(() => window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT)));
  expect(screen.getByText("Tu sesión venció. Ingresa nuevamente.")).toBeInTheDocument();
});

it("conserva el token si falla la verificación por conexión", async () => {
  const jwt = token(Math.floor(Date.now() / 1000) + 600);
  tokenStorage.set(jwt);
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
  render(<AuthProvider><Probe /></AuthProvider>);
  expect(await screen.findByText("Sin conexión")).toBeInTheDocument();
  expect(tokenStorage.get()).toBe(jwt);
  expect(screen.getByText("Anónimo")).toBeInTheDocument();
});

it("redirige al login con aviso cuando vence la sesión durante la navegación", async () => {
  tokenStorage.set(token(Math.floor(Date.now() / 1000) + 600));
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(user))));
  render(<MemoryRouter initialEntries={["/dashboard"]}><AuthProvider><App /></AuthProvider></MemoryRouter>);
  expect(await screen.findByRole("heading", { name: "Hola, u" })).toBeInTheDocument();
  act(() => window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT)));
  expect(await screen.findByRole("heading", { name: "Ingresa a EMOtv" })).toBeInTheDocument();
  expect(screen.getByRole("status")).toHaveTextContent("Tu sesión venció. Ingresa nuevamente.");
  expect(tokenStorage.get()).toBeNull();
});

it("muestra la pantalla de conexión si /auth/me no responde", async () => {
  const jwt = token(Math.floor(Date.now() / 1000) + 600);
  tokenStorage.set(jwt);
  vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));
  render(<MemoryRouter initialEntries={["/dashboard"]}><AuthProvider><App /></AuthProvider></MemoryRouter>);
  expect(await screen.findByRole("heading", { name: "No podemos comunicarnos con EMOtv" })).toBeInTheDocument();
  expect(screen.getByRole("button", { name: "Reintentar conexión" })).toBeInTheDocument();
  expect(tokenStorage.get()).toBe(jwt);
});
