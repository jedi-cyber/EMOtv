import type { Activity, ActivityStep } from "../api/types";

export function speechAvailable(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window &&
    "SpeechSynthesisUtterance" in window;
}

export function speakExercise(activity: Activity): boolean {
  return speakText(`${activity.name}. ${activity.description}. Mantén la postura durante ${activity.duration_seconds} segundos.`);
}

/** Anuncia un paso. `index`/`count` numeran los pasos; si se indica una
 * repetición de una actividad con varias, también se anuncia. */
export function speakStep(
  step: ActivityStep, index: number, count: number,
  repetition?: { index: number; count: number },
): boolean {
  const round = repetition && repetition.count > 1 ? ` Repetición ${repetition.index + 1} de ${repetition.count}.` : "";
  return speakText(`Paso ${index + 1} de ${count}.${round} ${step.instruction}. Mantén la postura durante ${step.duration_seconds} segundos.`);
}

function speakText(instruction: string): boolean {
  if (!speechAvailable()) return false;
  const synth = window.speechSynthesis;
  const utterance = new SpeechSynthesisUtterance(instruction);
  utterance.lang = "es-PE";
  utterance.rate = 0.9;
  const spanishVoice = synth.getVoices().find((voice) => voice.lang.toLowerCase().startsWith("es"));
  if (spanishVoice) utterance.voice = spanishVoice;
  synth.cancel();
  synth.speak(utterance);
  return true;
}

export function stopExerciseSpeech(): void {
  if (speechAvailable()) window.speechSynthesis.cancel();
}
