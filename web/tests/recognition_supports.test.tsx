import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ParticipantRecognition } from "../src/api/types";
import { RecognitionStage } from "../src/pages/ParticipantViewPage";

// Bloque 3: consignas breves, explicación del catálogo, «Escuchar», elección marcada
// con texto y retroalimentación sin valorar a la persona.
const VALUATIONS = /correct|incorrect|acertaste|fallaste|bien hecho|muy bien|excelente|error|mal\b|diagn|patol/i;
const STORY = "A Lucía se le cayó su helado al piso.";
const EXPLANATION = "En la tristeza, las cejas suben en el centro y las puntas de la boca bajan.";
const NOTE = "En una situación así, cada persona puede sentir algo distinto.";

const open: ParticipantRecognition = {
  question: "¿Qué emoción es?", situation: null, chosen: null, message: null, explanation: null, note: null,
  options: [{ key: "sadness", label: "Tristeza" }, { key: "happiness", label: "Alegría" }, { key: "fear", label: "Miedo" }],
};

function stage(recognition: ParticipantRecognition, onAnswer = vi.fn().mockResolvedValue(undefined)) {
  return { onAnswer, ...render(<RecognitionStage recognition={recognition} imageUrl={null} onAnswer={onAnswer} />) };
}

function speech() {
  const speak = vi.fn();
  class Utterance { text: string; lang = ""; rate = 1; voice: unknown = null; constructor(text: string) { this.text = text; } }
  Object.defineProperty(window, "speechSynthesis", { configurable: true,
    value: { speak, cancel: vi.fn(), getVoices: () => [] } });
  Object.defineProperty(window, "SpeechSynthesisUtterance", { configurable: true, value: Utterance });
  return speak;
}

afterEach(() => {
  Reflect.deleteProperty(window, "speechSynthesis");
  Reflect.deleteProperty(window, "SpeechSynthesisUtterance");
});

describe("apoyos del reconocimiento", () => {
  it("antes de responder solo hay la consigna breve: ni respuesta ni explicación", () => {
    stage(open);
    expect(screen.getByText("¿Qué emoción es?")).toBeInTheDocument();
    expect(screen.queryByText(EXPLANATION)).not.toBeInTheDocument();
    expect(screen.queryByText(/Tu elección/)).not.toBeInTheDocument();
  });

  it("al terminar explica la emoción de la imagen y marca la elegida con texto, sin valorar", () => {
    stage({ ...open, chosen: "happiness", message: "Es tristeza", explanation: EXPLANATION });
    const status = screen.getByRole("status");
    expect(within(status).getByText("Es tristeza")).toBeInTheDocument();
    expect(within(status).getByText(EXPLANATION)).toBeInTheDocument();
    // La elegida se reconoce por el texto, no solo por el color.
    const chosen = screen.getByRole("button", { name: "Alegría" });
    expect(chosen).toHaveAttribute("aria-pressed", "true");
    expect(within(chosen).getByText("✓ Tu elección")).toBeInTheDocument();
    expect(within(screen.getByRole("button", { name: "Tristeza" })).queryByText(/Tu elección/)).toBeNull();
    expect(document.body.textContent).not.toMatch(VALUATIONS);
  });

  it("con una situación aclara que cada persona puede sentir algo distinto", () => {
    stage({ ...open, question: "¿Qué emoción muestra la cara?", situation: STORY, chosen: "sadness",
      message: "La cara de la imagen muestra tristeza.", explanation: EXPLANATION, note: NOTE });
    expect(screen.getByText("La cara de la imagen muestra tristeza.")).toBeInTheDocument();
    expect(screen.getByText(NOTE)).toBeInTheDocument();
  });

  it("«Escuchar» repite la consigna y, al terminar, la respuesta y la explicación", async () => {
    const speak = speech();
    const { rerender, onAnswer } = stage({ ...open, situation: STORY });
    await userEvent.click(screen.getByRole("button", { name: "Escuchar" }));
    await userEvent.click(screen.getByRole("button", { name: "Escuchar" }));
    expect(speak).toHaveBeenCalledTimes(2);
    expect(speak.mock.calls[0][0].text).toBe(`${STORY} ¿Qué emoción es?`);
    // Escuchar no responde por la persona.
    expect(onAnswer).not.toHaveBeenCalled();
    rerender(<RecognitionStage recognition={{ ...open, chosen: "sadness", message: "Es tristeza", explanation: EXPLANATION }}
      imageUrl={null} onAnswer={onAnswer} />);
    await userEvent.click(screen.getByRole("button", { name: "Escuchar" }));
    expect(speak.mock.calls[2][0].text).toBe(`Es tristeza ${EXPLANATION}`);
  });

  it("sin voz en el navegador no se ofrece «Escuchar»", () => {
    stage(open);
    expect(screen.queryByRole("button", { name: "Escuchar" })).not.toBeInTheDocument();
  });
});
