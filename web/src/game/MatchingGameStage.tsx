import { useEffect, useState } from "react";
import type { ParticipantGame } from "../api/types";
import { speakText, speechAvailable, stopExerciseSpeech } from "../analysis/exerciseSpeech";
import { Button } from "../components/Button";
import { emotionPictograms } from "../stimuli/labels";

export type GameAction = "answer" | "help" | "next";

/** Las imágenes de las opciones de una ronda, como URL locales que se liberan al cambiar de ronda. */
function useOptionImages(keys: string[], round: string, load?: (key: string) => Promise<Blob>) {
  const [urls, setUrls] = useState<Record<string, string>>({});
  const joined = keys.join(",");
  useEffect(() => {
    if (!load || !joined) { setUrls({}); return undefined; }
    let cancelled = false;
    const made: string[] = [];
    void Promise.all(joined.split(",").map(async (key) => {
      try { const url = URL.createObjectURL(await load(key)); made.push(url); return [key, url] as const; }
      catch { return [key, ""] as const; }
    })).then((pairs) => { if (!cancelled) setUrls(Object.fromEntries(pairs)); });
    return () => { cancelled = true; made.forEach((url) => URL.revokeObjectURL(url)); };
  }, [round, joined, load]);
  return urls;
}

/**
 * Juegos con botones (sin arrastrar). «Empareja la emoción»: la imagen de la
 * ronda y un botón por emoción. «Busca la misma emoción»: la imagen modelo
 * arriba y un botón con cada cara para elegir la de la misma emoción. Si la
 * persona elige otra, se le invita a mirar otra vez; tras dos, se le muestra
 * cuál es con su explicación. «Ayuda» quita una opción y lee la pregunta. Sin
 * puntaje ni comparación: solo «Ronda 2 de 3».
 */
export function MatchingGameStage({ game, imageUrl, onAction, loadOption, pictograms = false, readAloud = false }: {
  game: ParticipantGame; imageUrl: string | null;
  onAction: (action: GameAction, expression?: string) => Promise<void>;
  /** Al buscar la misma emoción: la imagen de cada opción. */
  loadOption?: (key: string) => Promise<Blob>;
  /** Pictogramas junto a cada emoción. */
  pictograms?: boolean;
  /** Lee la pregunta al empezar la ronda y la respuesta al terminarla. */
  readAloud?: boolean;
}) {
  const [sending, setSending] = useState(false);
  const similar = game.game_type === "similar";
  const optionImages = useOptionImages(similar ? game.options.map((option) => option.key) : [], game.round,
    similar ? loadOption : undefined);
  const playing = game.state === "playing" || game.state === "retry";
  const revealed = game.state === "matched" || game.state === "shown";
  const spokenText = (revealed || game.state === "retry" || game.state === "finished" || game.state === "ended"
    ? [game.message, game.explanation] : [game.question]).filter(Boolean).join(" ");
  useEffect(() => () => stopExerciseSpeech(), []);
  // Se lee al empezar la ronda y otra vez al cambiar lo que pasó en ella.
  useEffect(() => { if (readAloud) speakText(spokenText); }, [readAloud, game.round, game.state]);

  async function send(action: GameAction, expression?: string) {
    setSending(true);
    try { await onAction(action, expression); } catch { /* el estado siguiente lo dice */ } finally { setSending(false); }
  }

  return <div className="participant-practice matching-game">
    <p className="matching-game-round">Ronda {game.number} de {game.total}</p>
    {imageUrl && <img className="participant-illustration" src={imageUrl}
      alt={similar ? "Cara de arriba, la que hay que comparar" : "Cara de la ronda"} />}
    <p className="participant-instruction">{game.question}</p>
    <div className={similar ? "recognition-options similar-game-options" : "recognition-options"}>
      {game.options.map((option) => {
        const isAnswer = revealed && game.answer === option.key;
        return <Button key={option.key} className="recognition-option"
          variant={isAnswer ? "primary" : "secondary"} aria-pressed={isAnswer}
          disabled={!playing || !option.available || sending} onClick={() => { void send("answer", option.key); }}>
          {/* Al buscar la misma emoción no hay pictogramas: dirían la respuesta. */}
          {!similar && pictograms && emotionPictograms[option.key] && <span className="recognition-pictogram" aria-hidden="true">{emotionPictograms[option.key]}</span>}
          {similar && (optionImages[option.key]
            ? <img className="similar-game-face" src={optionImages[option.key]} alt="" />
            : <span className="similar-game-face" aria-hidden="true" />)}
          {option.label}
          {/* Visible para no depender del color. */}
          {isAnswer && <span className="recognition-chosen" aria-hidden="true">✓ Es esta</span>}
        </Button>;
      })}
    </div>
    <div className="recognition-feedback" role="status" aria-live="polite">
      <p className="participant-achieved recognition-answer">{game.message ?? ""}</p>
      {game.explanation && <p className="recognition-explanation">{game.explanation}</p>}
    </div>
    <div className="inline-actions matching-game-actions">
      {revealed && <Button variant="primary" disabled={sending} onClick={() => { void send("next"); }}>
        {game.last_round ? "Terminar el juego" : "Siguiente"}</Button>}
      {game.can_help && <Button variant="secondary" disabled={sending} onClick={() => {
        if (speechAvailable()) speakText(game.question);
        void send("help");
      }}>Ayuda</Button>}
      {speechAvailable() && <Button variant="secondary" onClick={() => { speakText(spokenText); }}>Escuchar</Button>}
    </div>
  </div>;
}
