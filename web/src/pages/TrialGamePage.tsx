import { useCallback, useMemo, useState } from "react";
import { Navigate, useNavigate, useParams } from "react-router-dom";
import type { GameType } from "../api/types";
import { Button } from "../components/Button";
import { useExpressionCatalog } from "../expressions/ExpressionCatalog";
import { MatchingGameStage, type GameAction } from "../game/MatchingGameStage";
import { answerTrial, faceSvg, faceUrl, helpTrial, newTrialGame, nextTrial, trialView } from "../game/trialGame";
import { paths } from "../routes/paths";

const GAME_TYPES: GameType[] = ["matching", "similar"];

/**
 * Versión de prueba de un juego, a pantalla completa como la pantalla de la
 * persona. Corre en el navegador: no crea una sesión, no usa la cámara y no
 * guarda nada. Sirve para conocer el juego antes de ponerlo en un protocolo.
 */
export function TrialGamePage() {
  const { kind = "" } = useParams();
  const navigate = useNavigate();
  const { info } = useExpressionCatalog();
  const type = GAME_TYPES.find((item) => item === kind);
  const [game, setGame] = useState(() => newTrialGame(type ?? "matching"));
  const round = game.rounds[game.index];
  const view = useMemo(() => trialView(game, (key) => info(key)?.child_explanation ?? null), [game, info]);
  const loadOption = useCallback(async (key: string) => {
    const face = round.options.find((option) => option.key === key)?.face ?? "";
    return new Blob([faceSvg(face)], { type: "image/svg+xml" });
  }, [round]);
  if (!type) return <Navigate to={paths.games} replace />;

  async function act(action: GameAction, key?: string) {
    setGame((current) => action === "answer" && key ? answerTrial(current, key)
      : action === "help" ? helpTrial(current) : nextTrial(current));
  }

  return <main className="participant-view">
    <p className="participant-notice">Versión de prueba: no crea una sesión, no usa la cámara y no guarda nada.</p>
    <div className="participant-view-stage">
      {game.state === "finished"
        ? <div className="participant-practice">
          <p className="participant-instruction">Terminaste el juego.</p>
          <div className="inline-actions">
            <Button variant="primary" onClick={() => setGame(newTrialGame(type))}>Jugar otra vez</Button>
          </div>
        </div>
        : <MatchingGameStage game={view} imageUrl={faceUrl(round.face)} onAction={act}
          loadOption={type === "similar" ? loadOption : undefined} />}
    </div>
    <div className="participant-actions">
      <Button variant="ghost" onClick={() => { navigate(paths.games); }}>Salir</Button>
    </div>
  </main>;
}
