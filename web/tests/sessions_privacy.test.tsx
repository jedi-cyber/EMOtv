import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../src/api/http";
import { AuthContext } from "../src/auth/AuthContext";
import { ProtectedRoute } from "../src/auth/ProtectedRoute";
import type { UserRole } from "../src/auth/types";
import { ProtocolsPage } from "../src/pages/ProtocolsPage";
import { SessionDetailPage } from "../src/pages/SessionDetailPage";
import { StimuliPage } from "../src/pages/StimuliPage";
import { SessionConfirmDialog } from "../src/sessions/SessionConfirmDialog";

const state = vi.hoisted(() => ({ data: {} as Record<string, unknown> }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === null ? null : state.data[path] ?? [], loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn() }));

const notice = { kind: "child_notice", version: "2026-10-provisional", provisional: true, required: false, accepted: false,
  content: "# Aviso\n\nLos datos de menores son **más sensibles**." };

function withUser(role: UserRole, element: React.ReactNode, path = "/") {
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role, is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={[path]}>{element}</MemoryRouter>
  </AuthContext.Provider>);
}

beforeEach(() => {
  state.data = {};
  vi.mocked(apiRequest).mockReset();
});

describe("una sola confirmación por sesión", () => {
  it("con una persona adulta pide la autorización firmada y empieza sin marcar", async () => {
    const onConfirm = vi.fn();
    withUser("student", <SessionConfirmDialog open audience="adulto" onCancel={vi.fn()} onConfirm={onConfirm} />);
    const dialog = screen.getByRole("dialog", { name: "Antes de empezar" });
    const box = within(dialog).getByRole("checkbox", { name: "Es una sesión mía o cuento con la autorización firmada de la persona adulta" });
    expect(box).not.toBeChecked();
    expect(within(dialog).getByRole("button", { name: "Empezar la sesión" })).toBeDisabled();
    await userEvent.click(box);
    await userEvent.click(within(dialog).getByRole("button", { name: "Empezar la sesión" }));
    expect(onConfirm).toHaveBeenCalledWith(undefined);
    expect(dialog.textContent).toMatch(/no guarda nombres, DNI ni fotos/);
  });

  it("con un niño pide al tutor y, la primera vez, el aviso sobre menores con su versión", async () => {
    state.data["/commitment/child-notice"] = notice;
    const onConfirm = vi.fn();
    withUser("student", <SessionConfirmDialog open audience="infantil" onCancel={vi.fn()} onConfirm={onConfirm} />);
    const dialog = screen.getByRole("dialog", { name: "Antes de empezar" });
    expect(within(dialog).getByText("más sensibles")).toBeInTheDocument();
    expect(within(dialog).queryByText(/autorización firmada de la persona adulta/)).not.toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "Su tutor autorizó por escrito, está presente y el niño aceptó participar" }));
    const start = within(dialog).getByRole("button", { name: "Empezar la sesión" });
    expect(start).toBeDisabled();  // falta leer el aviso
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "Leí el aviso sobre datos de menores" }));
    await userEvent.click(start);
    expect(onConfirm).toHaveBeenCalledWith("2026-10-provisional");
  });
});

describe("compromiso de confidencialidad", () => {
  it("se acepta una vez en una ventana que no se cierra sin aceptar", async () => {
    vi.mocked(apiRequest).mockImplementation(async (path) => (path === "/commitment"
      ? { kind: "commitment", version: "v1", provisional: true, content: "# Compromiso\n\nNo compartas datos.", required: true, accepted: false }
      : { kind: "commitment", version: "v1", provisional: true, content: "", required: false, accepted: true }) as never);
    withUser("psychologist", <Routes>
      <Route element={<ProtectedRoute />}><Route path="/" element={<p>Inicio</p>} /></Route>
    </Routes>);
    const dialog = await screen.findByRole("dialog", { name: "Compromiso de confidencialidad" });
    expect(screen.getByText("Inicio")).toBeInTheDocument();
    expect(within(dialog).queryByRole("button", { name: "Cerrar" })).not.toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    expect(screen.getByRole("dialog", { name: "Compromiso de confidencialidad" })).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("checkbox", { name: /Leí el compromiso/ }));
    await userEvent.click(within(dialog).getByRole("button", { name: "Aceptar el compromiso" }));
    expect(apiRequest).toHaveBeenCalledWith("/commitment/accept", expect.objectContaining({ body: JSON.stringify({ version: "v1" }) }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });
});

describe("protocolos", () => {
  it("es una receta guardada: primero pregunta el público y no pide aprobación", async () => {
    state.data["/protocols"] = [{ id: "p1", family_id: "p1", version: 1, name: "Paisajes", description: "", for_children: true,
      pre_questionnaire_id: null, post_questionnaire_id: null, steps: [], created_at: "2026-10-01T00:00:00Z", owned_by_me: true, used: false }];
    withUser("student", <ProtocolsPage />);
    expect(screen.getByText("Un protocolo es una receta guardada: qué aplicar en una sesión, para usarla cuando quieras.")).toBeInTheDocument();
    expect(screen.getByText("Para niños")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Usar en el Analizador" })).toHaveAttribute("href", "/analysis?protocol=p1");
    expect(screen.queryByRole("button", { name: /Aprobar/ })).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/aprobación del docente|Pendiente de aprobación/);

    await userEvent.click(screen.getByRole("button", { name: "Nuevo protocolo" }));
    const dialog = screen.getByRole("dialog", { name: "Nuevo protocolo" });
    expect(within(dialog).getByRole("group", { name: "¿Para adultos o para niños?" })).toBeInTheDocument();
    expect(within(dialog).queryByLabelText("Nombre")).not.toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Guardar protocolo" })).toBeDisabled();
    await userEvent.click(within(dialog).getByRole("radio", { name: /Para adultos/ }));
    expect(within(dialog).getByLabelText("Nombre")).toBeInTheDocument();
    expect(within(dialog).getAllByRole("button", { name: "Crear cuestionario" })).toHaveLength(2);
  });

  it("crea un cuestionario sin salir y lo elige como previo", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ id: "q-new", family_id: "q-new", version: 1, title: "Al llegar", instructions: "",
      questions: [], created_at: "2026-10-01T00:00:00Z", shared_with_group: false, owned_by_me: true, used: false } as never);
    state.data["/questionnaires"] = [{ id: "q-new", title: "Al llegar" }];
    withUser("student", <ProtocolsPage />);
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
    await userEvent.click(screen.getByRole("radio", { name: /Para niños/ }));
    await userEvent.click(screen.getAllByRole("button", { name: "Crear cuestionario" })[0]);
    const editor = screen.getByRole("dialog", { name: "Nuevo cuestionario" });
    await userEvent.type(within(editor).getByLabelText("Título"), "Al llegar");
    await userEvent.click(within(editor).getByRole("button", { name: "Agregar pregunta" }));
    await userEvent.type(within(editor).getByLabelText("Pregunta"), "¿Cómo te sientes?");
    await userEvent.click(within(editor).getByRole("button", { name: "Guardar cuestionario" }));
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "Nuevo cuestionario" })).not.toBeInTheDocument());
    expect(screen.getByLabelText("Cuestionario previo (opcional)")).toHaveValue("q-new");
  });

  it("sin imágenes «Para niños» aprobadas lo dice y el docente tiene el botón para resolverlo", async () => {
    state.data["/stimuli"] = [{ id: "s1", title: "Tormenta", kind: "emotional", intensity: "moderate", audience: "adults", approved: true, active: true, category: "Clima", min_age: 6 }];
    withUser("psychologist", <ProtocolsPage />);
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
    await userEvent.click(screen.getByRole("radio", { name: /Para niños/ }));
    expect(screen.getByText(/No hay imágenes «Para niños» aprobadas/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir a Estímulos" })).toHaveAttribute("href", "/stimuli");
  });

  it("el usuario sin imágenes va a Imágenes a subir las suyas", async () => {
    withUser("student", <ProtocolsPage />);
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo protocolo" })[0]);
    await userEvent.click(screen.getByRole("radio", { name: /Para adultos/ }));
    expect(screen.getByText(/Sube las tuyas en Imágenes/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir a Imágenes" })).toHaveAttribute("href", "/images");
  });
});

describe("eliminación por sesión", () => {
  const session = { id: "s1", code: "S-4F7K2Q", state: "completed", session_type: "adulto", started_at: "2026-10-01T10:00:00Z",
    completed_at: "2026-10-01T10:10:00Z", owner_user_id: "u", student_id: "st1", activity_id: null, initial_emotion: null,
    recognized_at: null, emotion_confidence: null, exercise_result: null, deletion_requested_at: null };

  it("quien condujo la sesión pide eliminarla y ve el código", async () => {
    state.data["/sessions/s1"] = session;
    vi.mocked(apiRequest).mockResolvedValue({ ...session, deletion_requested_at: "2026-10-02T10:00:00Z" } as never);
    withUser("student", <Routes><Route path="/sessions/:sessionId" element={<SessionDetailPage />} /></Routes>, "/sessions/s1");
    expect(screen.getByText("S-4F7K2Q")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Eliminar la sesión" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Pedir que se elimine" }));
    await userEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Pedir la eliminación" }));
    expect(apiRequest).toHaveBeenCalledWith("/sessions/s1/deletion-request", expect.objectContaining({ method: "POST" }));
  });

  it("el docente la elimina y llega al acta", async () => {
    state.data["/sessions/s1"] = { ...session, owner_user_id: "other", deletion_requested_at: "2026-10-02T10:00:00Z" };
    vi.mocked(apiRequest).mockResolvedValue({ id: "c1", session_code: "S-4F7K2Q", deleted_at: "2026-10-03T10:00:00Z", counts: {}, verified: true } as never);
    withUser("psychologist", <Routes>
      <Route path="/sessions/:sessionId" element={<SessionDetailPage />} />
      <Route path="/sessions/deletions/:certificateId" element={<p>Acta c1</p>} />
    </Routes>, "/sessions/s1");
    expect(screen.getByText(/Se pidió eliminar esta sesión/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Eliminar la sesión" }));
    await userEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Eliminar y generar el acta" }));
    expect(apiRequest).toHaveBeenCalledWith("/sessions/s1/delete", expect.objectContaining({ method: "POST" }));
    expect(await screen.findByText("Acta c1")).toBeInTheDocument();
  });
});

describe("estímulos", () => {
  it("exigen origen, licencia y declarar que no son fotos de personas evaluadas", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ title: "Forma" } as never);
    withUser("psychologist", <StimuliPage />, "/stimuli");
    await userEvent.click(screen.getByRole("button", { name: "Agregar estímulo" }));
    const submit = screen.getByRole("button", { name: "Agregar" });
    await userEvent.upload(screen.getByLabelText(/Imagen/), new File(["x"], "forma.png", { type: "image/png" }));
    await userEvent.type(screen.getByLabelText("Título"), "Forma");
    await userEvent.selectOptions(screen.getByLabelText("Tipo"), "abstract");
    await userEvent.type(screen.getByLabelText("Categoría"), "Manchas");
    await userEvent.type(screen.getByLabelText("Origen"), "Creación propia");
    await userEvent.type(screen.getByLabelText("Licencia"), "Uso docente");
    await userEvent.click(screen.getByRole("checkbox", { name: /no es una fotografía de una persona evaluada/ }));
    expect(submit).toBeDisabled();  // falta declarar que no es una lámina proyectiva
    await userEvent.click(screen.getByRole("checkbox", { name: /no es una lámina de una prueba proyectiva/ }));
    expect(submit).toBeEnabled();
    await userEvent.click(submit);
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/stimuli", expect.objectContaining({ method: "POST" })));
  });
});
