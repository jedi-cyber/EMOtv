import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Link } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AssistantWidget } from "../src/components/AssistantWidget";

const mocks = vi.hoisted(() => ({
  auth: { user: { id: "student-1" } as { id: string } | null, token: "token", loading: false },
  request: vi.fn(),
}));
vi.mock("../src/auth/useAuth", () => ({ useAuth: () => mocks.auth }));
vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: mocks.request }));

function Harness() {
  return <MemoryRouter><Link to="/activities">Actividades</Link><AssistantWidget /></MemoryRouter>;
}

describe("asistente global", () => {
  beforeEach(() => {
    mocks.auth.user = { id: "student-1" };
    mocks.request.mockReset();
  });
  it("conserva la conversación al navegar y minimizar", async () => {
    mocks.request.mockResolvedValue({ answer: "Abre Actividades para comenzar." });
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Abrir asistente EMOtv" }));
    await userEvent.type(screen.getByLabelText("Tu pregunta"), "¿Cómo comienzo?");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(await screen.findByText("Abre Actividades para comenzar.")).toBeVisible();
    expect(mocks.request).toHaveBeenCalledWith("/chat", expect.objectContaining({ token: "token", body: JSON.stringify({ question: "¿Cómo comienzo?" }) }));
    await userEvent.click(screen.getByRole("link", { name: "Actividades" }));
    expect(screen.getByText("Abre Actividades para comenzar.")).toBeVisible();
    await userEvent.click(screen.getByLabelText("Tu pregunta"));
    await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "Abrir asistente EMOtv" })).toHaveFocus();
    expect(screen.queryByRole("log")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Abrir asistente EMOtv" }));
    expect(screen.getByText("Abre Actividades para comenzar.")).toBeVisible();
  });
  it("retira el asistente al cerrar sesión y limpia la conversación", async () => {
    const view = render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Abrir asistente EMOtv" }));
    await userEvent.type(screen.getByLabelText("Tu pregunta"), "Borrador privado");
    mocks.auth.user = null;
    view.rerender(<Harness />);
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    mocks.auth.user = { id: "student-2" };
    view.rerender(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Abrir asistente EMOtv" }));
    expect(screen.getByLabelText("Tu pregunta")).toHaveValue("");
  });
});
