import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { ParticipantGame } from "../src/api/types";
import { MatchingGameStage } from "../src/game/MatchingGameStage";

// «Responde con la cara»: la persona pone la cara de la emoción y la cámara marca la
// opción que coincide. Su pantalla no tiene botones para las opciones y nunca
// muestra niveles ni la expresión estimada.

function faceGame(game: Partial<ParticipantGame> = {}): ParticipantGame {
  return {
    round: "0-1-0", number: 1, total: 2, game_type: "matching", question: "¿Qué emoción muestra esta cara?",
    state: "playing", answer: null, explanation: null, can_help: true, last_round: false, asks_face: false,
    message: "Mira la imagen y pon la cara de esa emoción. Sostenla y la cámara marcará la opción.",
    options: [{ key: "sadness", label: "Tristeza", available: true }, { key: "happiness", label: "Alegría", available: true }],
    answers_by_face: true, ...game,
  };
}

describe("Responde con la cara", () => {
  it("muestra las opciones sin botón y la invitación a poner la cara", () => {
    const onAction = vi.fn(async () => undefined);
    render(<MatchingGameStage game={faceGame()} imageUrl={null} onAction={onAction} />);
    expect(screen.getByText(/pon la cara de esa emoción/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Tristeza|Alegría/ })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Tristeza")).toBeInTheDocument();
    // «Ayuda» sigue disponible.
    expect(screen.getByRole("button", { name: "Ayuda" })).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/%|nivel|probab/i);
  });

  it("la opción que marcó la cámara queda marcada", () => {
    render(<MatchingGameStage imageUrl={null} onAction={vi.fn(async () => undefined)} game={faceGame({
      state: "retry", message: "Mira otra vez la imagen.",
      options: [{ key: "sadness", label: "Tristeza", available: false }, { key: "happiness", label: "Alegría", available: true }],
    })} />);
    expect(screen.getByLabelText("Tristeza: marcada, no es esta")).toBeInTheDocument();
    expect(screen.getByText("Marcada")).toBeInTheDocument();
  });

  it("sin cámara se responde con botones", () => {
    render(<MatchingGameStage game={faceGame({ answers_by_face: false, message: null })} imageUrl={null}
      onAction={vi.fn(async () => undefined)} />);
    expect(screen.getByRole("button", { name: "Tristeza" })).toBeEnabled();
  });

  it("al terminar la ronda se ve como siempre, con la respuesta", () => {
    render(<MatchingGameStage imageUrl={null} onAction={vi.fn(async () => undefined)} game={faceGame({
      state: "matched", answer: "happiness", answers_by_face: false, message: "Lo encontraste: es alegría.",
    })} />);
    expect(screen.getByRole("button", { name: /Alegría/ })).toHaveAttribute("aria-pressed", "true");
  });
});
