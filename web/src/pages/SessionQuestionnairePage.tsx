import { useNavigate, useParams } from "react-router-dom";
import type { Questionnaire, QuestionnaireMoment } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { ButtonLink } from "../components/Button";
import { Callout } from "../components/Callout";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { SessionQuestionnaire } from "../questionnaires/SessionQuestionnaire";
import { paths } from "../routes/paths";

/** Responder el cuestionario previo o posterior de una sesión. */
export function SessionQuestionnairePage() {
  const { sessionId = "", moment = "pre" } = useParams();
  const navigate = useNavigate();
  const kind: QuestionnaireMoment = moment === "post" ? "post" : "pre";
  const query = useApiQuery<{ questionnaire: Questionnaire; answered: boolean }>(
    `/sessions/${encodeURIComponent(sessionId)}/questionnaires/${kind}`);
  const data = query.data;

  return <section>
    <ButtonLink variant="ghost" className="back-link" to={paths.session(sessionId)}>← Volver a la sesión</ButtonLink>
    <PageHeader title={kind === "pre" ? "Cuestionario previo" : "Cuestionario posterior"}
      description={kind === "pre" ? "Se responde antes de iniciar el analizador." : "Se responde al terminar la sesión."} />
    <PageState {...query} onRetry={query.reload} />
    {data?.answered && <Callout variant="success">Este cuestionario ya se respondió en la sesión.</Callout>}
    {data && !data.answered && <SessionQuestionnaire sessionId={sessionId} moment={kind} questionnaire={data.questionnaire}
      onDone={() => navigate(paths.session(sessionId))} />}
  </section>;
}
