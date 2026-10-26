import { useState } from "react";
import { apiRequest } from "../api/http";
import type { Answers, Questionnaire, QuestionnaireMoment } from "../api/types";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { QuestionnaireForm } from "./QuestionnaireForm";

type Mode = "participant" | "conductor";

/**
 * Aplica el cuestionario de una sesión. En la pantalla de la persona, ella
 * responde; en el registro manual, quien conduce la
 * sesión anota las respuestas que le dieron.
 */
export function SessionQuestionnaire({ sessionId, moment, questionnaire, onDone }: {
  sessionId: string;
  moment: QuestionnaireMoment;
  questionnaire: Questionnaire;
  onDone: () => void;
}) {
  const { token } = useAuth();
  const [mode, setMode] = useState<Mode>("participant");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function submit(answers: Answers) {
    setBusy(true); setError("");
    try {
      await apiRequest(`/sessions/${encodeURIComponent(sessionId)}/questionnaires/${moment}`, {
        method: "POST", token, body: JSON.stringify({ answers, entry_mode: mode }),
      });
      onDone();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudieron guardar las respuestas."); }
    finally { setBusy(false); }
  }

  return <section className="session-questionnaire" aria-label={moment === "pre" ? "Cuestionario previo" : "Cuestionario posterior"}>
    <div className="inline-actions" role="group" aria-label="Quién registra las respuestas">
      <Button variant={mode === "participant" ? "secondary" : "ghost"} aria-pressed={mode === "participant"}
        onClick={() => setMode("participant")}>Responde la persona</Button>
      <Button variant={mode === "conductor" ? "secondary" : "ghost"} aria-pressed={mode === "conductor"}
        onClick={() => setMode("conductor")}>Registrar a mano</Button>
    </div>
    <p className="muted">{mode === "participant"
      ? "Entrega la pantalla a la persona para que responda."
      : "Anota las respuestas tal como te las dieron."}</p>
    {error && <Callout variant="error">{error}</Callout>}
    <QuestionnaireForm key={mode} questionnaire={questionnaire} large={mode === "participant"} busy={busy}
      submitLabel={moment === "pre" ? "Guardar y continuar" : "Guardar respuestas"} onSubmit={submit} />
  </section>;
}
