import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../src/api/http";
import type { Questionnaire } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import type { UserRole } from "../src/auth/types";
import { QuestionnairesPage } from "../src/pages/QuestionnairesPage";
import { AnswerList, QuestionnaireForm } from "../src/questionnaires/QuestionnaireForm";

const state = vi.hoisted(() => ({ questionnaires: [] as unknown[] }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({ data: path === "/questionnaires" ? state.questionnaires : [], loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn() }));

const questionnaire: Questionnaire = {
  id: "q1", family_id: "q1", version: 1, title: "Antes de empezar", instructions: "Responde con calma.",
  created_at: "2026-10-22T00:00:00Z", shared_with_group: false, owned_by_me: true, used: false,
  questions: [
    { id: "animo", kind: "faces", text: "¿Cómo te sientes?", required: true, options: [], scale_points: null, min_label: null, max_label: null },
    { id: "energia", kind: "scale", text: "¿Cuánta energía tienes?", required: false, options: [], scale_points: 4, min_label: "Poca", max_label: "Mucha" },
    { id: "apoyos", kind: "multiple_choice", text: "¿Qué te ayuda?", required: false, options: ["Música", "Caminar"], scale_points: null, min_label: null, max_label: null },
  ],
};
const NO_SCORES = /puntaje|puntuaci|total|suma|promedio|interpret|diagn/i;

function withUser(role: UserRole, element: React.ReactNode) {
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role, is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter>{element}</MemoryRouter>
  </AuthContext.Provider>);
}

beforeEach(() => {
  state.questionnaires = [];
  vi.mocked(apiRequest).mockReset();
});

describe("cuestionarios", () => {
  it("exige las preguntas obligatorias y envía las respuestas tal como se dieron", async () => {
    const submit = vi.fn();
    withUser("student", <QuestionnaireForm questionnaire={questionnaire} onSubmit={submit} />);
    // Cinco caritas dibujadas para EMOtv, todas con el mismo trazo.
    const faces = within(screen.getByRole("radiogroup", { name: "¿Cómo te sientes?" })).getAllByRole("radio");
    expect(faces.map((item) => item.getAttribute("aria-label"))).toEqual(["Figura 1 de 5", "Figura 2 de 5", "Figura 3 de 5", "Figura 4 de 5", "Figura 5 de 5"]);
    await userEvent.click(screen.getByRole("button", { name: "Guardar respuestas" }));
    expect(submit).not.toHaveBeenCalled();
    expect(screen.getByText(/Faltan preguntas obligatorias: «¿Cómo te sientes\?»/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("radio", { name: "Figura 3 de 5" }));
    await userEvent.click(screen.getByRole("radio", { name: "2 de 4" }));
    await userEvent.click(screen.getByRole("checkbox", { name: "Caminar" }));
    await userEvent.click(screen.getByRole("button", { name: "Guardar respuestas" }));
    expect(submit).toHaveBeenCalledWith({ animo: 3, energia: 2, apoyos: ["Caminar"] });
    expect(screen.getByRole("note")).toHaveTextContent("lo creó su autor. EMOtv no lo valida, no calcula puntajes ni interpreta las respuestas");
  });

  it("muestra las respuestas sin sumarlas ni interpretarlas", () => {
    withUser("psychologist", <AnswerList questionnaire={questionnaire} answers={{ animo: 2, energia: 4 }} />);
    expect(screen.getByText("Figura 2 de 5")).toBeInTheDocument();
    expect(screen.getByText("Posición 4 de 4 (Poca — Mucha)")).toBeInTheDocument();
    expect(screen.getByText("Sin respuesta")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(NO_SCORES);
  });

  it("arma un cuestionario con vista previa antes de guardarlo", async () => {
    vi.mocked(apiRequest).mockResolvedValue({ ...questionnaire, id: "nuevo" } as never);
    withUser("student", <QuestionnairesPage />);
    expect(document.body.textContent).not.toMatch(/estudiante|psicolog/i);
    expect(screen.getByText(/un protocolo aplica antes o después/)).toBeInTheDocument();
    // Sin cuestionarios, el estado vacío también ofrece el botón que lo resuelve.
    await userEvent.click(screen.getAllByRole("button", { name: "Nuevo cuestionario" })[0]);
    expect(screen.getByRole("dialog", { name: "Nuevo cuestionario" })).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Título"), "Al llegar");
    await userEvent.selectOptions(screen.getByLabelText("Tipo de pregunta"), "scale");
    await userEvent.click(screen.getByRole("button", { name: "Agregar pregunta" }));
    await userEvent.type(screen.getByLabelText("Pregunta"), "¿Cuánto dormiste?");
    await userEvent.selectOptions(screen.getByLabelText("Puntos de la escala"), "3");
    await userEvent.type(screen.getByLabelText(/Etiqueta del extremo inicial/), "Poco");
    await userEvent.type(screen.getByLabelText(/Etiqueta del extremo final/), "Mucho");
    await userEvent.click(screen.getByRole("checkbox", { name: "Obligatoria" }));
    await userEvent.click(screen.getByRole("button", { name: "Vista previa" }));
    const preview = screen.getByRole("dialog", { name: "Vista previa" });
    expect(within(preview).getAllByRole("radio")).toHaveLength(3);
    expect(within(preview).getByText("Poco")).toBeInTheDocument();
    // Escape cierra solo la vista previa; el editor sigue abierto debajo.
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Vista previa" })).not.toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Nuevo cuestionario" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Guardar cuestionario" }));
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/questionnaires", expect.objectContaining({ method: "POST" })));
    const body = JSON.parse(String(vi.mocked(apiRequest).mock.calls[0][1]?.body));
    expect(body.questions[0]).toMatchObject({ kind: "scale", text: "¿Cuánto dormiste?", required: true, scale_points: 3, min_label: "Poco", max_label: "Mucho" });
  });

  it("el docente comparte un cuestionario y el usuario copia la plantilla", async () => {
    state.questionnaires = [questionnaire];
    vi.mocked(apiRequest).mockResolvedValue({} as never);
    const view = withUser("psychologist", <QuestionnairesPage />);
    await userEvent.click(screen.getByRole("button", { name: "Compartir con mi grupo" }));
    expect(apiRequest).toHaveBeenCalledWith("/questionnaires/q1/share", expect.objectContaining({ method: "PUT", body: JSON.stringify({ shared: true }) }));
    view.unmount();
    state.questionnaires = [{ ...questionnaire, owned_by_me: false, shared_with_group: true }];
    withUser("student", <QuestionnairesPage />);
    expect(screen.getByText("Plantilla de tu docente")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Compartir con mi grupo" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Copiar y modificar" }));
    expect(apiRequest).toHaveBeenCalledWith("/questionnaires/q1/copy", expect.objectContaining({ method: "POST" }));
    await userEvent.click(screen.getByRole("button", { name: "Usar la plantilla inicial" }));
    expect(apiRequest).toHaveBeenCalledWith("/questionnaires/starter", expect.objectContaining({ method: "POST" }));
  });
});
