import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../src/api/http";
import type { GuidedScreen, GuidedState } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { GuidedConductorPage } from "../src/pages/GuidedConductorPage";

// Bloque 8: quien conduce vincula Android con un código de un solo uso. La
// pantalla en Android solo muestra la actividad; la web informa dónde está abierta.

vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: () => ({ data: [], loading: false, error: "", reload: vi.fn() }),
}));
vi.mock("../src/api/http", async (original) => ({
  ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn(),
}));

const base: GuidedState = {
  session_id: "s1", session_code: "S-4F7K2Q", phase: "stimuli", audience: "infantil", has_protocol: true, stop_reason: null,
  step_index: 0, step_count: 2, remaining_seconds: 30, steps_log: [],
  steps: [0, 1].map((index) => ({ index, stimulus_id: null, title: "", kind: "", exposure_seconds: 30, capture_after_seconds: 0,
    record_verbal_response: false, shown_before_analyzer: false, step_kind: "drawing" as const, target_expression: null,
    hold_seconds: null, option_count: null })),
  calibration: { state: "none", progress: 0, notice: null }, capture_status: [], pre_questionnaire_id: null,
  post_questionnaire_id: null, abstract_notice: null, captures: [], markers: [], verbal_responses: [],
  waiting_for_conductor: false, attempt: 1, can_repeat: false, max_attempts: 3, uses_camera: false,
};

let current: GuidedState;
function withScreen(value: GuidedScreen) { current = { ...base, screen: value }; }

beforeEach(() => {
  vi.mocked(apiRequest).mockReset();
  vi.mocked(apiRequest).mockImplementation(async (path) => {
    if (path === "/guided-sessions/s1/android-code") {
      current = { ...current, screen: { ...current.screen!, pairing_expires_at: "2026-11-07T10:05:00Z" } };
      return { code: "K7MP2QXR", expires_at: "2026-11-07T10:05:00Z", expires_in: 300 } as never;
    }
    return (path === "/guided-sessions/s1" ? current : {}) as never;
  });
});

function page() {
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "u@example.com", role: "student", is_active: true }, token: "t", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <MemoryRouter initialEntries={["/guided/s1"]}><Routes><Route path="/guided/:sessionId" element={<GuidedConductorPage />} /></Routes></MemoryRouter>
  </AuthContext.Provider>);
}

describe("vincular Android desde la vista de quien conduce", () => {
  it("pide un código de un solo uso y lo muestra mientras no se canjee", async () => {
    withScreen({ device: "web", pairing_expires_at: null, can_pair_android: true });
    page();
    expect(await screen.findByText(/la pantalla abierta hasta ahora deja de valer/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Vincular Android" }));
    expect(apiRequest).toHaveBeenCalledWith("/guided-sessions/s1/android-code", expect.objectContaining({ method: "POST" }));
    expect(await screen.findByText("K7MP2QXR")).toBeInTheDocument();
    expect(screen.getByText(/Sirve una sola vez y vence en 5 minutos/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Pedir otro código" })).toBeInTheDocument();
  });

  it("con la pantalla en Android lo informa y ofrece volver a la web", async () => {
    withScreen({ device: "android", pairing_expires_at: null, can_pair_android: true });
    page();
    expect(await screen.findByText("La pantalla de la persona está abierta en Android.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Abrir la pantalla de la persona" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Volver a abrirla en la web" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Vincular otro dispositivo Android" })).toBeInTheDocument();
  });

  it("una sesión con cámara no ofrece Android", async () => {
    withScreen({ device: "web", pairing_expires_at: null, can_pair_android: false });
    page();
    expect(await screen.findByRole("heading", { name: "Pantalla de la persona" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Android/ })).not.toBeInTheDocument();
  });
});
