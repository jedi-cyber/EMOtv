import { useApiQuery } from "../api/useApiQuery";
import { Callout } from "../components/Callout";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";

export interface GuideTopic {
  id: string;
  title: string;
  steps: string[];
  note: string | null;
}

/** Guía de uso: tareas paso a paso para el papel de la cuenta. El servidor elige los temas. */
export function GuidePage() {
  const query = useApiQuery<{ topics: GuideTopic[] }>("/guide");
  const topics = query.data?.topics ?? [];
  return <section>
    <PageHeader title="Guía de uso"
      description="Cómo hacer cada tarea en EMOtv, paso a paso. Si tienes una duda que no está aquí, pregúntale a Emi." />
    <PageState {...query} empty={!query.loading && !query.error && topics.length === 0}
      emptyMessage="No hay temas de la guía para tu cuenta." onRetry={query.reload} />
    {topics.length > 0 && <ul className="card-list">{topics.map((topic) => <li key={topic.id} className="card form-stack">
      <h2>{topic.title}</h2>
      <ol>{topic.steps.map((step) => <li key={step}>{step}</li>)}</ol>
      {topic.note && <p className="muted">{topic.note}</p>}
    </li>)}</ul>}
    <Callout variant="info" role="note">
      EMOtv estima la expresión facial visible: no diagnostica, no indica lo que una persona siente y no sustituye a un
      profesional.
    </Callout>
  </section>;
}
