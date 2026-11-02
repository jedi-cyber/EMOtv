import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuthContext } from "../src/auth/AuthContext";
import { ApiError, apiRequest } from "../src/api/http";
import { LoginPage } from "../src/pages/LoginPage";

vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn() }));

const login = vi.fn();
const completeMfa = vi.fn();

function renderLogin() {
  return render(<AuthContext.Provider value={{ user: null, token: null, loading: false, notice: "", login, completeMfa,
    changePassword: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={["/login"]}><Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/dashboard" element={<p>Panel</p>} />
    </Routes></MemoryRouter>
  </AuthContext.Provider>);
}

async function passwordStep() {
  await userEvent.type(screen.getByLabelText("Correo institucional"), "admin@ejemplo.local");
  await userEvent.type(screen.getByLabelText("Contraseña"), "valor-de-prueba-largo");
  await userEvent.click(screen.getByRole("button", { name: "Ingresar" }));
}

beforeEach(() => {
  login.mockReset();
  completeMfa.mockReset().mockResolvedValue(undefined);
  vi.mocked(apiRequest).mockReset();
});

describe("ingreso de las cuentas de gestión", () => {
  it("la primera vez muestra la clave una sola vez y entra con el código", async () => {
    login.mockResolvedValue({ step: "setup", mfaToken: "paso" });
    vi.mocked(apiRequest).mockResolvedValue({ secret: "ABCDEFGHIJKLMNOP", otpauth_uri: "otpauth://totp/EMOtv" } as never);
    renderLogin();
    await passwordStep();
    expect(await screen.findByText("ABCD EFGH IJKL MNOP")).toBeInTheDocument();
    expect(apiRequest).toHaveBeenCalledTimes(1);
    expect(apiRequest).toHaveBeenCalledWith("/auth/mfa/setup", expect.objectContaining({ body: JSON.stringify({ mfa_token: "paso" }) }));
    expect(screen.getByRole("link", { name: "Abrir en la aplicación autenticadora" })).toHaveAttribute("href", "otpauth://totp/EMOtv");
    const enter = screen.getByRole("button", { name: "Confirmar y entrar" });
    expect(enter).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Código de tu aplicación autenticadora"), "123456");
    await userEvent.click(enter);
    expect(completeMfa).toHaveBeenCalledWith("paso", "123456");
    expect(await screen.findByText("Panel")).toBeInTheDocument();
  });

  it("después solo pide el código y muestra el error si no corresponde", async () => {
    login.mockResolvedValue({ step: "verify", mfaToken: "paso" });
    completeMfa.mockRejectedValueOnce(new ApiError(401, "Código incorrecto o ya usado."));
    renderLogin();
    await passwordStep();
    expect(await screen.findByRole("heading", { name: "Código de verificación" })).toBeInTheDocument();
    expect(apiRequest).not.toHaveBeenCalled();
    await userEvent.type(screen.getByLabelText("Código de tu aplicación autenticadora"), "000000");
    await userEvent.click(screen.getByRole("button", { name: "Entrar" }));
    expect(await screen.findByText("Código incorrecto o ya usado.")).toBeInTheDocument();
    expect(screen.getByLabelText("Código de tu aplicación autenticadora")).toHaveValue("");
  });

  it("las demás cuentas entran solo con la contraseña", async () => {
    login.mockResolvedValue(null);
    renderLogin();
    await passwordStep();
    expect(await screen.findByText("Panel")).toBeInTheDocument();
    expect(completeMfa).not.toHaveBeenCalled();
  });
});
