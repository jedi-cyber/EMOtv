import { useState } from "react";
import type { FormEvent } from "react";
import { apiRequest } from "../api/http";
import type { PauseMode, Protocol, ProtocolStep, ProtocolSupports, Questionnaire, Stimulus } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button, ButtonLink } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { Modal } from "../components/Modal";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip } from "../components/StatusChip";
import { QuestionnaireEditor } from "../questionnaires/QuestionnaireEditor";
import { paths } from "../routes/paths";
import { ACCESSIBLE_RECOGNITION, ACCESSIBLE_TIME_FACTOR, DEFAULT_PRACTICE, DRAWING_SECONDS, DEFAULT_RECOGNITION, MAX_HOLD_SECONDS, MAX_SITUATION_CHARS, MAX_STEP_SECONDS, practiceProblem, practiceTargetNames, protocolStepParts,
  RECOGNITION_OPTION_COUNTS, recognizable, stimulusSummary } from "../stimuli/labels";
import { NoticeList } from "../components/NoticeList";

interface Draft {
  name: string;
  description: string;
  /** null hasta que se responde «¿Para adultos o para niños?»: es obligatorio. */
  for_children: boolean | null;
  /** Apoyos de la pantalla de la persona; «Modo accesible» es un preajuste. */
  supports: ProtocolSupports;
  steps: ProtocolStep[];
  pre_questionnaire_id: string;
  post_questionnaire_id: string;
}

type Moment = "pre" | "post";

const noSupports: ProtocolSupports = { pictograms: false, large_controls: false, read_aloud: false, no_time_limit: false, pause: "normal" };
const emptyDraft: Draft = { name: "", description: "", for_children: null, supports: noSupports, steps: [], pre_questionnaire_id: "", post_questionnaire_id: "" };
const pauseNames: Record<PauseMode, string> = {
  normal: "Normal", long: "Larga (el doble)", wait: "Esperar a que quien conduce pulse «Seguir»",
};
/** El modo accesible de siempre: pictogramas, botones grandes y pausa larga. */
function accessibleOn(supports: ProtocolSupports) { return supports.pictograms && supports.large_controls; }
function anySupport(supports: ProtocolSupports) {
  return supports.pictograms || supports.large_controls || supports.read_aloud || supports.no_time_limit || supports.pause !== "normal";
}

/** Con niños solo imágenes «Para niños» (leves) y aprobadas; el servidor aplica la misma regla. */
function suitableForChildren(item: Stimulus) {
  return item.active && item.approved && item.audience === "children";
}

/** Protocolos: recetas guardadas que el Analizador aplica en una sesión. */
export function ProtocolsPage() {
  const { token, user } = useAuth();
  const isDocente = user?.role === "psychologist";
  const query = useApiQuery<Protocol[]>("/protocols");
  const stimuliQuery = useApiQuery<Stimulus[]>("/stimuli");
  const questionnairesQuery = useApiQuery<Questionnaire[]>("/questionnaires");
  const questionnaires = questionnairesQuery.data ?? [];
  // Solo cuentas de voluntarios (PRUEBA-NN) en modo demo: el servidor decide.
  const validationQuery = useApiQuery<{ available: boolean; protocol_id: string | null }>("/practice-validation/protocol");
  const validation = validationQuery.data && "available" in validationQuery.data ? validationQuery.data : null;
  // Lo que propone el editor para un ejercicio nuevo; lo configura el servidor.
  const defaultsQuery = useApiQuery<{ hold_seconds: number; max_seconds: number }>("/protocols/practice-defaults");
  const practiceDefaults = defaultsQuery.data && "hold_seconds" in defaultsQuery.data ? defaultsQuery.data : DEFAULT_PRACTICE;
  const protocols = query.data ?? [];
  const stimuli = stimuliQuery.data ?? [];
  const byId = new Map(stimuli.map((item) => [item.id, item]));
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [editing, setEditing] = useState<Protocol | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  // Cuestionario nuevo creado sin salir del protocolo: se elige como previo o posterior.
  const [questionnaireFor, setQuestionnaireFor] = useState<Moment | null>(null);
  const [choice, setChoice] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const offered = stimuli.filter((item) => item.active && (!draft.for_children || suitableForChildren(item)));
  const unsuitableSteps = draft.for_children
    ? draft.steps.filter((step) => { const stimulus = step.stimulus_id ? byId.get(step.stimulus_id) : undefined; return stimulus != null && !suitableForChildren(stimulus); }).length
    : 0;
  // Una imagen eliminada por el docente ya no aparece: hay que quitarla y elegir otra.
  // Un ejercicio de práctica sin ilustración no necesita imagen.
  const missingSteps = stimuliQuery.loading ? 0 : draft.steps.filter((step) => step.stimulus_id != null && !byId.has(step.stimulus_id)).length;
  const practiceProblems = draft.steps.filter((step) => step.kind === "practice" && practiceProblem(step) !== null).length;
  // Un reconocimiento necesita una imagen emocional con su expresión esperada.
  const recognitionProblems = stimuliQuery.loading ? 0 : draft.steps.filter((step) => step.kind === "recognition"
    && (!recognizable(step.stimulus_id ? byId.get(step.stimulus_id) : undefined)
      || step.exposure_seconds < 1 || step.exposure_seconds > MAX_STEP_SECONDS)).length;
  const drawingProblems = draft.steps.filter((step) => step.kind === "drawing"
    && (step.exposure_seconds < 1 || step.exposure_seconds > MAX_STEP_SECONDS)).length;
  const chosen = choice ? byId.get(choice) : undefined;
  // «Haz la misma cara»: la imagen es el modelo y su expresión esperada es la pedida.
  const imitable = recognizable(chosen) && (chosen?.expected_expression ?? "") in practiceTargetNames;
  const ready = draft.for_children !== null && draft.name.trim() !== "" && draft.steps.length > 0 && unsuitableSteps === 0
    && missingSteps === 0 && practiceProblems === 0 && recognitionProblems === 0 && drawingProblems === 0;

  function update(changes: Partial<Draft>) { setDraft((current) => ({ ...current, ...changes })); }
  function updateStep(index: number, changes: Partial<ProtocolStep>) {
    update({ steps: draft.steps.map((step, position) => position === index ? { ...step, ...changes } : step) });
  }
  function move(index: number, offset: number) {
    const steps = [...draft.steps];
    const [step] = steps.splice(index, 1);
    steps.splice(index + offset, 0, step);
    update({ steps });
  }
  function addStep() {
    if (!choice) return;
    update({ steps: [...draft.steps, { stimulus_id: choice, exposure_seconds: 8, capture_after_seconds: 4, record_verbal_response: false, shown_before_analyzer: false }] });
    setChoice("");
  }
  function addRecognition() {
    if (!recognizable(chosen)) return;
    const defaults = accessibleOn(draft.supports) ? ACCESSIBLE_RECOGNITION : DEFAULT_RECOGNITION;
    update({ steps: [...draft.steps, { kind: "recognition", stimulus_id: choice, option_count: defaults.option_count,
      exposure_seconds: defaults.max_seconds, capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false }] });
    setChoice("");
  }
  function addImitation() {
    if (!imitable || !chosen) return;
    update({ steps: [...draft.steps, { kind: "practice", stimulus_id: choice, imitate: true,
      target_expression: chosen.expected_expression, hold_seconds: practiceDefaults.hold_seconds,
      exposure_seconds: accessibleOn(draft.supports) ? Math.min(MAX_STEP_SECONDS, practiceDefaults.max_seconds * ACCESSIBLE_TIME_FACTOR) : practiceDefaults.max_seconds,
      capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false }] });
    setChoice("");
  }
  function addPractice() {
    update({ steps: [...draft.steps, { kind: "practice", stimulus_id: null, target_expression: "happiness",
      hold_seconds: practiceDefaults.hold_seconds,
      exposure_seconds: accessibleOn(draft.supports) ? Math.min(MAX_STEP_SECONDS, practiceDefaults.max_seconds * ACCESSIBLE_TIME_FACTOR) : practiceDefaults.max_seconds,
      capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false }] });
  }
  function addDrawing() {
    // Sin imagen ni opciones: la persona dibuja y señala la emoción que quiso representar.
    update({ steps: [...draft.steps, { kind: "drawing", stimulus_id: null,
      exposure_seconds: accessibleOn(draft.supports) ? MAX_STEP_SECONDS : DRAWING_SECONDS,
      capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false }] });
  }
  function openEditor(item: Protocol | null) {
    setEditing(item); setChoice(""); setMessage(""); setError(""); setEditorOpen(true);
    setDraft(item ? { name: item.name, description: item.description, for_children: item.for_children,
      supports: item.supports ?? (item.accessible ? { ...noSupports, pictograms: true, large_controls: true, pause: "long" } : noSupports), steps: item.steps,
      pre_questionnaire_id: item.pre_questionnaire_id ?? "", post_questionnaire_id: item.post_questionnaire_id ?? "" } : emptyDraft);
  }
  function close() { setEditing(null); setDraft(emptyDraft); setChoice(""); setEditorOpen(false); }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready) return;
    setBusy(true); setError(""); setMessage("");
    try {
      const saved = await apiRequest<Protocol>(editing ? `/protocols/${encodeURIComponent(editing.id)}` : "/protocols", {
        method: editing ? "PUT" : "POST", token, body: JSON.stringify({ ...draft, accessible: anySupport(draft.supports), pre_questionnaire_id: draft.pre_questionnaire_id || null,
          post_questionnaire_id: draft.post_questionnaire_id || null }),
      });
      setMessage(editing && saved.id !== editing.id
        ? `Se creó la versión ${saved.version}: la anterior ya se usó en una sesión y se conserva sin cambios.`
        : editing ? "Protocolo actualizado." : "Protocolo guardado. Úsalo cuando quieras desde el Analizador.");
      close();
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo guardar el protocolo."); }
    finally { setBusy(false); }
  }

  /** Copiar una plantilla del docente (o duplicar uno propio) y compartir uno propio con el grupo. */
  async function run(action: () => Promise<string>) {
    setBusy(true); setError(""); setMessage("");
    try { setMessage(await action()); await query.reload(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo completar la acción."); }
    finally { setBusy(false); }
  }

  async function addValidation() {
    setBusy(true); setError(""); setMessage("");
    try {
      await apiRequest("/practice-validation/protocol", { method: "POST", token });
      setMessage("Se agregó el protocolo «Validación con adultos». Úsalo desde el Analizador.");
      await Promise.all([query.reload(), validationQuery.reload()]);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo agregar el protocolo."); }
    finally { setBusy(false); }
  }

  function questionnaireSelect(moment: Moment) {
    const field = moment === "pre" ? "pre_questionnaire_id" : "post_questionnaire_id";
    return <div className="inline-actions">
      <label>{moment === "pre" ? "Cuestionario previo (opcional)" : "Cuestionario posterior (opcional)"}
        <select value={draft[field]} onChange={(event) => update({ [field]: event.target.value })}>
          <option value="">Sin cuestionario</option>
          {questionnaires.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
        </select></label>
      <Button size="sm" variant="ghost" onClick={() => setQuestionnaireFor(moment)}>Crear cuestionario</Button>
    </div>;
  }

  return <section>
    <PageHeader title="Protocolos"
      description="Un protocolo es una receta guardada: qué aplicar en una sesión, para usarla cuando quieras."
      actions={<>
        <Button disabled={busy} onClick={() => { void run(async () => {
          await apiRequest("/protocols/starter", { method: "POST", token });
          return "Se agregó «Emociones básicas 4 a 6 años» a tus protocolos. Puedes editarla y usarla en el Analizador.";
        }); }}>Usar la plantilla inicial</Button>
        <Button variant="primary" onClick={() => openEditor(null)}>Nuevo protocolo</Button>
      </>} />
    <p className="muted">La plantilla inicial «Emociones básicas 4 a 6 años» es para niños y en modo accesible: seis dibujos
      del banco inicial, cada uno con dos opciones para elegir qué emoción es.</p>
    <NoticeList />
    {message && <Callout variant="success">{message}</Callout>}
    {error && !editorOpen && <Callout variant="error">{error}</Callout>}
    {validation?.available && !validation.protocol_id && <Callout variant="info" role="note">
      <p>Cuenta de voluntario: puedes agregar el protocolo «Validación con adultos», con un ejercicio por cada expresión.
        Sirve para medir si el modelo reconoce expresiones producidas a propósito. No se guardan imágenes.</p>
      <Button disabled={busy} onClick={() => { void addValidation(); }}>Agregar «Validación con adultos»</Button>
    </Callout>}

    <Modal open={editorOpen} title={editing ? `Editar «${editing.name}»` : "Nuevo protocolo"} onClose={close} busy={busy}
      footer={<>
        <Button disabled={busy} onClick={close}>Cancelar</Button>
        <Button variant="primary" type="submit" form="protocol-editor" disabled={busy || !ready}>
          {busy ? "Guardando…" : editing ? "Guardar cambios" : "Guardar protocolo"}
        </Button>
      </>}>
    <form id="protocol-editor" className="form-stack" onSubmit={(event) => { void submit(event); }}>
      {error && <Callout variant="error">{error}</Callout>}
      {editing?.used && <Callout variant="info" role="note">
        Este protocolo ya se usó en una sesión: al guardar se crea la versión {editing.version + 1} y la actual se conserva.
      </Callout>}
      <fieldset className="audience-choice">
        <legend>¿Para adultos o para niños?</legend>
        <label className={`audience-option${draft.for_children === false ? " is-selected" : ""}`}>
          <input type="radio" name="protocol-audience" checked={draft.for_children === false} required
            onChange={() => update({ for_children: false })} />
          <strong>Para adultos</strong>
          <span>Para sesiones propias o con una persona adulta.</span>
        </label>
        <label className={`audience-option${draft.for_children === true ? " is-selected" : ""}`}>
          <input type="radio" name="protocol-audience" checked={draft.for_children === true}
            onChange={() => update({ for_children: true })} />
          <strong>Para niños</strong>
          <span>Solo imágenes «Para niños» aprobadas.</span>
        </label>
      </fieldset>

      {draft.for_children !== null && <>
        <Checkbox checked={accessibleOn(draft.supports)} onChange={(event) => update({ supports: event.target.checked
          ? { ...draft.supports, pictograms: true, large_controls: true, pause: "long" }
          : { ...draft.supports, pictograms: false, large_controls: false, pause: "normal" } })}>
          Modo accesible
        </Checkbox>
        <p className="muted">Para quienes se saturan con facilidad: pictogramas junto a cada emoción, botones grandes, nada que se mueva y pausas más largas. Los pasos nuevos proponen menos opciones y más tiempo.</p>
        <fieldset className="form-stack">
          <legend>Apoyos uno por uno</legend>
          <Checkbox checked={draft.supports.pictograms} onChange={(event) => update({ supports: { ...draft.supports, pictograms: event.target.checked } })}>
            Pictogramas junto a cada emoción
          </Checkbox>
          <Checkbox checked={draft.supports.large_controls} onChange={(event) => update({ supports: { ...draft.supports, large_controls: event.target.checked } })}>
            Botones y letra grandes, sin animaciones
          </Checkbox>
          <Checkbox checked={draft.supports.read_aloud} onChange={(event) => update({ supports: { ...draft.supports, read_aloud: event.target.checked } })}>
            Leer la consigna en voz alta al empezar cada paso
          </Checkbox>
          <Checkbox checked={draft.supports.no_time_limit} onChange={(event) => update({ supports: { ...draft.supports, no_time_limit: event.target.checked } })}>
            Sin límite de tiempo en «¿Qué emoción es?» y en la práctica
          </Checkbox>
          <label>Pausa tras cada paso<select value={draft.supports.pause}
            onChange={(event) => update({ supports: { ...draft.supports, pause: event.target.value as PauseMode } })}>
            {(Object.keys(pauseNames) as PauseMode[]).map((key) => <option key={key} value={key}>{pauseNames[key]}</option>)}
          </select></label>
          <p className="muted">Sin límite de tiempo, el paso termina al responder, al lograrlo o cuando lo saltas. Cambian el ritmo y la pantalla, no lo que se registra.</p>
        </fieldset>
        <label>Nombre<input value={draft.name} maxLength={120} required onChange={(event) => update({ name: event.target.value })} /></label>
        <label>Descripción (opcional)<textarea rows={2} maxLength={2000} value={draft.description}
          onChange={(event) => update({ description: event.target.value })} /></label>
        {questionnaireSelect("pre")}
        <p className="muted">El previo se responde antes de la calibración; el posterior, al terminar. Se aplica la versión vigente de cada cuestionario.</p>

        <h3>Pasos en orden</h3>
        {draft.steps.length === 0 && <p className="muted">Agrega al menos una imagen o un ejercicio de práctica.</p>}
        <ol className="card-list">{draft.steps.map((step, index) => {
          const stimulus = step.stimulus_id ? byId.get(step.stimulus_id) : undefined;
          const order = <>
            <Button size="sm" disabled={index === 0} onClick={() => move(index, -1)}>Subir</Button>
            <Button size="sm" disabled={index === draft.steps.length - 1} onClick={() => move(index, 1)}>Bajar</Button>
            <Button size="sm" variant="ghost" onClick={() => update({ steps: draft.steps.filter((_, position) => position !== index) })}>Quitar</Button>
          </>;
          if (step.kind === "practice" && step.imitate) {
            const problem = practiceProblem(step);
            const unsuitableModel = draft.for_children && stimulus != null && !suitableForChildren(stimulus);
            const modelName = stimulus?.expected_expression ? practiceTargetNames[stimulus.expected_expression] : null;
            return <li key={`imitation-${index}`} className="row-card protocol-step">
              <div>
                <strong>{index + 1}. Haz la misma cara: {stimulus?.title ?? "Imagen no disponible"}</strong>
                {modelName && <span>La persona ve la imagen y hace la misma cara. Expresión pedida: {modelName} (la expresión esperada de la imagen).</span>}
                {problem && <span role="alert">{problem}.</span>}
                {unsuitableModel && <span>No se puede usar con niños: quítala o elige una «Para niños».</span>}
                {!stimulus && !stimuliQuery.loading && <span>Necesita una imagen: quítala y elige otra.</span>}
              </div>
              <div className="inline-actions">
                <label>Sostener (s)<input type="number" min={1} max={MAX_HOLD_SECONDS} value={step.hold_seconds ?? ""}
                  onChange={(event) => updateStep(index, { hold_seconds: Number(event.target.value) })} /></label>
                <label>Tiempo máximo (s)<input type="number" min={2} max={MAX_STEP_SECONDS} value={step.exposure_seconds}
                  onChange={(event) => updateStep(index, { exposure_seconds: Number(event.target.value) })} /></label>
                {order}
              </div>
            </li>;
          }
          if (step.kind === "practice") {
            const problem = practiceProblem(step);
            const unsuitableIllustration = draft.for_children && stimulus != null && !suitableForChildren(stimulus);
            return <li key={`practice-${index}`} className="row-card protocol-step">
              <div>
                <strong>{index + 1}. Ejercicio de práctica: {practiceTargetNames[step.target_expression ?? ""] ?? "elige la expresión"}</strong>
                <span>Se pide la expresión y se espera que la persona la sostenga.</span>
                {problem && <span role="alert">{problem}.</span>}
                {unsuitableIllustration && <span>La ilustración no se puede usar con niños: quítala o elige una «Para niños».</span>}
                {step.stimulus_id && !stimulus && !stimuliQuery.loading && <span>La ilustración ya no está disponible: elige otra o quítala.</span>}
              </div>
              <div className="inline-actions">
                <label>Expresión pedida<select value={step.target_expression ?? ""}
                  onChange={(event) => updateStep(index, { target_expression: event.target.value })}>
                  {Object.entries(practiceTargetNames).map(([key, name]) => <option key={key} value={key}>{name}</option>)}
                </select></label>
                <label>Sostener (s)<input type="number" min={1} max={MAX_HOLD_SECONDS} value={step.hold_seconds ?? ""}
                  onChange={(event) => updateStep(index, { hold_seconds: Number(event.target.value) })} /></label>
                <label>Tiempo máximo (s)<input type="number" min={2} max={MAX_STEP_SECONDS} value={step.exposure_seconds}
                  onChange={(event) => updateStep(index, { exposure_seconds: Number(event.target.value) })} /></label>
                <label>Ilustración (opcional)<select value={step.stimulus_id ?? ""}
                  onChange={(event) => updateStep(index, { stimulus_id: event.target.value || null })}>
                  <option value="">Sin ilustración</option>
                  {step.stimulus_id && !offered.some((item) => item.id === step.stimulus_id) &&
                    <option value={step.stimulus_id}>{stimulus?.title ?? "Imagen no disponible"}</option>}
                  {offered.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
                </select></label>
                {order}
              </div>
            </li>;
          }
          if (step.kind === "drawing") {
            return <li key={`drawing-${index}`} className="row-card protocol-step">
              <div>
                <strong>{index + 1}. Dibujo: una cara con una emoción</strong>
                <span>La persona dibuja en su pantalla y después señala qué emoción quiso dibujar. El dibujo no se envía ni se guarda.</span>
              </div>
              <div className="inline-actions">
                <label>Tiempo para dibujar (s)<input type="number" min={1} max={MAX_STEP_SECONDS} value={step.exposure_seconds}
                  onChange={(event) => updateStep(index, { exposure_seconds: Number(event.target.value) })} /></label>
                {order}
              </div>
            </li>;
          }
          const unsuitable = draft.for_children && stimulus != null && !suitableForChildren(stimulus);
          if (step.kind === "recognition") {
            const answerName = stimulus?.expected_expression ? practiceTargetNames[stimulus.expected_expression] : null;
            return <li key={`recognition-${index}`} className="row-card protocol-step">
              <div>
                <strong>{index + 1}. {step.situation ? "Situación" : "¿Qué emoción es?"} {stimulus?.title ?? "Imagen no disponible"}</strong>
                {answerName && <span>La persona elige entre varias emociones. Respuesta: {answerName} (la expresión esperada de la imagen).</span>}
                {stimulus && !recognizable(stimulus) && <span role="alert">Esta imagen no indica una expresión esperada: elige una imagen emocional que la tenga.</span>}
                {unsuitable && <span>No se puede usar con niños: quítala o elige una «Para niños».</span>}
                {!stimulus && !stimuliQuery.loading && <span>Necesita una imagen: quítala y elige otra.</span>}
                {/* Con una historia, se pregunta por la cara de la imagen: una situación no tiene una única emoción posible. */}
                <label>Situación (opcional)<textarea rows={2} maxLength={MAX_SITUATION_CHARS} value={step.situation ?? ""}
                  placeholder="A Lucía se le cayó su helado al piso."
                  onChange={(event) => updateStep(index, { situation: event.target.value || null })} /></label>
                <span className="muted">Con una situación, la pregunta es «¿Qué emoción muestra la cara?» y al final se aclara que cada persona puede sentir algo distinto. Usa nombres inventados.</span>
              </div>
              <div className="inline-actions">
                <label>Opciones<select value={step.option_count ?? DEFAULT_RECOGNITION.option_count}
                  onChange={(event) => updateStep(index, { option_count: Number(event.target.value) })}>
                  {RECOGNITION_OPTION_COUNTS.map((count) => <option key={count} value={count}>{count}</option>)}
                </select></label>
                <label>Tiempo para responder (s)<input type="number" min={1} max={MAX_STEP_SECONDS} value={step.exposure_seconds}
                  onChange={(event) => updateStep(index, { exposure_seconds: Number(event.target.value) })} /></label>
                {order}
              </div>
            </li>;
          }
          return <li key={`${step.stimulus_id}-${index}`} className="row-card protocol-step">
            <div>
              <strong>{index + 1}. {stimulus?.title ?? "Imagen no disponible"}</strong>
              {stimulus && <span>{stimulusSummary(stimulus)}</span>}
              {unsuitable && <span>No se puede usar con niños: quítala o elige una «Para niños».</span>}
              {!stimulus && !stimuliQuery.loading && <span>Necesita una imagen: quítala y elige otra.</span>}
            </div>
            <div className="inline-actions">
              <label>Segundos en pantalla<input type="number" min={1} max={120} value={step.exposure_seconds}
                onChange={(event) => updateStep(index, { exposure_seconds: Number(event.target.value) })} /></label>
              <label>Captura a los (s)<input type="number" min={0} max={step.exposure_seconds} value={step.capture_after_seconds}
                onChange={(event) => updateStep(index, { capture_after_seconds: Number(event.target.value) })} /></label>
              {stimulus?.kind === "abstract" && <Checkbox checked={step.record_verbal_response}
                onChange={(event) => updateStep(index, { record_verbal_response: event.target.checked })}>Registrar lo que dice ver</Checkbox>}
              {stimulus?.kind === "abstract" && <Checkbox checked={step.shown_before_analyzer}
                onChange={(event) => updateStep(index, { shown_before_analyzer: event.target.checked })}>Mostrar antes del analizador (sin capturas)</Checkbox>}
              {order}
            </div>
          </li>;
        })}</ol>
        {offered.length > 0 ? <div className="inline-actions">
          <label>Imagen<select value={choice} onChange={(event) => setChoice(event.target.value)}>
            <option value="">Elige una imagen</option>
            {offered.map((item) => <option key={item.id} value={item.id}>{item.title} — {stimulusSummary(item)}</option>)}
          </select></label>
          <Button disabled={!choice} onClick={addStep}>Agregar al protocolo</Button>
          <Button disabled={!recognizable(chosen)} onClick={addRecognition}>Agregar como «¿Qué emoción es?»</Button>
          <Button disabled={!imitable} onClick={addImitation}>Agregar como «Haz la misma cara»</Button>
        </div> : !stimuliQuery.loading && <div className="empty-state">
          <p>{draft.for_children ? "No hay imágenes «Para niños» aprobadas." : "No hay imágenes disponibles."}
            {isDocente ? " Sube una en Estímulos." : " Sube las tuyas en Imágenes: se usan cuando tu docente las aprueba."}</p>
          <div className="inline-actions"><ButtonLink variant="secondary" to={isDocente ? paths.stimuli : paths.images}>
            {isDocente ? "Ir a Estímulos" : "Ir a Imágenes"}</ButtonLink></div>
        </div>}
        <div className="inline-actions">
          <Button onClick={addPractice}>Agregar ejercicio de práctica</Button>
          <Button onClick={addDrawing}>Agregar dibujo</Button>
        </div>
        <p className="muted">En un ejercicio de práctica se pide una expresión (por ejemplo, «Muestra alegría») y la persona ve
          una señal simple que crece al acercarse. Se registra si la logró y en cuánto tiempo; no evalúa a nadie.</p>
        <p className="muted">En «¿Qué emoción es?» se muestra una imagen emocional y la persona elige entre varias emociones;
          después lee el nombre de la emoción de la imagen. Las opciones se eligen solas. Se registra qué eligió; no evalúa a nadie.</p>
        <p className="muted">En «Haz la misma cara» la imagen es un modelo: la persona la ve y hace la misma cara, con la misma
          señal simple de la práctica. La expresión pedida es la de la imagen. Se registra si la logró; no evalúa a nadie.</p>
        <p className="muted">En un dibujo la persona dibuja una cara en su pantalla y después señala qué emoción quiso
          representar. El dibujo se queda en su pantalla y se borra al terminar el paso: solo se registra la emoción que
          señaló. EMOtv no mira ni interpreta el dibujo.</p>

        {questionnaireSelect("post")}
      </>}
    </form>
    </Modal>

    <QuestionnaireEditor open={questionnaireFor !== null} onClose={() => setQuestionnaireFor(null)}
      onSaved={(saved) => {
        update(questionnaireFor === "post" ? { post_questionnaire_id: saved.id } : { pre_questionnaire_id: saved.id });
        setQuestionnaireFor(null);
        void questionnairesQuery.reload();
      }} />

    <PageState {...query} empty={!query.loading && !query.error && protocols.length === 0}
      emptyMessage="Todavía no tienes protocolos. Sin protocolo también puedes analizar en el Analizador."
      emptyAction={<Button variant="primary" onClick={() => openEditor(null)}>Nuevo protocolo</Button>} onRetry={query.reload} />
    {protocols.length > 0 && <ul className="card-list">{protocols.map((item) => <li key={item.id} className="card row-card">
      <div>
        <strong>{item.name}</strong>
        <span>Versión {item.version} · {protocolStepParts(item.steps).join(" · ")}
          {isDocente && !item.owned_by_me ? " · De un usuario de tu grupo" : ""}</span>
        <span className="inline-actions">
          {item.for_children ? <StatusChip tone="progress">Para niños</StatusChip> : <StatusChip tone="neutral">Para adultos</StatusChip>}
          {item.accessible && <StatusChip tone="neutral">{item.supports && !accessibleOn(item.supports) ? "Con apoyos" : "Modo accesible"}</StatusChip>}
          {!item.owned_by_me && item.shared_with_group && <StatusChip tone="neutral">Plantilla de tu docente</StatusChip>}
          {item.owned_by_me && item.shared_with_group && <StatusChip tone="progress">Compartido con tu grupo</StatusChip>}
          {item.used && <StatusChip tone="neutral">Usado en sesiones</StatusChip>}
          {item.needs_image && <StatusChip tone="error">Necesita una imagen</StatusChip>}
        </span>
      </div>
      <div className="inline-actions">
        {item.owned_by_me && !item.needs_image && <ButtonLink variant="secondary" to={paths.analysisWithProtocol(item.id)}>Usar en el Analizador</ButtonLink>}
        {item.owned_by_me && <Button onClick={() => openEditor(item)}>Editar</Button>}
        {(item.owned_by_me || item.shared_with_group) && <Button variant={item.owned_by_me ? "secondary" : "primary"} disabled={busy}
          onClick={() => { void run(async () => {
            await apiRequest(`/protocols/${encodeURIComponent(item.id)}/copy`, { method: "POST", token });
            return `Se agregó una copia de «${item.name}» a tus protocolos. Puedes editarla y usarla en el Analizador.`;
          }); }}>{item.owned_by_me ? "Duplicar" : "Copiar y modificar"}</Button>}
        {isDocente && item.owned_by_me && <Button disabled={busy} onClick={() => { void run(async () => {
          await apiRequest(`/protocols/${encodeURIComponent(item.id)}/share`, { method: "PUT", token, body: JSON.stringify({ shared: !item.shared_with_group }) });
          return item.shared_with_group ? "Tu grupo ya no ve este protocolo como plantilla." : "Tu grupo puede copiar este protocolo como plantilla.";
        }); }}>{item.shared_with_group ? "Dejar de compartir" : "Compartir con mi grupo"}</Button>}
      </div>
    </li>)}</ul>}
  </section>;
}
