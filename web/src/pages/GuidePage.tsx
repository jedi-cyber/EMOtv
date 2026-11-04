import { useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { useAssistant } from "../components/AssistantContext";
import { EMI_ROLES } from "../components/AssistantWidget";
import { Button, ButtonLink } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { navigationByRole } from "../routes/navigation";
import { paths } from "../routes/paths";

export interface GuideTopic {
  id: string;
  title: string;
  steps: string[];
  note: string | null;
}

/** Pantalla donde se hace cada tema; el enlace solo aparece si el menú del papel la tiene. */
const topicScreens: Record<string, string> = {
  "first-steps": paths.analysis,
  material: paths.protocols,
  "own-images": paths.images,
  conduct: paths.analysis,
  after: paths.sessions,
  supervise: paths.reviews,
  teach: paths.protocols,
  statistics: paths.statistics,
  "admin-accounts": paths.users,
  "admin-stimuli": paths.stimuli,
  audit: paths.audit,
};

/** Pasos marcados como hechos: comodidad de este navegador, nunca un dato del servidor. */
type DoneSteps = Record<string, number[]>;

function storageKey(userId: string) {
  return `emotv.guide.done.${userId}`;
}

function readDone(userId: string): DoneSteps {
  try {
    const raw = window.localStorage.getItem(storageKey(userId));
    const parsed: unknown = raw ? JSON.parse(raw) : {};
    return parsed && typeof parsed === "object" ? parsed as DoneSteps : {};
  } catch {
    return {};
  }
}

function writeDone(userId: string, done: DoneSteps) {
  try {
    window.localStorage.setItem(storageKey(userId), JSON.stringify(done));
  } catch {
    // Sin almacenamiento (ventana privada): los pasos se marcan solo mientras dura la página.
  }
}

/** Minúsculas y sin tildes, para que «sesion» encuentre «sesión». */
function fold(text: string) {
  return text.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase();
}

/** Resalta lo buscado; `fold` conserva la longitud de cada letra con tilde. */
function highlight(text: string, term: string): ReactNode {
  if (!term) return text;
  const folded = fold(text);
  const parts: ReactNode[] = [];
  let from = 0;
  for (let at = folded.indexOf(term); at !== -1; at = folded.indexOf(term, from)) {
    if (at > from) parts.push(text.slice(from, at));
    parts.push(<mark key={at}>{text.slice(at, at + term.length)}</mark>);
    from = at + term.length;
  }
  parts.push(text.slice(from));
  return parts;
}

/** Guía de uso: tareas paso a paso para el papel de la cuenta. El servidor elige los temas. */
export function GuidePage() {
  const query = useApiQuery<{ topics: GuideTopic[] }>("/guide");
  const topics = useMemo(() => query.data?.topics ?? [], [query.data]);
  const { user } = useAuth();
  const assistant = useAssistant();
  const userId = user?.id ?? "anonimo";
  const [search, setSearch] = useState("");
  const [done, setDone] = useState<DoneSteps>(() => readDone(userId));
  const [open, setOpen] = useState<Set<string>>(new Set());

  const term = fold(search.trim());
  const visible = term
    ? topics.filter((topic) => [topic.title, topic.note ?? "", ...topic.steps].some((text) => fold(text).includes(term)))
    : topics;
  const screens = new Map((user ? navigationByRole[user.role] : []).map((item) => [item.to, item.label]));
  const canAskEmi = !!assistant && !!user && EMI_ROLES.has(user.role);
  const totalSteps = topics.reduce((sum, topic) => sum + topic.steps.length, 0);
  const totalDone = topics.reduce((sum, topic) => sum + (done[topic.id]?.length ?? 0), 0);

  function save(next: DoneSteps) {
    setDone(next);
    writeDone(userId, next);
  }

  function toggleStep(topicId: string, index: number) {
    const current = new Set(done[topicId] ?? []);
    if (current.has(index)) current.delete(index); else current.add(index);
    save({ ...done, [topicId]: [...current].sort((a, b) => a - b) });
  }

  function toggleTopic(id: string, isOpen: boolean) {
    setOpen((current) => {
      const next = new Set(current);
      if (isOpen) next.add(id); else next.delete(id);
      return next;
    });
  }

  function goTo(id: string) {
    toggleTopic(id, true);
    window.requestAnimationFrame(() => document.getElementById(`guia-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" }));
  }

  return <section className="guide">
    <PageHeader title="Guía de uso"
      description="Cómo hacer cada tarea en EMOtv, paso a paso. Si tienes una duda que no está aquí, pregúntale a Emi." />
    <PageState {...query} empty={!query.loading && !query.error && topics.length === 0}
      emptyMessage="No hay temas de la guía para tu cuenta." onRetry={query.reload} />
    {topics.length > 0 && <>
      <div className="filter-bar guide-toolbar">
        <label>Buscar en la guía
          <input type="search" value={search} placeholder="Por ejemplo: reporte, imagen, código"
            onChange={(event) => setSearch(event.target.value)} />
        </label>
        <Button variant="secondary" type="button" onClick={() => setOpen(new Set(visible.map((topic) => topic.id)))}>Abrir todos</Button>
        <Button variant="secondary" type="button" onClick={() => setOpen(new Set())}>Cerrar todos</Button>
      </div>
      <div className="progress-label"><span>Pasos que marcaste como hechos</span><strong>{totalDone} de {totalSteps}</strong></div>
      <div className="progress-track small" aria-hidden="true"><div style={{ width: `${totalSteps ? (totalDone / totalSteps) * 100 : 0}%` }} /></div>
      {term && <p className="filter-summary" role="status">
        {visible.length === 0 ? "Ningún tema coincide con la búsqueda. Prueba con otra palabra o pregúntale a Emi."
          : visible.length === 1 ? "1 tema coincide con la búsqueda." : `${visible.length} temas coinciden con la búsqueda.`}
      </p>}
      <nav className="guide-index" aria-label="Temas de la guía">
        {visible.map((topic) => {
          const complete = (done[topic.id]?.length ?? 0) === topic.steps.length;
          return <a key={topic.id} href={`#guia-${topic.id}`} className={complete ? "guide-chip done" : "guide-chip"}
            onClick={(event) => { event.preventDefault(); goTo(topic.id); }}>
            {complete && <span className="sr-only">Completado: </span>}{topic.title}
          </a>;
        })}
      </nav>
      <ul className="card-list guide-topics">{visible.map((topic) => {
        const marked = new Set(done[topic.id] ?? []);
        const screen = topicScreens[topic.id];
        const screenLabel = screen ? screens.get(screen) : undefined;
        return <li key={topic.id} id={`guia-${topic.id}`} className="card guide-topic">
          <details open={!!term || open.has(topic.id)} onToggle={(event) => {
            if (!term) toggleTopic(topic.id, event.currentTarget.open);
          }}>
            <summary>
              <h2>{highlight(topic.title, term)}</h2>
              <span className="guide-count">{marked.size} de {topic.steps.length} pasos</span>
            </summary>
            <div className="form-stack guide-body">
              <ol className="guide-steps">{topic.steps.map((step, index) => <li key={step}>
                <Checkbox checked={marked.has(index)} onChange={() => toggleStep(topic.id, index)}>
                  {highlight(step, term)}
                </Checkbox>
              </li>)}</ol>
              {topic.note && <p className="muted">{highlight(topic.note, term)}</p>}
              <div className="inline-actions">
                {screen && screenLabel && <ButtonLink variant="primary" to={screen}>Ir a {screenLabel}</ButtonLink>}
                {canAskEmi && <Button variant="secondary" type="button"
                  onClick={() => assistant.askAssistant(`¿Cómo hago esto en EMOtv: ${topic.title.toLowerCase()}?`)}>
                  Preguntar a Emi
                </Button>}
                {marked.size > 0 && <Button variant="secondary" type="button" onClick={() => save({ ...done, [topic.id]: [] })}>
                  Desmarcar los pasos
                </Button>}
              </div>
            </div>
          </details>
        </li>;
      })}</ul>
    </>}
    <Callout variant="info" role="note">
      EMOtv estima la expresión facial visible: no diagnostica, no indica lo que una persona siente y no sustituye a un
      profesional.
    </Callout>
  </section>;
}
