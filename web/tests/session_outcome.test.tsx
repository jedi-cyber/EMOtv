import { render, screen, within } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";
import { AuthContext } from "../src/auth/AuthContext";
import { SessionDetailPage } from "../src/pages/SessionDetailPage";
import { SessionsPage } from "../src/pages/SessionsPage";

const base = {
  student_id: "student-1", started_at: "2026-10-08T10:00:00Z", completed_at: "2026-10-08T10:02:00Z",
  initial_emotion: "sadness", emotion_confidence: .8, exercise_duration_seconds: null,
  emotion_model_id: "ferplus_onnx", emotion_model_version: "1.0", recognized_at: "2026-10-08T10:01:00Z",
};
const sessions = [
  { ...base, id: "s-skipped", state: "completed", activity_id: null, exercise_result: "skipped" },
  { ...base, id: "s-cancelled", state: "completed", activity_id: "arms_up_5s", exercise_result: "cancelled" },
  { ...base, id: "s-done", state: "completed", activity_id: "arms_up_5s", exercise_result: "completed", exercise_duration_seconds: 5 },
  { ...base, id: "s-recognized", state: "recognized", completed_at: null, activity_id: null, exercise_result: null },
];

vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string) => ({
    data: path.startsWith("/sessions/") ? sessions.find((item) => path.endsWith(item.id)) : sessions,
    loading: false, error: "", reload: vi.fn(),
  }),
}));

function renderAt(path: string, element: React.ReactNode, route: string) {
  const router = createMemoryRouter([{ path: route, element }], { initialEntries: [path] });
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "s@example.com", role: "student", is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}><RouterProvider router={router} /></AuthContext.Provider>);
}

describe("resultado de la actividad", () => {
  it("la lista distingue completada, omitida y cancelada", () => {
    renderAt("/sessions", <SessionsPage />, "/sessions");
    const rows = screen.getAllByRole("row").slice(1);
    expect(within(rows[0]).getByText("Omitida")).toBeInTheDocument();
    expect(within(rows[1]).getByText("Cancelada")).toBeInTheDocument();
    expect(within(rows[2]).getAllByText("Completada")).toHaveLength(2);
    expect(within(rows[3]).getByText("Expresión registrada")).toBeInTheDocument();
    // Etiquetas en español en el historial, nunca la clave del modelo.
    expect(within(rows[0]).getByText("Tristeza")).toBeInTheDocument();
    expect(screen.queryByText("sadness")).not.toBeInTheDocument();
  });

  it("el detalle muestra la actividad omitida y cuándo se registró la expresión", () => {
    renderAt("/sessions/s-skipped", <SessionDetailPage />, "/sessions/:sessionId");
    expect(screen.getByText("Resultado de la actividad").nextElementSibling).toHaveTextContent("Omitida");
    expect(screen.getByText("Expresión registrada el").nextElementSibling).not.toHaveTextContent("—");
    expect(screen.getByText("Expresión registrada").nextElementSibling).toHaveTextContent("Tristeza");
  });
});
