import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import type { ReactElement } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../src/api/http";
import { AuthContext } from "../src/auth/AuthContext";
import { ActivitiesPage } from "../src/pages/ActivitiesPage";
import { DashboardPage } from "../src/pages/DashboardPage";
import { SessionsPage } from "../src/pages/SessionsPage";

vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn() }));

const policy = { id: "EMOTV-CONSENT-DEMO-003:v0.3", version: "v0.3", mode: "demo", url: null, available: true };
const activity = { id: "full_body_flow", name: "Movilidad suave", description: "Tres posturas encadenadas", required_posture: "arms_open",
  duration_seconds: 4, repetitions: 2, steps: [
    { posture: "arms_open", instruction: "Abre los brazos a la altura de los hombros", duration_seconds: 4 },
    { posture: "arms_up", instruction: "Eleva los brazos por encima de la cabeza", duration_seconds: 5 },
  ] };
const recognized = { id: "s2", state: "completed", student_id: "student-1", started_at: "2026-10-08T15:00:00Z", completed_at: "2026-10-08T15:05:00Z",
  initial_emotion: "sadness", emotion_confidence: .82, activity_id: "full_body_flow", exercise_result: "completed", exercise_duration_seconds: 18,
  emotion_model_id: "ferplus_onnx", emotion_model_version: "1" };
const withoutResult = { ...recognized, id: "s1", state: "cancelled", started_at: "2026-10-07T15:00:00Z", initial_emotion: null,
  emotion_confidence: null, activity_id: null, exercise_result: null, exercise_duration_seconds: null };

function api(responses: Record<string, unknown>) {
  vi.mocked(apiRequest).mockReset().mockImplementation(async (path) => {
    if (path in responses) return responses[path] as never;
    if (path.endsWith("/consents/active")) return (responses.active ?? null) as never;
    return [] as never;
  });
}

function show(element: ReactElement, path = "/") {
  const router = createMemoryRouter([{ path, element }, { path: "/sessions/:id", element: <p>Detalle de la sesión</p> }], { initialEntries: [path] });
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "prueba-07@example.com", role: "student", is_active: true }, token: "test", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}><RouterProvider router={router} /></AuthContext.Provider>);
}

const consented = { "/consent-policy": policy, "/students": [{ id: "student-1", user_id: "u", student_code: "PRUEBA-07" }],
  active: { id: "c1", policy_version: policy.id, granted_at: "2026-10-06T16:00:00Z" } };

beforeEach(() => vi.clearAllMocks());

describe("Inicio del estudiante", () => {
  it("invita a revisar el consentimiento si no está vigente y nunca saluda con el correo", async () => {
    api({ ...consented, active: null, "/sessions": [] });
    show(<DashboardPage />);
    expect(screen.getByRole("heading", { level: 1, name: "Hola" })).toBeInTheDocument();
    expect(screen.queryByText(/prueba-07/)).not.toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Revisar consentimiento" })).toHaveAttribute("href", "/consent");
    expect(screen.queryByRole("link", { name: "Empezar análisis" })).not.toBeInTheDocument();
  });

  it("sin sesiones explica los tres pasos del recorrido con «Empezar análisis»", async () => {
    api({ ...consented, "/sessions": [] });
    show(<DashboardPage />);
    expect(await screen.findByRole("link", { name: "Empezar análisis" })).toHaveAttribute("href", "/analysis");
    const steps = within(screen.getByRole("list"));
    expect(steps.getAllByRole("listitem").map((item) => item.querySelector("strong")?.textContent)).toEqual([
      "Encuadra tu rostro.", "Registra la expresión.", "Practica la actividad."]);
  });

  it("con sesiones muestra la última y «Nuevo análisis», sin tarjetas que repitan el menú", async () => {
    api({ ...consented, "/sessions": [withoutResult, recognized] });
    show(<DashboardPage />);
    const card = (await screen.findByRole("heading", { name: "Tu última sesión" })).closest("section") as HTMLElement;
    expect(card).toHaveTextContent("Tristeza");
    expect(card).toHaveTextContent(/8 de octubre de 2026/);
    expect(within(card).getByText("Completada")).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Nuevo análisis" })).toHaveAttribute("href", "/analysis");
    expect(screen.queryByRole("link", { name: "Ver sesiones" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Abrir analizador" })).not.toBeInTheDocument();
  });
});

describe("Actividades", () => {
  it("abre los pasos en un modal con postura, instrucción y duración, y permite empezar", async () => {
    api({ "/activities": [activity] });
    show(<ActivitiesPage />, "/activities");
    const card = (await screen.findByRole("heading", { name: "Movilidad suave" })).closest("article") as HTMLElement;
    expect(card).toHaveTextContent("2 pasos · 2 repeticiones · unos 18 s");
    expect(screen.queryByText(/full_body_flow/)).not.toBeInTheDocument();
    await userEvent.click(within(card).getByRole("button", { name: "Ver pasos de Movilidad suave" }));
    const dialog = screen.getByRole("dialog", { name: "Movilidad suave" });
    expect(dialog).toHaveTextContent("Tres posturas encadenadas");
    const steps = within(dialog).getAllByRole("listitem");
    expect(steps).toHaveLength(2);
    expect(steps[0]).toHaveTextContent("Brazos abiertos");
    expect(steps[0]).toHaveTextContent("Abre los brazos a la altura de los hombros");
    expect(steps[1]).toHaveTextContent("Brazos arriba");
    expect(steps[1]).toHaveTextContent("5 s");
    expect(within(dialog).getByRole("link", { name: "Empezar actividad" })).toHaveAttribute("href", "/analysis?activity=full_body_flow");
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("explica el estado vacío", async () => {
    api({ "/activities": [] });
    show(<ActivitiesPage />, "/activities");
    expect(await screen.findByText(/Todavía no hay actividades disponibles/)).toBeInTheDocument();
  });
});

describe("Mis sesiones", () => {
  it("usa nombres de actividad, oculta las sesiones sin resultado y abre el detalle desde la fila", async () => {
    api({ "/sessions": [withoutResult, recognized], "/activities": [activity] });
    show(<SessionsPage />, "/sessions");
    const table = await screen.findByRole("table");
    expect(await within(table).findByText("Movilidad suave")).toBeInTheDocument();
    expect(screen.queryByText("full_body_flow")).not.toBeInTheDocument();
    expect(within(table).getAllByRole("row")).toHaveLength(2); // encabezado + 1 sesión
    expect(screen.getByText("1 sesión oculta")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("checkbox", { name: "Mostrar sesiones sin resultado" }));
    expect(within(table).getAllByRole("row")).toHaveLength(3);
    expect(within(table).getByText("Cancelada").closest(".status-chip")).toHaveClass("status-chip-neutral");
    await userEvent.click(within(table).getByText("Tristeza"));
    expect(await screen.findByText("Detalle de la sesión")).toBeInTheDocument();
  });

  it("muestra el estado vacío con «Nuevo análisis»", async () => {
    api({ "/sessions": [], "/activities": [] });
    show(<SessionsPage />, "/sessions");
    expect(await screen.findByRole("link", { name: "Nuevo análisis" })).toHaveAttribute("href", "/analysis");
  });
});
