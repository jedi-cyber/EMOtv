import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Link } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AssistantWidget } from "../src/components/AssistantWidget";
import { ApiError } from "../src/api/http";

const mocks = vi.hoisted(() => ({
  auth: { user: { id: "student-1", role: "student" } as { id: string; role: string } | null, token: "token", loading: false },
  request: vi.fn(),
}));
vi.mock("../src/auth/useAuth", () => ({ useAuth: () => mocks.auth }));
vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: mocks.request }));

function Harness({ path = "/dashboard" }: { path?: string }) {
  return <MemoryRouter initialEntries={[path]}><Link to="/activities">Actividades</Link><AssistantWidget /></MemoryRouter>;
}

type Handler = (path: string, init?: { body?: string }) => unknown;
function serve(handler: Handler) {
  mocks.request.mockImplementation(async (path: string, init?: { body?: string }) => handler(path, init));
}
const empty = { conversation_id: null, messages: [] };

describe("Emi", () => {
  beforeEach(() => {
    mocks.auth.user = { id: "student-1", role: "student" };
    mocks.request.mockReset();
  });

  it("se llama Emi, conserva la conversación al navegar y minimizar", async () => {
    serve((path) => path === "/chat" ? { conversation_id: "c-1", answer: "Abre Actividades para comenzar.", in_scope: true } : empty);
    render(<Harness />);
    expect(screen.getByRole("button", { name: "Abrir a Emi" })).toHaveTextContent("Emi");
    await userEvent.click(screen.getByRole("button", { name: "Abrir a Emi" }));
    expect(screen.getByRole("heading", { name: "Emi" })).toBeVisible();
    expect(screen.getByText(/no diagnostica a nadie ni reemplaza a tu docente/)).toBeVisible();
    await userEvent.type(screen.getByLabelText("Tu pregunta"), "¿Cómo comienzo?");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(await screen.findByText("Abre Actividades para comenzar.")).toBeVisible();
    expect(mocks.request).toHaveBeenCalledWith("/chat", expect.objectContaining({ token: "token", body: JSON.stringify({ question: "¿Cómo comienzo?" }) }));
    await userEvent.click(screen.getByRole("link", { name: "Actividades" }));
    expect(screen.getByText("Abre Actividades para comenzar.")).toBeVisible();
    await userEvent.click(screen.getByLabelText("Tu pregunta"));
    await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("button", { name: "Abrir a Emi" })).toHaveFocus();
    expect(screen.queryByRole("log")).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Abrir a Emi" }));
    expect(screen.getByText("Abre Actividades para comenzar.")).toBeVisible();
    // La siguiente pregunta continúa la misma conversación.
    await userEvent.type(screen.getByLabelText("Tu pregunta"), "¿Y después?");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    await waitFor(() => expect(mocks.request).toHaveBeenLastCalledWith("/chat", expect.objectContaining({
      body: JSON.stringify({ conversation_id: "c-1", question: "¿Y después?" }) })));
  });

  it("carga el historial al abrir y empieza una conversación nueva", async () => {
    serve((path) => {
      if (path === "/chat/conversations/current") return { conversation_id: "c-7", messages: [
        { role: "user", content: "¿Qué es una postura?", created_at: "2026-10-09T10:00:00Z" },
        { role: "assistant", content: "Es una posición del cuerpo.", created_at: "2026-10-09T10:00:05Z" }] };
      if (path === "/chat/conversations") return { conversation_id: "c-8", messages: [] };
      return { conversation_id: "c-8", answer: "Respuesta nueva", in_scope: true };
    });
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Abrir a Emi" }));
    expect(await screen.findByText("Es una posición del cuerpo.")).toBeVisible();
    expect(screen.getAllByText("Emi", { selector: "strong" })).toHaveLength(1);
    await userEvent.click(screen.getByRole("button", { name: "Nueva conversación" }));
    await waitFor(() => expect(screen.queryByText("Es una posición del cuerpo.")).not.toBeInTheDocument());
    expect(mocks.request).toHaveBeenCalledWith("/chat/conversations", expect.objectContaining({ method: "POST" }));
    await userEvent.type(screen.getByLabelText("Tu pregunta"), "Hola");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(mocks.request).toHaveBeenLastCalledWith("/chat", expect.objectContaining({ body: JSON.stringify({ conversation_id: "c-8", question: "Hola" }) }));
  });

  it("muestra que Emi está escribiendo mientras espera la respuesta", async () => {
    let answer: (value: unknown) => void = () => undefined;
    serve((path) => path === "/chat" ? new Promise((resolve) => { answer = resolve; }) : empty);
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Abrir a Emi" }));
    await userEvent.type(screen.getByLabelText("Tu pregunta"), "¿Qué es la sorpresa?");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(screen.getByText(/Emi está escribiendo/)).toBeVisible();
    answer({ conversation_id: "c-1", answer: "Es una expresión breve.", in_scope: true });
    expect(await screen.findByText("Es una expresión breve.")).toBeVisible();
    expect(screen.queryByText(/Emi está escribiendo/)).not.toBeInTheDocument();
  });

  it.each([
    [429, "Enviaste muchos mensajes seguidos a Emi. Espera unos minutos."],
    [503, "Emi no está disponible: el servidor no tiene configurada la conexión con el asistente."],
  ])("ante %i muestra el mensaje del servidor y conserva la pregunta", async (status, detail) => {
    serve((path) => { if (path === "/chat") throw new ApiError(status, detail); return empty; });
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Abrir a Emi" }));
    await userEvent.type(screen.getByLabelText("Tu pregunta"), "Pregunta pendiente");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(await screen.findByText(detail)).toBeVisible();
    expect(screen.getByLabelText("Tu pregunta")).toHaveValue("Pregunta pendiente");
  });

  it("retira a Emi al cerrar sesión y limpia la conversación", async () => {
    serve(() => empty);
    const view = render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Abrir a Emi" }));
    await userEvent.type(screen.getByLabelText("Tu pregunta"), "Borrador privado");
    mocks.auth.user = null;
    view.rerender(<Harness />);
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    mocks.auth.user = { id: "student-2", role: "student" };
    view.rerender(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Abrir a Emi" }));
    expect(screen.getByLabelText("Tu pregunta")).toHaveValue("");
  });

  it("es para usuarios y docentes; no aparece para la administración", () => {
    serve(() => empty);
    mocks.auth.user = { id: "docente-1", role: "psychologist" };
    const view = render(<Harness />);
    expect(screen.getByRole("button", { name: "Abrir a Emi" })).toBeInTheDocument();
    for (const role of ["admin", "superadmin"]) {
      mocks.auth.user = { id: `${role}-1`, role };
      view.rerender(<Harness />);
      expect(screen.queryByRole("button", { name: "Abrir a Emi" })).not.toBeInTheDocument();
    }
  });

  it.each([
    ["la vista del participante", "/participant-view/token-de-prueba"],
    ["la sesión guiada con un participante", "/guided/s-1"],
  ])("no carga a Emi en %s", (_, path) => {
    serve(() => empty);
    render(<Harness path={path} />);
    expect(screen.queryByRole("button", { name: "Abrir a Emi" })).not.toBeInTheDocument();
    expect(screen.queryByRole("complementary")).not.toBeInTheDocument();
    expect(mocks.request).not.toHaveBeenCalled();
  });

  it("muestra siempre el aviso de no escribir datos de niños o familias", async () => {
    serve((path) => path === "/chat" ? { conversation_id: null, answer: "Tu mensaje no se envió.", in_scope: false } : empty);
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Abrir a Emi" }));
    const notice = /No escribas nombres ni datos de niños o familias/;
    expect(screen.getByText(notice)).toBeVisible();
    await userEvent.type(screen.getByLabelText("Tu pregunta"), "Pregunta");
    await userEvent.click(screen.getByRole("button", { name: "Enviar" }));
    expect(await screen.findByText("Tu mensaje no se envió.")).toBeVisible();
    expect(screen.getByText(notice)).toBeVisible();
  });

  it("borra la propia conversación después de confirmar", async () => {
    serve((path) => path === "/chat/conversations/current"
      ? { conversation_id: "c-9", messages: [{ role: "user", content: "Mi pregunta", created_at: "2026-10-23T10:00:00Z" }] }
      : null);
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Abrir a Emi" }));
    expect(await screen.findByText("Mi pregunta")).toBeVisible();
    await userEvent.click(screen.getByRole("button", { name: "Borrar conversación" }));
    await userEvent.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.getByText("Mi pregunta")).toBeVisible();
    expect(mocks.request).not.toHaveBeenCalledWith("/chat/conversations/c-9", expect.anything());
    await userEvent.click(screen.getByRole("button", { name: "Borrar conversación" }));
    await userEvent.click(screen.getByRole("button", { name: "Sí, borrar" }));
    expect(await screen.findByText("Conversación borrada.")).toBeVisible();
    expect(mocks.request).toHaveBeenCalledWith("/chat/conversations/c-9", expect.objectContaining({ method: "DELETE", token: "token" }));
    expect(screen.queryByText("Mi pregunta")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Borrar conversación" })).toBeDisabled();
  });
});
