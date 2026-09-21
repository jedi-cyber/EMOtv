import { afterEach, describe, expect, it, vi } from "vitest";
import { speakExercise, speechAvailable, stopExerciseSpeech } from "../src/analysis/exerciseSpeech";

const activity = {
  id: "arms_up_5s", name: "Elevación de brazos", description: "Levanta ambos brazos",
  required_posture: "arms_up", duration_seconds: 5, repetitions: 1,
};

afterEach(() => vi.unstubAllGlobals());

describe("instrucciones habladas", () => {
  it("permanece opcional si el navegador no tiene síntesis de voz", () => {
    vi.stubGlobal("SpeechSynthesisUtterance", undefined);
    expect(speechAvailable()).toBe(false);
    expect(speakExercise(activity)).toBe(false);
  });

  it("lee la instrucción en español y detiene la voz al salir", () => {
    class Utterance {
      lang = "";
      rate = 1;
      voice: unknown = null;
      constructor(public text: string) {}
    }
    const voice = { lang: "es-PE", name: "Español" };
    const synth = { getVoices: vi.fn(() => [voice]), cancel: vi.fn(), speak: vi.fn() };
    vi.stubGlobal("SpeechSynthesisUtterance", Utterance);
    vi.stubGlobal("speechSynthesis", synth);
    expect(speakExercise(activity)).toBe(true);
    const utterance = synth.speak.mock.calls[0][0] as Utterance;
    expect(utterance.text).toContain("Levanta ambos brazos");
    expect(utterance.text).toContain("5 segundos");
    expect(utterance.lang).toBe("es-PE");
    expect(utterance.voice).toBe(voice);
    stopExerciseSpeech();
    expect(synth.cancel).toHaveBeenCalledTimes(2);
  });
});
