import type { GameType, ParticipantGame } from "../api/types";
import { practiceTargetNames } from "../stimuli/labels";

/**
 * Versión de prueba de los juegos: corre solo en el navegador, sin sesión, sin
 * cámara y sin guardar nada. Sigue las mismas reglas que el juego de una sesión
 * (guided_session_service): tras dos opciones distintas se muestra la respuesta,
 * «Ayuda» quita una opción y no hay puntaje. Las caras son pictogramas, no fotos.
 */

export const TRIAL_ROUNDS = 3;
const OPTION_COUNT = 4;
const MISSES_BEFORE_ANSWER = 2;
// Las cinco expresiones que estima EMOtv.
const TRIAL_EXPRESSIONS = ["happiness", "surprise", "sadness", "anger", "neutral"] as const;
// Dos caras distintas por emoción: al buscar la misma emoción, la pareja no es la misma cara repetida.
const FACES: Record<string, [string, string]> = {
  happiness: ["😊", "😄"], surprise: ["😮", "😲"], sadness: ["😢", "😞"], anger: ["😠", "😡"], neutral: ["😐", "😑"],
};
const ANSWERS: Record<string, string> = {
  happiness: "Es alegría", surprise: "Es sorpresa", sadness: "Es tristeza", anger: "Es enojo", neutral: "Es una cara tranquila",
};
const QUESTION = { matching: "¿Qué emoción muestra esta cara?", similar: "¿Qué cara muestra la misma emoción que la de arriba?" };
const RETRY = { matching: "Mira otra vez la cara.", similar: "Mira otra vez la cara de arriba." };
const lower = (text: string) => text.charAt(0).toLowerCase() + text.slice(1);

export interface TrialOption { key: string; expression: string; face: string }
export interface TrialRound { target: string; face: string; options: TrialOption[] }
export interface TrialGame {
  type: GameType;
  rounds: TrialRound[];
  index: number;
  state: "playing" | "retry" | "matched" | "shown" | "finished";
  tried: string[];
  removed: string | null;
  helped: boolean;
}

function shuffle<T>(items: readonly T[], random: () => number): T[] {
  const copy = [...items];
  for (let index = copy.length - 1; index > 0; index -= 1) {
    const other = Math.floor(random() * (index + 1));
    [copy[index], copy[other]] = [copy[other], copy[index]];
  }
  return copy;
}

/** Rondas al azar, sin repetir la emoción de la ronda anterior. */
export function newTrialGame(type: GameType, random: () => number = Math.random): TrialGame {
  const rounds: TrialRound[] = [];
  for (let index = 0; index < TRIAL_ROUNDS; index += 1) {
    const previous = rounds.at(-1)?.target;
    const target = shuffle(TRIAL_EXPRESSIONS.filter((item) => item !== previous), random)[0];
    const others = shuffle(TRIAL_EXPRESSIONS.filter((item) => item !== target), random).slice(0, OPTION_COUNT - 1);
    const expressions = shuffle([target, ...others], random);
    // Al buscar la misma emoción, la cara de arriba es la primera variante y la pareja, la segunda.
    const options = expressions.map((expression, position) => ({
      key: type === "similar" ? String(position + 1) : expression, expression,
      face: FACES[expression][type === "similar" ? 1 : 0] }));
    rounds.push({ target, face: FACES[target][0], options });
  }
  return { type, rounds, index: 0, state: "playing", tried: [], removed: null, helped: false };
}

const answerKey = (round: TrialRound) => round.options.find((option) => option.expression === round.target)!.key;

export function answerTrial(game: TrialGame, key: string): TrialGame {
  if (game.state !== "playing" && game.state !== "retry") return game;
  const round = game.rounds[game.index];
  if (key === answerKey(round)) return { ...game, state: "matched" };
  const tried = game.tried.includes(key) ? game.tried : [...game.tried, key];
  return { ...game, tried, state: tried.length >= MISSES_BEFORE_ANSWER ? "shown" : "retry" };
}

/** «Ayuda»: quita una opción que no es la respuesta ni se eligió antes. */
export function helpTrial(game: TrialGame, random: () => number = Math.random): TrialGame {
  if (game.helped || (game.state !== "playing" && game.state !== "retry")) return game;
  const round = game.rounds[game.index];
  const correct = answerKey(round);
  const candidates = round.options.map((option) => option.key).filter((key) => key !== correct && !game.tried.includes(key));
  return { ...game, helped: true, removed: candidates.length ? shuffle(candidates, random)[0] : null };
}

export function nextTrial(game: TrialGame): TrialGame {
  if (game.state !== "matched" && game.state !== "shown") return game;
  if (game.index + 1 >= game.rounds.length) return { ...game, state: "finished" };
  return { ...game, index: game.index + 1, state: "playing", tried: [], removed: null, helped: false };
}

/** Lo que ve la persona, con la misma forma que en una sesión. */
export function trialView(game: TrialGame, explanation: (key: string) => string | null = () => null): ParticipantGame {
  const round = game.rounds[game.index];
  const similar = game.type === "similar";
  const revealed = game.state === "matched" || game.state === "shown";
  const name = practiceTargetNames[round.target];
  const messages: Record<TrialGame["state"], string | null> = {
    playing: null,
    retry: `${RETRY[game.type]}${game.helped ? "" : " Puedes pedir ayuda."}`,
    matched: similar ? `Lo encontraste: las dos caras muestran la misma emoción, ${lower(name)}.`
      : `Lo encontraste: ${lower(ANSWERS[round.target])}.`,
    shown: similar ? `Esta cara muestra la misma emoción: ${name}.` : `${ANSWERS[round.target]}.`,
    finished: "Terminaste el juego.",
  };
  return {
    round: String(game.index), number: game.index + 1, total: game.rounds.length, game_type: game.type,
    question: QUESTION[game.type], state: game.state,
    options: round.options.map((option) => ({ key: option.key,
      label: similar ? `Cara ${option.key}` : practiceTargetNames[option.expression],
      available: !game.tried.includes(option.key) && option.key !== game.removed })),
    answer: revealed ? answerKey(round) : null,
    message: messages[game.state],
    explanation: revealed ? explanation(round.target) : null,
    can_help: (game.state === "playing" || game.state === "retry") && !game.helped,
    last_round: game.index + 1 === game.rounds.length,
  };
}

/** Una cara como imagen SVG (sin archivos ni servicios externos). */
export function faceSvg(face: string): string {
  return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 120"><text x="60" y="64" font-size="96" text-anchor="middle" dominant-baseline="middle">${face}</text></svg>`;
}
export const faceUrl = (face: string) => `data:image/svg+xml;charset=utf-8,${encodeURIComponent(faceSvg(face))}`;
