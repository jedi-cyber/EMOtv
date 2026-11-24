import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { answerTrial, helpTrial, newTrialGame, nextTrial, trialView } from "../src/game/trialGame";
import { navigationByRole } from "../src/routes/navigation";
import { paths } from "../src/routes/paths";
import { GamesPage } from "../src/pages/GamesPage";
import { TrialGamePage } from "../src/pages/TrialGamePage";

const fixed = () => 0.3;

describe("juegos de prueba", () => {
  it("el menú de usuarios y docentes tiene «Juegos»; la administración no", () => {
    for (const role of ["student", "psychologist"] as const) {
      expect(navigationByRole[role].some((item) => item.to === paths.games && item.label === "Juegos")).toBe(true);
    }
    expect(navigationByRole.admin.some((item) => item.to === paths.games)).toBe(false);
  });

  it("tres rondas de las cinco expresiones, sin repetir la emoción de la ronda anterior", () => {
    const game = newTrialGame("matching");
    expect(game.rounds).toHaveLength(3);
    game.rounds.forEach((round, index) => {
      expect(["happiness", "surprise", "sadness", "anger", "neutral"]).toContain(round.target);
      expect(round.options.map((option) => option.expression)).toContain(round.target);
      if (index > 0) expect(round.target).not.toBe(game.rounds[index - 1].target);
    });
  });

  it("tras dos opciones distintas muestra la respuesta; sin puntaje", () => {
    let game = newTrialGame("matching", fixed);
    const round = game.rounds[0];
    const wrong = round.options.filter((option) => option.expression !== round.target);
    game = answerTrial(game, wrong[0].key);
    expect(game.state).toBe("retry");
    expect(trialView(game).message).toBe("Mira otra vez la cara. Puedes pedir ayuda.");
    game = answerTrial(game, wrong[1].key);
    const shown = trialView(game);
    expect(game.state).toBe("shown");
    expect(shown.answer).toBe(round.target);
    expect(JSON.stringify(shown)).not.toMatch(/punt|score/i);
  });

  it("la ayuda quita una opción que no es la respuesta, una sola vez", () => {
    const game = helpTrial(newTrialGame("similar", fixed), fixed);
    const round = game.rounds[0];
    const correct = round.options.find((option) => option.expression === round.target)!.key;
    expect(game.removed).not.toBeNull();
    expect(game.removed).not.toBe(correct);
    expect(trialView(game).can_help).toBe(false);
    expect(trialView(game).options.find((option) => option.key === game.removed)?.available).toBe(false);
  });

  it("al buscar la misma emoción, la pareja es otra cara y las opciones no dicen su emoción", () => {
    const game = newTrialGame("similar", fixed);
    const round = game.rounds[0];
    const pair = round.options.find((option) => option.expression === round.target)!;
    expect(pair.face).not.toBe(round.face);
    expect(trialView(game).options.map((option) => option.label)).toEqual(["Cara 1", "Cara 2", "Cara 3", "Cara 4"]);
  });

  it("termina tras la última ronda", () => {
    let game = newTrialGame("matching", fixed);
    for (let index = 0; index < 3; index += 1) {
      const round = game.rounds[game.index];
      game = nextTrial(answerTrial(game, round.target));
    }
    expect(game.state).toBe("finished");
  });

  it("la página de juegos lleva al dibujo y a las pruebas", () => {
    render(<MemoryRouter><GamesPage /></MemoryRouter>);
    expect(screen.getByRole("link", { name: "Actividad de dibujo" })).toHaveAttribute("href", paths.drawing);
    expect(screen.getAllByRole("link", { name: "Jugar la prueba" }).map((link) => link.getAttribute("href")))
      .toEqual([paths.game("matching"), paths.game("similar")]);
    expect(screen.getByText(/No crea una sesión, no usa la cámara y no guarda el dibujo/)).toBeInTheDocument();
  });

  it("se juega una ronda en la pantalla, sin llamar al servidor", async () => {
    render(<MemoryRouter initialEntries={[paths.game("matching")]}>
      <Routes><Route path={paths.gamePattern} element={<TrialGamePage />} /></Routes>
    </MemoryRouter>);
    expect(screen.getByText(/Versión de prueba/)).toBeInTheDocument();
    expect(screen.getByText("Ronda 1 de 3")).toBeInTheDocument();
    await userEvent.click(screen.getAllByRole("button", { name: /Alegría|Sorpresa|Tristeza|Enojo|Cara tranquila/ })[0]);
    expect(screen.getByRole("status").textContent).toMatch(/Lo encontraste|Mira otra vez/);
  });
});
