import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiRequest } from "../src/api/http";
import type { ExamDetail, ParticipantViewState } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { ExamPage } from "../src/pages/ExamPage";
import { StationPage } from "../src/pages/StationPage";
import { navigationByRole } from "../src/routes/navigation";

vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(), apiBlob: vi.fn(),
}));

const DEBRIEFING = "Gracias. Durante el examen, EMOtv estimó la expresión de tu rostro.";
const exam = (changes: Partial<ExamDetail> = {}): ExamDetail => ({
  id: "e1", join_code: "K7Q2MX", state: "open", created_at: "2026-10-27T10:00:00Z", consent_confirmed_at: null,
  started_at: null, closed_at: null, station_count: 2, waiting_consent: 2,
  stations: [
    { code: "S-AAAA11", joined_at: "2026-10-27T10:01:00Z", consent_confirmed: false, phase: "waiting", finished: false },
    { code: "S-BBBB22", joined_at: "2026-10-27T10:02:00Z", consent_confirmed: false, phase: "waiting", finished: false },
  ],
  ...changes,
});

function docente(detail: ExamDetail, after: Record<string, ExamDetail> = {}) {
  let current = detail;   // el servidor recuerda el último paso
  vi.mocked(apiRequest).mockImplementation(async (path, options) => {
    const action = options?.method === "POST" ? String(path).split("/").pop() ?? "" : "";
    current = after[action] ?? current;
    return current as never;
  });
  return render(<AuthContext.Provider value={{ user: { id: "d", email: "d@example.com", role: "psychologist", is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={["/exams/e1"]}><Routes><Route path="/exams/:examId" element={<ExamPage />} /></Routes></MemoryRouter>
  </AuthContext.Provider>);
}

function station(view: ParticipantViewState | null, join = { view_token: "tok", session_code: "S-AAAA11" }) {
  vi.mocked(apiRequest).mockImplementation(async (path) => {
    if (path === "/exam-stations") return join as never;
    if (path === "/participant-view/tok") {
      if (!view) throw new ApiError(404, "Not found");
      return view as never;
    }
    return { stopped: true } as never;
  });
  return render(<MemoryRouter><StationPage /></MemoryRouter>);
}

const view = (changes: Partial<ParticipantViewState> = {}): ParticipantViewState => ({
  phase: "waiting", message: "Espera la indicación de quien conduce el examen.", stimulus: null, remaining_seconds: null,
  capture_frames: false, frame_interval_ms: 500, abstract_notice: null, ...changes,
});

beforeEach(() => { vi.mocked(apiRequest).mockReset(); sessionStorage.clear(); });

describe("examen del docente", () => {
  it("el menú del docente tiene Exámenes y el del usuario no", () => {
    expect(navigationByRole.psychologist.some((item) => item.label === "Exámenes")).toBe(true);
    expect(navigationByRole.student.some((item) => item.label === "Exámenes")).toBe(false);
  });

  it("muestra el código y las estaciones por código, sin expresiones", async () => {
    docente(exam());
    expect(await screen.findByText("K7Q2MX", { selector: ".exam-code" })).toBeInTheDocument();
    expect(screen.getByText("S-AAAA11")).toBeInTheDocument();
    expect(screen.getAllByText("Espera el consentimiento")).toHaveLength(2);
    // Sin consentimientos no se puede iniciar.
    expect(screen.getByRole("button", { name: "Iniciar examen" })).toBeDisabled();
    expect(document.body.textContent?.toLowerCase()).not.toMatch(/felicidad|happiness|confianza/);
  });

  it("confirma los consentimientos de todos con un diálogo", async () => {
    const user = userEvent.setup();
    const confirmed = exam({ waiting_consent: 0, consent_confirmed_at: "2026-10-27T10:03:00Z",
      stations: exam().stations.map((item) => ({ ...item, consent_confirmed: true, phase: "calibration" })) });
    docente(exam(), { consents: confirmed });
    await user.click(await screen.findByRole("button", { name: "Recibí los consentimientos de todos" }));
    expect(screen.getByText(/las 2 estaciones que esperan \(S-AAAA11, S-BBBB22\)/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Sí, los recibí" }));
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/exams/e1/consents", expect.objectContaining({ method: "POST" })));
    expect(await screen.findAllByText("Calibrando")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Iniciar examen" })).toBeEnabled();
  });

  it("terminar pide confirmación", async () => {
    const user = userEvent.setup();
    const running = exam({ state: "in_progress", waiting_consent: 0,
      stations: exam().stations.map((item) => ({ ...item, consent_confirmed: true, phase: "exam" })) });
    docente(running, { finish: { ...running, state: "closed", closed_at: "2026-10-27T11:00:00Z" } });
    await user.click(await screen.findByRole("button", { name: "Terminar examen" }));
    expect(apiRequest).not.toHaveBeenCalledWith("/exams/e1/finish", expect.anything());
    await user.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Terminar examen" }));
    expect(await screen.findByText(/Examen terminado/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Iniciar examen" })).not.toBeInTheDocument();
  });
});

describe("estación del examen", () => {
  it("se une con el código y muestra el código de su sesión", async () => {
    const user = userEvent.setup();
    station(view());
    await user.type(screen.getByLabelText("Código del examen"), "k7q2mx");
    await user.click(screen.getByRole("button", { name: "Unirse" }));
    expect(apiRequest).toHaveBeenCalledWith("/exam-stations", expect.objectContaining({ body: JSON.stringify({ join_code: "K7Q2MX" }) }));
    expect(await screen.findByText("S-AAAA11")).toBeInTheDocument();
    expect(screen.getByText("Anótalo en tu consentimiento firmado.")).toBeInTheDocument();
    expect(await screen.findByText("Espera la indicación de quien conduce el examen.")).toBeInTheDocument();
    // Al recargar, la estación sigue en su sesión.
    expect(sessionStorage.getItem("emotv.exam-station")).toContain("tok");
  });

  it("al terminar muestra el debriefing del servidor", async () => {
    sessionStorage.setItem("emotv.exam-station", JSON.stringify({ view_token: "tok", session_code: "S-AAAA11" }));
    station(view({ phase: "finished", message: DEBRIEFING }));
    expect(await screen.findByText(DEBRIEFING)).toBeInTheDocument();
    expect(screen.getByText("S-AAAA11")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Salir" })).toBeInTheDocument();
  });

  it("parar pide confirmación", async () => {
    const user = userEvent.setup();
    sessionStorage.setItem("emotv.exam-station", JSON.stringify({ view_token: "tok", session_code: "S-AAAA11" }));
    station(view());
    await user.click(await screen.findByRole("button", { name: "Quiero parar" }));
    expect(apiRequest).not.toHaveBeenCalledWith("/participant-view/tok/stop", expect.anything());
    await user.click(screen.getByRole("button", { name: "Sí, parar" }));
    await waitFor(() => expect(apiRequest).toHaveBeenCalledWith("/participant-view/tok/stop", expect.objectContaining({ method: "POST" })));
  });

  it("un código inválido muestra el error del servidor", async () => {
    const user = userEvent.setup();
    vi.mocked(apiRequest).mockRejectedValue(new ApiError(404, "El código no corresponde a un examen abierto"));
    render(<MemoryRouter><StationPage /></MemoryRouter>);
    await user.type(screen.getByLabelText("Código del examen"), "ZZZZZZ");
    await user.click(screen.getByRole("button", { name: "Unirse" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("El código no corresponde a un examen abierto");
  });
});
