import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, MemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiRequest } from "../src/api/http";
import type { ParticipantGame } from "../src/api/types";
import { AuthContext } from "../src/auth/AuthContext";
import { MatchingGameStage } from "../src/game/MatchingGameStage";
import { AdaptiveAnalysisPage } from "../src/pages/AdaptiveAnalysisPage";
import { GamesPage } from "../src/pages/GamesPage";

// Juegos con cámara: desde Juegos se abre el Analizador con el juego elegido; al
// empezar, EMOtv arma el protocolo de la cuenta y la sesión sigue como con cualquiera.

const { protocols } = vi.hoisted(() => ({ protocols: { value: [] as unknown[] } }));
vi.mock("../src/api/useApiQuery", () => ({
  useApiQuery: (path: string | null) => ({
    data: path === null ? null : path === "/protocols" ? protocols.value
      : [{ model_id: "ferplus_onnx", state: "SUPPORTED", reasons: [], is_default: true }],
    loading: false, error: "", reload: vi.fn(),
  }),
}));
vi.mock("../src/api/http", async (original) => ({ ...await original<typeof import("../src/api/http")>(), apiRequest: vi.fn() }));

function analyzer(entry: string) {
  const router = createMemoryRouter([
    { path: "/analysis", element: <AdaptiveAnalysisPage /> },
    { path: "/guided/:id", element: <p>Conducción</p> },
  ], { initialEntries: [entry] });
  return render(<AuthContext.Provider value={{ user: { id: "u", email: "student@example.com", role: "student", is_active: true }, token: "test", loading: false, notice: "", login: vi.fn(), logout: vi.fn() }}>
    <RouterProvider router={router} /></AuthContext.Provider>);
}

beforeEach(() => {
  protocols.value = [];
  vi.mocked(apiRequest).mockReset().mockImplementation(async (path) => {
    if (path === "/consent-policy") return { id: "EMOTV-CONSENT-DEMO-001:v0.1", version: "v0.1", mode: "demo", available: true } as never;
    if (path === "/students") return [{ id: "student-1" }] as never;
    if (path.endsWith("/consents/active")) return { id: "consent-1", policy_version: "EMOTV-CONSENT-DEMO-001:v0.1" } as never;
    if (path.startsWith("/camera-games/")) return { id: "cg-1", name: "Juego con cámara: empareja la emoción", for_children: true } as never;
    if (path === "/sessions") return { id: "session-1", state: "in_progress", code: "S-4F7K2Q" } as never;
    if (path.startsWith("/guided-sessions/")) return { view_token: "tok" } as never;
    return {} as never;
  });
});
afterEach(cleanup);

describe("juegos con cámara", () => {
  it("la página de Juegos lleva al Analizador con el juego elegido", () => {
    render(<MemoryRouter><GamesPage /></MemoryRouter>);
    const links = screen.getAllByRole("link", { name: "Jugar con la cámara" });
    expect(links.map((item) => item.getAttribute("href"))).toEqual(["/analysis?game=matching", "/analysis?game=similar"]);
  });

  it("el Analizador ofrece los juegos con cámara y no repite sus protocolos", () => {
    protocols.value = [
      { id: "p1", name: "Paisajes", for_children: false, owned_by_me: true, steps: [{}], pre_questionnaire_id: null, post_questionnaire_id: null },
      { id: "cg-1", name: "Juego con cámara: empareja la emoción", for_children: false, owned_by_me: true, steps: [{}],
        pre_questionnaire_id: null, post_questionnaire_id: null, camera_game: "matching" },
    ];
    analyzer("/analysis?game=matching");
    const select = screen.getByLabelText("Protocolo");
    expect(select).toHaveValue("game:matching");
    const games = within(select).getByRole("group", { name: "Juegos con cámara" });
    expect(within(games).getAllByRole("option").map((item) => item.textContent))
      .toEqual(["Empareja la emoción · responde con la cara", "Busca la misma emoción · responde con la cara"]);
    expect(within(select).queryByRole("option", { name: /Juego con cámara: empareja/ })).not.toBeInTheDocument();
    // Pregunta con quién es la sesión y no pide probar la cámara aquí.
    expect(screen.getByRole("group", { name: "¿Con quién es la sesión?" })).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Requisitos para empezar" })).queryByText("Cámara")).not.toBeInTheDocument();
    expect(screen.getByText(/la cámara marca el nombre que coincide/)).toBeInTheDocument();
  });

  it("al empezar arma el protocolo del juego para ese público y sigue como con un protocolo", async () => {
    analyzer("/analysis?game=matching");
    await userEvent.click(screen.getByRole("radio", { name: /Un adulto/ }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Empezar la sesión" })).toBeEnabled());
    await userEvent.click(screen.getByRole("button", { name: "Empezar la sesión" }));
    const dialog = await screen.findByRole("dialog", { name: "Antes de empezar" });
    await userEvent.click(within(dialog).getByRole("checkbox"));
    await userEvent.click(within(dialog).getByRole("button", { name: "Empezar la sesión" }));
    await screen.findByText("Conducción");
    const calls = vi.mocked(apiRequest).mock.calls;
    const built = calls.find(([path]) => path === "/camera-games/matching/protocol");
    expect(JSON.parse(String(built?.[1]?.body))).toEqual({ for_children: false });
    const created = calls.find(([path]) => path === "/sessions");
    expect(JSON.parse(String(created?.[1]?.body))).toMatchObject({ protocol_id: "cg-1", session_type: "adulto", authorization_confirmed: true });
  });

  it("en pantallas anchas el juego pone la cara a un lado y las opciones al otro", () => {
    const game: ParticipantGame = {
      round: "0-1-0", number: 1, total: 3, game_type: "matching", question: "¿Qué emoción muestra esta cara?",
      state: "playing", answer: null, explanation: null, can_help: false, last_round: false, asks_face: false, message: null,
      options: [{ key: "sadness", label: "Tristeza", available: true }, { key: "happiness", label: "Alegría", available: true }],
    };
    const { container } = render(<MatchingGameStage game={game} imageUrl="/cara.png" onAction={vi.fn(async () => undefined)} />);
    const stage = container.querySelector(".matching-game");
    expect(stage).toHaveClass("has-image");
    expect(stage?.querySelector(".matching-game-figure")).toBeInTheDocument();
    expect(stage?.querySelector(".matching-game-body .recognition-options")).toBeInTheDocument();
  });
});

describe("buscar la misma emoción en pantallas anchas", () => {
  it("deja la cara modelo arriba, como dice la consigna", () => {
    const game: ParticipantGame = {
      round: "0-1-0", number: 1, total: 3, game_type: "similar", question: "¿Qué cara muestra la misma emoción que la de arriba?",
      state: "playing", answer: null, explanation: null, can_help: false, last_round: false, asks_face: false, message: null,
      options: [{ key: "a", label: "Cara 1", available: true }, { key: "b", label: "Cara 2", available: true }],
    };
    const { container } = render(<MatchingGameStage game={game} imageUrl="/cara.png" onAction={vi.fn(async () => undefined)} />);
    expect(container.querySelector(".matching-game")).not.toHaveClass("has-image");
  });
});
