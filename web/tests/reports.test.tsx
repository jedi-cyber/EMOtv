import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../src/api/http";
import type { SessionReport } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import type { UserRole } from "../src/auth/types";
import { ReportPrintPage } from "../src/pages/ReportPrintPage";
import { SessionReportPage } from "../src/pages/SessionReportPage";

const state = vi.hoisted(() => ({ report: null as unknown }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: () => ({ data: state.report, loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn() }));

const ESTIMATES = "Las expresiones de este reporte son estimaciones de apoyo de un modelo automático sobre el rostro visible. No son una evaluación ni indican lo que la persona sentía.";
const base: SessionReport = {
  id: "r1", version: 1, status: "draft", current: true, narrative: "", created_at: "2026-10-22T10:00:00Z", updated_at: "2026-10-22T10:00:00Z",
  approved_at: null, session: { id: "s1", started_at: "2026-10-22T09:00:00Z", session_type: "participante_adulto", emotion_model_id: "hsemotion_enet_b0_8_best_afew", emotion_model_version: "1" },
  participant_code: "P-ABC234", estimates_notice: ESTIMATES, abstract_notice: null,
  timeline: { session_id: "s1", started_at: "2026-10-22T09:00:00Z", duration_seconds: 10, lanes: { questionnaires: [], stimuli: [], captures: [], said: [], markers: [], heart_rate: [] } },
  metrics: { session_id: "s1", emotional: [], abstract: [], totals: { emotional_stimuli: 0, counted: 0, matched: 0, excluded_captures: 0, sentence: "Ningún estímulo emocional tuvo una captura de buena calidad para comparar." }, abstract_notice: null },
  authored_by_me: true, requires_review: true, can_edit: true, can_review: false, can_new_version: false, comments: [], history: [], versions: [],
};

function page(role: UserRole, report: SessionReport, element: React.ReactNode, path: string, pattern: string) {
  state.report = report;
  vi.mocked(apiRequest).mockImplementation(async (url) => (url === "/sessions/s1/report" ? report : { ...report, narrative: "Texto" }) as never);
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role, is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={[path]}><Routes><Route path={pattern} element={element} /></Routes></MemoryRouter>
  </AuthContext.Provider>);
}
const report = (role: UserRole, value: SessionReport) => page(role, value, <SessionReportPage />, "/sessions/s1/report", "/sessions/:sessionId/report");

beforeEach(() => vi.mocked(apiRequest).mockReset());

describe("reporte de sesión", () => {
  it("quien condujo la sesión redacta y envía a revisión; el aviso y el modelo siempre están", async () => {
    report("student", base);
    expect(await screen.findByText(ESTIMATES)).toBeInTheDocument();
    expect(screen.getByText("P-ABC234")).toBeInTheDocument();
    expect(screen.getByText(/HSEmotion/)).toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Texto"), "Observó con atención.");
    expect(screen.getByRole("button", { name: "Enviar a revisión" })).toBeDisabled();  // primero se guarda
    await userEvent.click(screen.getByRole("button", { name: "Guardar texto" }));
    expect(apiRequest).toHaveBeenCalledWith("/reports/r1", expect.objectContaining({ method: "PUT", body: JSON.stringify({ narrative: "Observó con atención." }) }));
  });

  it("el reporte de un docente se cierra sin revisión", async () => {
    report("psychologist", { ...base, narrative: "Texto", requires_review: false });
    expect(await screen.findByRole("button", { name: "Cerrar el reporte" })).toBeEnabled();
    expect(screen.getByText(/no requiere revisión/)).toBeInTheDocument();
  });

  it("el docente asignado comenta por secciones, aprueba o devuelve", async () => {
    report("psychologist", { ...base, status: "submitted", narrative: "Texto", authored_by_me: false, can_edit: false, can_review: true });
    await screen.findByRole("button", { name: "Aprobar" });
    expect(screen.queryByLabelText("Texto")).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Comentario sobre métricas por estímulo"), "Describe la captura marcada.");
    await userEvent.click(screen.getAllByRole("button", { name: "Comentar" })[1]);
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/reports/r1/comments", expect.objectContaining({
      body: JSON.stringify({ section: "metrics", text: "Describe la captura marcada." }) })));
    await userEvent.click(screen.getByRole("button", { name: "Devolver con observaciones" }));
    expect(apiRequest).toHaveBeenCalledWith("/reports/r1/return", expect.objectContaining({ method: "POST" }));
  });

  it("un reporte aprobado no se edita: se crea una versión nueva", async () => {
    report("student", { ...base, status: "approved", narrative: "Texto", approved_at: "2026-10-22T11:00:00Z", can_edit: false, can_new_version: true });
    await screen.findByRole("button", { name: "Crear versión nueva" });
    expect(screen.queryByLabelText("Texto")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Vista imprimible" })).toHaveAttribute("href", "/reports/r1/print");
  });

  it("la vista imprimible registra la impresión antes de imprimir y muestra solo el código", async () => {
    const print = vi.spyOn(window, "print").mockImplementation(() => undefined);
    page("psychologist", { ...base, status: "approved", narrative: "Texto", approved_at: "2026-10-22T11:00:00Z" }, <ReportPrintPage />, "/reports/r1/print", "/reports/:reportId/print");
    await userEvent.click(await screen.findByRole("button", { name: "Imprimir reporte" }));
    expect(apiRequest).toHaveBeenCalledWith("/reports/r1/print", expect.objectContaining({ method: "POST" }));
    await waitFor(() => expect(print).toHaveBeenCalled());
    expect(screen.getByText("P-ABC234")).toBeInTheDocument();
    expect(screen.getByText(ESTIMATES)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/nombre del participante|DNI/i);
    print.mockRestore();
  });
});
