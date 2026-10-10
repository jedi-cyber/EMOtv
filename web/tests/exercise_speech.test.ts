import { afterEach, describe, expect, it, vi } from "vitest";
import { speakExercise, speakStep, speechAvailable, stopExerciseSpeech } from "../src/analysis/exerciseSpeech";
import { remainingSeconds, stepPosition } from "../src/analysis/activityProgress";

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

describe("posición en actividades con repeticiones", () => {
  it("numera el paso dentro de la repetición", () => {
    expect(stepPosition(0, 6, 2)).toEqual({ step: 1, steps: 3, repetition: 1, repetitions: 2 });
    expect(stepPosition(4, 6, 2)).toEqual({ step: 2, steps: 3, repetition: 2, repetitions: 2 });
    expect(stepPosition(9, 6, 2)).toEqual({ step: 3, steps: 3, repetition: 2, repetitions: 2 });
    expect(stepPosition(1, 3)).toEqual({ step: 2, steps: 3, repetition: 1, repetitions: 1 });
  });

  it("redondea el tiempo restante hacia arriba sin bajar de cero", () => {
    expect(remainingSeconds(1.2)).toBe(2);
    expect(remainingSeconds(2)).toBe(2);
    expect(remainingSeconds(-1)).toBe(0);
    expect(remainingSeconds(undefined)).toBe(0);
  });

  it("anuncia la repetición solo si hay más de una", () => {
    class Utterance { lang = ""; rate = 1; voice: unknown = null; constructor(public text: string) {} }
    const synth = { getVoices: vi.fn(() => []), cancel: vi.fn(), speak: vi.fn() };
    vi.stubGlobal("SpeechSynthesisUtterance", Utterance);
    vi.stubGlobal("speechSynthesis", synth);
    const step = { posture: "arms_up", instruction: "Eleva los brazos", duration_seconds: 4 };
    speakStep(step, 1, 3, { index: 1, count: 2 });
    speakStep(step, 0, 3, { index: 0, count: 1 });
    const texts = synth.speak.mock.calls.map(([utterance]) => (utterance as Utterance).text);
    expect(texts[0]).toBe("Paso 2 de 3. Repetición 2 de 2. Eleva los brazos. Mantén la postura durante 4 segundos.");
    expect(texts[1]).toBe("Paso 1 de 3. Eleva los brazos. Mantén la postura durante 4 segundos.");
  });
});
