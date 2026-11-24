import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { apiRequest } from "../api/http";
import type { GameType, PauseMode, Protocol, ProtocolStep, ProtocolSupports, Questionnaire, Stimulus } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button, ButtonLink } from "../components/Button";
import { Callout } from "../components/Callout";
import { ActionsMenu } from "../components/ActionsMenu";
import type { ActionsMenuItem } from "../components/ActionsMenu";
import { Checkbox } from "../components/Checkbox";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { Modal } from "../components/Modal";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip } from "../components/StatusChip";
import { QuestionnaireEditor } from "../questionnaires/QuestionnaireEditor";
import { paths } from "../routes/paths";
import { ACCESSIBLE_RECOGNITION, ACCESSIBLE_TIME_FACTOR, DEFAULT_GAME, DEFAULT_PRACTICE, DRAWING_SECONDS, MAX_GAME_ROUNDS, MIN_GAME_ROUNDS, DEFAULT_RECOGNITION, MAX_HOLD_SECONDS, MAX_SITUATION_CHARS, MAX_STEP_SECONDS, cameraTargets, isCameraTarget, practiceProblem, practiceTargetNames, protocolStepLines, protocolStepParts,
  RECOGNITION_OPTION_COUNTS, recognizable, stimulusSummary } from "../stimuli/labels";
import { NoticeList } from "../components/NoticeList";
import { toast } from "../components/Toaster";
import { CAMERA_GAME, cameraGameSteps, itemRange, moveItem, removeItem, replaceItem } from "../stimuli/cameraGame";

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

/** Tipos de paso que se pueden agregar. Los que llevan imagen piden elegirla después de tocar la tarjeta. */
type StepChoice = "matching" | "similar" | "recognition" | "drawing" | "camera" | "rated" | "practice" | "imitation" | "stimulus";
type ImageChoice = Extract<StepChoice, "recognition" | "imitation" | "rated" | "stimulus">;
const stepCatalog: { group: string; hint: string; items: { key: StepChoice; title: string; text: string; image?: boolean }[] }[] = [
  { group: "Juegos", hint: "Sin cámara: se juegan con botones.", items: [
    { key: "matching", title: "Juego: empareja la emoción", text: "Relaciona cada imagen con el nombre de su emoción." },
    { key: "similar", title: "Juego: busca la misma emoción", text: "Ve una cara y elige otra que muestre la misma emoción." },
  ] },
  { group: "Reconocer y dibujar", hint: "Sin cámara.", items: [
    { key: "recognition", title: "¿Qué emoción es?", text: "Ve una imagen y elige qué emoción muestra.", image: true },
    { key: "drawing", title: "Dibujo", text: "Dibuja una cara y pulsa «Terminé». No se pregunta qué emoción quiso dibujar y el dibujo no se guarda." },
  ] },
  { group: "Expresión con la cámara", hint: "EMOtv estima la expresión facial; no evalúa a nadie.", items: [
    { key: "camera", title: "Juego con cámara: muestra la emoción", text: "En cada ronda se pide una emoción; una estrella por cada cara lograda. Sin puntos." },
    { key: "rated", title: "Juego: imita la cara", text: "Ve una imagen y hace la misma cara. La cámara estima la expresión y tú la valoras de 1 a 5 estrellas; la persona no ve tu valoración.", image: true },
    { key: "practice", title: "Ejercicio de práctica", text: "Se pide una expresión y una señal simple crece al acercarse." },
    { key: "imitation", title: "Haz la misma cara", text: "Ve una imagen y hace la misma cara.", image: true },
    { key: "stimulus", title: "Mostrar una imagen", text: "Se muestra una imagen mientras se estima la expresión facial.", image: true },
  ] },
];
const imageChoiceTitle: Record<ImageChoice, string> = { recognition: "¿Qué emoción es?", imitation: "Haz la misma cara", rated: "Juego: imita la cara", stimulus: "Mostrar una imagen" };

/** Una ronda del juego sin imagen elegida la completa EMOtv al guardar: no se envía el hueco. */
function withoutEmptyImages(step: ProtocolStep): ProtocolStep {
  return step.game_stimulus_ids ? { ...step, game_stimulus_ids: step.game_stimulus_ids.filter(Boolean) } : step;
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
  // Tipo de paso con imagen que se está agregando: muestra el selector de imagen.
  const [picking, setPicking] = useState<ImageChoice | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  // Protocolo que se mira sin editar y protocolo que se va a eliminar.
  const [preview, setPreview] = useState<Protocol | null>(null);
  const [removing, setRemoving] = useState<Protocol | null>(null);
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
  const drawingProblems = draft.steps.filter((step) => (step.kind === "drawing" || step.kind === "game")
    && (step.exposure_seconds < 1 || step.exposure_seconds > MAX_STEP_SECONDS)).length;
  const chosen = choice ? byId.get(choice) : undefined;
  // Imágenes para una ronda de «Empareja la emoción»: emocionales con su expresión esperada.
  const matchable = offered.filter((item) => recognizable(item));
  // «Haz la misma cara»: la imagen es el modelo y su expresión esperada es la pedida.
  const imitable = recognizable(chosen) && isCameraTarget(chosen?.expected_expression);
  // Imágenes que sirven para el tipo elegido: reconocer e imitar necesitan una expresión esperada.
  const pickable = picking === "stimulus" ? offered : offered.filter((item) => recognizable(item)
    && ((picking !== "imitation" && picking !== "rated") || isCameraTarget(item.expected_expression)));
  const missing = [
    draft.name.trim() === "" && "el nombre",
    draft.for_children === null && "para quién es",
    draft.steps.length === 0 && "al menos un paso",
  ].filter(Boolean) as string[];
  const stepProblems = unsuitableSteps + missingSteps + practiceProblems + recognitionProblems + drawingProblems;
  const ready = draft.for_children !== null && draft.name.trim() !== "" && draft.steps.length > 0 && unsuitableSteps === 0
    && missingSteps === 0 && practiceProblems === 0 && recognitionProblems === 0 && drawingProblems === 0;

  // Al agregar un paso, se muestra en la lista sin tener que buscarlo.
  const stepsRef = useRef<HTMLOListElement>(null);
  const stepCount = useRef(0);
  useEffect(() => {
    if (draft.steps.length > stepCount.current) {
      stepsRef.current?.lastElementChild?.scrollIntoView?.({ block: "nearest", behavior: "smooth" });
    }
    stepCount.current = draft.steps.length;
  }, [draft.steps.length]);

  function update(changes: Partial<Draft>) { setDraft((current) => ({ ...current, ...changes })); }
  function updateStep(index: number, changes: Partial<ProtocolStep>) {
    update({ steps: draft.steps.map((step, position) => position === index ? { ...step, ...changes } : step) });
  }
  // Un juego con cámara se mueve y se quita entero: sus rondas van seguidas.
  function move(index: number, offset: -1 | 1) { update({ steps: moveItem(draft.steps, index, offset) }); }
  function cameraGameSeconds() {
    return accessibleOn(draft.supports) ? Math.min(MAX_STEP_SECONDS, CAMERA_GAME.exposure_seconds * ACCESSIBLE_TIME_FACTOR) : CAMERA_GAME.exposure_seconds;
  }
  function addCameraGame() {
    update({ steps: [...draft.steps, ...cameraGameSteps(CAMERA_GAME.rounds, CAMERA_GAME.hold_seconds, cameraGameSeconds())] });
  }
  function addStep() {
    if (!choice) return;
    update({ steps: [...draft.steps, { stimulus_id: choice, exposure_seconds: 8, capture_after_seconds: 4, record_verbal_response: false, shown_before_analyzer: false }] });
    setChoice(""); setPicking(null);
  }
  function addRecognition() {
    if (!recognizable(chosen)) return;
    const defaults = accessibleOn(draft.supports) ? ACCESSIBLE_RECOGNITION : DEFAULT_RECOGNITION;
    update({ steps: [...draft.steps, { kind: "recognition", stimulus_id: choice, option_count: defaults.option_count,
      exposure_seconds: defaults.max_seconds, capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false }] });
    setChoice(""); setPicking(null);
  }
  function addImitation(rated = false) {
    if (!imitable || !chosen) return;
    update({ steps: [...draft.steps, { kind: "practice", stimulus_id: choice, imitate: true, conductor_rating: rated,
      target_expression: chosen.expected_expression, hold_seconds: practiceDefaults.hold_seconds,
      exposure_seconds: accessibleOn(draft.supports) ? Math.min(MAX_STEP_SECONDS, practiceDefaults.max_seconds * ACCESSIBLE_TIME_FACTOR) : practiceDefaults.max_seconds,
      capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false }] });
    setChoice(""); setPicking(null);
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
  function addGame(gameType: GameType) {
    // Pocas opciones al empezar. Las imágenes las elige el servidor del banco aprobado.
    update({ steps: [...draft.steps, { kind: "game", game_type: gameType, stimulus_id: null,
      rounds: DEFAULT_GAME.rounds, option_count: DEFAULT_GAME.option_count, game_stimulus_ids: [],
      exposure_seconds: accessibleOn(draft.supports)
        ? Math.min(MAX_STEP_SECONDS, DEFAULT_GAME.exposure_seconds * ACCESSIBLE_TIME_FACTOR) : DEFAULT_GAME.exposure_seconds,
      capture_after_seconds: 0, record_verbal_response: false, shown_before_analyzer: false }] });
  }
  function choose(key: StepChoice) {
    setChoice("");
    if (key === "recognition" || key === "imitation" || key === "rated" || key === "stimulus") { setPicking(key); return; }
    setPicking(null);
    if (key === "matching" || key === "similar") addGame(key);
    else if (key === "drawing") addDrawing();
    else if (key === "camera") addCameraGame();
    else addPractice();
  }
  function addPicked() {
    if (picking === "recognition") addRecognition();
    else if (picking === "imitation") addImitation();
    else if (picking === "rated") addImitation(true);
    else addStep();
  }
  function openEditor(item: Protocol | null) {
    setEditing(item); setChoice(""); setPicking(null); setError(""); setEditorOpen(true);
    setDraft(item ? { name: item.name, description: item.description, for_children: item.for_children,
      supports: item.supports ?? (item.accessible ? { ...noSupports, pictograms: true, large_controls: true, pause: "long" } : noSupports), steps: item.steps,
      pre_questionnaire_id: item.pre_questionnaire_id ?? "", post_questionnaire_id: item.post_questionnaire_id ?? "" } : emptyDraft);
  }
  function close() { setEditing(null); setDraft(emptyDraft); setChoice(""); setPicking(null); setEditorOpen(false); }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready) return;
    setBusy(true); setError("");
    try {
      const saved = await apiRequest<Protocol>(editing ? `/protocols/${encodeURIComponent(editing.id)}` : "/protocols", {
        method: editing ? "PUT" : "POST", token, body: JSON.stringify({ ...draft, steps: draft.steps.map(withoutEmptyImages), accessible: anySupport(draft.supports), pre_questionnaire_id: draft.pre_questionnaire_id || null,
          post_questionnaire_id: draft.post_questionnaire_id || null }),
      });
      toast.success(editing && saved.id !== editing.id
        ? `Se creó la versión ${saved.version}: la anterior ya se usó en una sesión y se conserva sin cambios.`
        : editing ? "Protocolo actualizado." : "Protocolo guardado. Úsalo cuando quieras desde el Analizador.");
      close();
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo guardar el protocolo."); }
    finally { setBusy(false); }
  }

  /** Copiar una plantilla del docente (o duplicar uno propio) y compartir uno propio con el grupo. */
  async function run(action: () => Promise<string>) {
    setBusy(true); setError("");
    try { toast.success(await action()); await query.reload(); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo completar la acción."); }
    finally { setBusy(false); }
  }

  function questionnaireTitle(id: string | null) {
    if (!id) return null;
    const found = questionnaires.find((item) => item.id === id);
    return found ? `«${found.title}»` : "un cuestionario";
  }

  async function remove() {
    const item = removing;
    if (!item) return;
    await run(async () => {
      await apiRequest(`/protocols/${encodeURIComponent(item.id)}`, { method: "DELETE", token });
      return `Se eliminó «${item.name}». Las sesiones que lo usaron conservan su registro.`;
    });
    setRemoving(null);
  }

  function actions(item: Protocol): ActionsMenuItem[] {
    const items: ActionsMenuItem[] = [{ label: "Vista previa", onSelect: () => setPreview(item) }];
    if (item.owned_by_me) items.push({ label: "Editar", onSelect: () => openEditor(item) });
    if (item.owned_by_me || item.shared_with_group) items.push({
      label: item.owned_by_me ? "Duplicar" : "Copiar y modificar", disabled: busy,
      onSelect: () => { void run(async () => {
        await apiRequest(`/protocols/${encodeURIComponent(item.id)}/copy`, { method: "POST", token });
        return `Se agregó una copia de «${item.name}» a tus protocolos. Puedes editarla y usarla en el Analizador.`;
      }); },
    });
    if (isDocente && item.owned_by_me) items.push({
      label: item.shared_with_group ? "Dejar de compartir" : "Compartir con mi grupo", disabled: busy,
      onSelect: () => { void run(async () => {
        await apiRequest(`/protocols/${encodeURIComponent(item.id)}/share`, { method: "PUT", token, body: JSON.stringify({ shared: !item.shared_with_group }) });
        return item.shared_with_group ? "Tu grupo ya no ve este protocolo como plantilla." : "Tu grupo puede copiar este protocolo como plantilla.";
      }); },
    });
    if (item.owned_by_me) items.push({ label: "Eliminar", danger: true, disabled: busy, onSelect: () => setRemoving(item) });
    return items;
  }

  async function addValidation() {
    setBusy(true); setError("");
    try {
      await apiRequest("/practice-validation/protocol", { method: "POST", token });
      toast.success("Se agregó el protocolo «Validación con adultos». Úsalo desde el Analizador.");
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
    {error && !editorOpen && <Callout variant="error">{error}</Callout>}
    {validation?.available && !validation.protocol_id && <Callout variant="info" role="note">
      <p>Cuenta de voluntario: puedes agregar el protocolo «Validación con adultos», con un ejercicio por cada expresión.
        Sirve para medir si el modelo reconoce expresiones producidas a propósito. No se guardan imágenes.</p>
      <Button disabled={busy} onClick={() => { void addValidation(); }}>Agregar «Validación con adultos»</Button>
    </Callout>}

    <Modal open={editorOpen} title={editing ? `Editar «${editing.name}»` : "Nuevo protocolo"} onClose={close} busy={busy} wide
      footer={<>
        <Button disabled={busy} onClick={close}>Cancelar</Button>
        <Button variant="primary" type="submit" form="protocol-editor" disabled={busy || !ready}>
          {busy ? "Guardando…" : editing ? "Guardar cambios" : "Guardar protocolo"}
        </Button>
      </>}>
    <form id="protocol-editor" className="form-stack protocol-editor" onSubmit={(event) => { void submit(event); }}>
      {error && <Callout variant="error">{error}</Callout>}
      {editing?.used && <Callout variant="info" role="note">
        Este protocolo ya se usó en una sesión: al guardar se crea la versión {editing.version + 1} y la actual se conserva.
      </Callout>}

      <section className="protocol-section" aria-labelledby="protocol-data-title">
        <h3 id="protocol-data-title"><span className="protocol-section-number" aria-hidden="true">1</span>Datos</h3>
        <label>Nombre<input value={draft.name} maxLength={120} required onChange={(event) => update({ name: event.target.value })} /></label>
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
        <label>Descripción (opcional)<textarea rows={2} maxLength={2000} value={draft.description}
          onChange={(event) => update({ description: event.target.value })} /></label>
      </section>

      <section className="protocol-section" aria-labelledby="protocol-supports-title">
        <h3 id="protocol-supports-title"><span className="protocol-section-number" aria-hidden="true">2</span>Apoyos para la persona (opcional)</h3>
        <Checkbox checked={accessibleOn(draft.supports)} onChange={(event) => update({ supports: event.target.checked
          ? { ...draft.supports, pictograms: true, large_controls: true, pause: "long" }
          : { ...draft.supports, pictograms: false, large_controls: false, pause: "normal" } })}>
          Modo accesible
        </Checkbox>
        <p className="muted">Para quienes se saturan con facilidad: pictogramas junto a cada emoción, botones grandes, nada que se mueva y pausas más largas. Los pasos nuevos proponen menos opciones y más tiempo.</p>
        <details className="protocol-details" open={anySupport(draft.supports) && !accessibleOn(draft.supports)}>
          <summary>Elegir los apoyos uno por uno</summary>
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
        </details>
      </section>

      <section className="protocol-section" aria-labelledby="protocol-flow-title">
        <h3 id="protocol-flow-title"><span className="protocol-section-number" aria-hidden="true">3</span>Qué se aplica en la sesión</h3>
        <p className="muted">La sesión sigue este orden, de arriba abajo.</p>
        <ol className="protocol-flow">
          <li className="protocol-moment">
            <h4>Antes de empezar</h4>
            {questionnaireSelect("pre")}
            <p className="muted">Se responde antes de los pasos. Se aplica la versión vigente del cuestionario.</p>
          </li>
          <li className="protocol-moment">
            <h4>Pasos{draft.steps.length > 0 ? ` (${draft.steps.length})` : ""}</h4>
            <div className="protocol-steps-layout">
            <div className="protocol-steps-column">
            {draft.steps.length === 0 && <p className="muted">Todavía no hay pasos. Elige al menos uno en «Agregar un paso».</p>}
            <ol ref={stepsRef} className="card-list protocol-steps">{draft.steps.map((step, index) => {
              const stimulus = step.stimulus_id ? byId.get(step.stimulus_id) : undefined;
              const [itemStart, itemEnd] = itemRange(draft.steps, index);
              // Arriba a la derecha de cada paso: subir, bajar y quitar, sin desplazarse.
              const order = <span className="step-order" role="group" aria-label={`Orden del paso ${index + 1}`}>
                <button type="button" className="step-order-button" aria-label={`Subir el paso ${index + 1}`} title="Subir"
                  disabled={itemStart === 0} onClick={() => move(index, -1)}>
                  <svg aria-hidden="true" focusable="false" viewBox="0 0 20 20" fill="none"><path d="m5 12 5-5 5 5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </button>
                <button type="button" className="step-order-button" aria-label={`Bajar el paso ${index + 1}`} title="Bajar"
                  disabled={itemEnd >= draft.steps.length} onClick={() => move(index, 1)}>
                  <svg aria-hidden="true" focusable="false" viewBox="0 0 20 20" fill="none"><path d="m5 8 5 5 5-5" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /></svg>
                </button>
                <button type="button" className="step-order-button step-order-remove" aria-label={`Quitar el paso ${index + 1}`} title="Quitar"
                  onClick={() => update({ steps: removeItem(draft.steps, index) })}>
                  <svg aria-hidden="true" focusable="false" viewBox="0 0 20 20" fill="none"><path d="m6 6 8 8M14 6l-8 8" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" /></svg>
                </button>
              </span>;
              if (step.game_round) {
                // Las rondas de un juego con cámara se muestran como un solo paso, en la primera.
                if (itemStart !== index) return null;
                const block = draft.steps.slice(itemStart, itemEnd);
                const hold = step.hold_seconds ?? CAMERA_GAME.hold_seconds;
                const updateBlock = (changes: Partial<ProtocolStep>) => update({ steps: replaceItem(draft.steps, index,
                  block.map((round) => ({ ...round, ...changes }))) });
                const problem = block.map(practiceProblem).find((item) => item !== null);
                return <li key={`camera-game-${index}`} className="row-card protocol-step">
                  <div>
                    <strong>{index + 1}–{itemEnd}. Juego con cámara: muestra la emoción</strong>
                    <span>En cada ronda se pide una emoción y una barra crece al acercarse. Si la sostiene, gana una estrella; al final se ve «Lograste X de {block.length} caras». Sin puntos.</span>
                    <span className="muted">Emociones: {block.map((round) => practiceTargetNames[round.target_expression ?? ""] ?? "—").join(", ")}.</span>
                    {problem && <span role="alert">{problem}.</span>}
                  </div>
                  <div className="inline-actions">
                    <label>Rondas<select value={block.length} onChange={(event) => update({ steps: replaceItem(draft.steps, index,
                      cameraGameSteps(Number(event.target.value), hold, step.exposure_seconds)) })}>
                      {Array.from({ length: MAX_GAME_ROUNDS - MIN_GAME_ROUNDS + 1 }, (_, offset) => MIN_GAME_ROUNDS + offset)
                        .map((count) => <option key={count} value={count}>{count}</option>)}
                    </select></label>
                    <label>Sostener (s)<input type="number" min={1} max={MAX_HOLD_SECONDS} value={hold}
                      onChange={(event) => updateBlock({ hold_seconds: Number(event.target.value) })} /></label>
                    <label>Tiempo por ronda (s)<input type="number" min={2} max={MAX_STEP_SECONDS} value={step.exposure_seconds}
                      onChange={(event) => updateBlock({ exposure_seconds: Number(event.target.value) })} /></label>
                    <Button size="sm" onClick={() => update({ steps: replaceItem(draft.steps, index,
                      cameraGameSteps(block.length, hold, step.exposure_seconds)) })}>Otras emociones</Button>
                    {order}
                  </div>
                </li>;
              }
              if (step.kind === "practice" && step.imitate) {
                const problem = practiceProblem(step);
                const unsuitableModel = draft.for_children && stimulus != null && !suitableForChildren(stimulus);
                const modelName = stimulus?.expected_expression ? practiceTargetNames[stimulus.expected_expression] : null;
                return <li key={`imitation-${index}`} className="row-card protocol-step">
                  <div>
                    <strong>{index + 1}. {step.conductor_rating ? "Juego: imita la cara" : "Haz la misma cara"}: {stimulus?.title ?? "Imagen no disponible"}</strong>
                    {modelName && <span>La persona ve la imagen y hace la misma cara. Expresión pedida: {modelName} (la expresión esperada de la imagen).</span>}
                    {step.conductor_rating && <span className="muted">Al terminar, tú la valoras de 1 a 5 estrellas y el paso espera tu valoración. La persona no la ve; EMOtv no la calcula ni la suma.</span>}
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
                      {cameraTargets.map((key) => <option key={key} value={key}>{practiceTargetNames[key]}</option>)}
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
                    <strong>{index + 1}. Dibujo: {stimulus ? `la emoción que siente al ver «${stimulus.title}»` : "una cara con una emoción"}</strong>
                    <span>{stimulus
                      ? "La persona mira la imagen, dibuja una cara con la emoción que siente y pulsa «Terminé»."
                      : "La persona dibuja una cara en su pantalla y pulsa «Terminé»."} El dibujo no se envía ni se guarda, y EMOtv no lo compara con la imagen.</span>
                    {step.stimulus_id && !stimulus && !stimuliQuery.loading && <span>La imagen ya no está disponible: elige otra o quítala.</span>}
                    {draft.for_children && stimulus != null && !suitableForChildren(stimulus) && <span>La imagen no se puede usar con niños: quítala o elige una «Para niños».</span>}
                  </div>
                  <div className="inline-actions">
                    <label>Imagen para mirar (opcional)<select value={step.stimulus_id ?? ""}
                      onChange={(event) => updateStep(index, { stimulus_id: event.target.value || null })}>
                      <option value="">Sin imagen</option>
                      {step.stimulus_id && !offered.some((item) => item.id === step.stimulus_id) &&
                        <option value={step.stimulus_id}>{stimulus?.title ?? "Imagen no disponible"}</option>}
                      {offered.map((item) => <option key={item.id} value={item.id}>{item.title}</option>)}
                    </select></label>
                    <label>Tiempo para dibujar (s)<input type="number" min={1} max={MAX_STEP_SECONDS} value={step.exposure_seconds}
                      onChange={(event) => updateStep(index, { exposure_seconds: Number(event.target.value) })} /></label>
                    {order}
                  </div>
                </li>;
              }
              if (step.kind === "game") {
                const rounds = step.rounds ?? DEFAULT_GAME.rounds;
                const similar = step.game_type === "similar";
                const children = draft.for_children ? " «Para niños»" : "";
                return <li key={`game-${index}`} className="row-card protocol-step">
                  <div>
                    <strong>{index + 1}. Juego: {similar ? "busca la misma emoción" : "empareja la emoción"}</strong>
                    <span>{similar
                      ? "En cada ronda la persona ve una cara y elige, entre otras caras, la que muestra la misma emoción, con botones."
                      : "En cada ronda la persona relaciona una imagen con el nombre de su emoción, con botones."} Puede pedir ayuda; si no la encuentra, se le muestra con su explicación. Sin puntaje.</span>
                    <span className="muted">{similar
                      ? `EMOtv elige las imágenes emocionales aprobadas${children} al guardar. En cada ronda, la pareja es otra imagen de la misma emoción que se ve distinta (nunca la misma imagen repetida), y las demás caras son de otras emociones y se parecen más a la de arriba: así se elige por la emoción y no por el parecido. Necesita al menos dos imágenes distintas por emoción.`
                      : `Elige la imagen de cada ronda, o deja «La elige EMOtv» y se completa al guardar con una imagen emocional aprobada${children}. Puedes usar las imágenes que subiste y aprobó tu docente; las fotografías de personas las agrega el docente.`}</span>
                    {!similar && <div className="inline-actions game-round-images">{Array.from({ length: rounds }, (_, round) => {
                      const ids = step.game_stimulus_ids ?? [];
                      const current = ids[round] ?? "";
                      const known = current ? byId.get(current) : undefined;
                      return <label key={round}>Imagen de la ronda {round + 1}<select value={current} onChange={(event) => {
                        const next = Array.from({ length: rounds }, (_, position) => ids[position] ?? "");
                        next[round] = event.target.value;
                        updateStep(index, { game_stimulus_ids: next });
                      }}>
                        <option value="">La elige EMOtv</option>
                        {current && !matchable.some((item) => item.id === current) &&
                          <option value={current}>{known?.title ?? "Imagen no disponible"}</option>}
                        {matchable.map((item) => <option key={item.id} value={item.id}
                          disabled={item.id !== current && ids.includes(item.id)}>{item.title} — {practiceTargetNames[item.expected_expression ?? ""] ?? ""}</option>)}
                      </select></label>;
                    })}</div>}
                  </div>
                  <div className="inline-actions">
                    <label>Rondas<select value={rounds} onChange={(event) => {
                      const next = Number(event.target.value);
                      updateStep(index, { rounds: next, game_stimulus_ids: (step.game_stimulus_ids ?? []).slice(0, next) });
                    }}>
                      {Array.from({ length: MAX_GAME_ROUNDS - MIN_GAME_ROUNDS + 1 }, (_, offset) => MIN_GAME_ROUNDS + offset)
                        .map((count) => <option key={count} value={count}>{count}</option>)}
                    </select></label>
                    <label>{similar ? "Caras para elegir" : "Opciones por ronda"}<select value={step.option_count ?? DEFAULT_GAME.option_count}
                      onChange={(event) => updateStep(index, { option_count: Number(event.target.value) })}>
                      {RECOGNITION_OPTION_COUNTS.map((count) => <option key={count} value={count}>{count}</option>)}
                    </select></label>
                    <label>Tiempo por ronda (s)<input type="number" min={1} max={MAX_STEP_SECONDS} value={step.exposure_seconds}
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
            </div>
            <div className="step-catalog" role="region" aria-labelledby="step-catalog-title">
              <h5 id="step-catalog-title">Agregar un paso</h5>
              {stepCatalog.map((group) => <div key={group.group} className="step-catalog-group">
                <p className="step-catalog-head"><strong>{group.group}</strong> <span className="muted">{group.hint}</span></p>
                <div className="step-catalog-grid">{group.items.map((item) => <button key={item.key} type="button"
                  className={`step-option${picking === item.key ? " is-selected" : ""}`}
                  aria-labelledby={`step-option-${item.key}-title`} aria-describedby={`step-option-${item.key}`}
                  aria-pressed={item.image ? picking === item.key : undefined} onClick={() => choose(item.key)}>
                  <strong id={`step-option-${item.key}-title`}>{item.title}</strong>
                  <span id={`step-option-${item.key}`}>{item.text}{item.image ? " Lleva una imagen." : ""}</span>
                </button>)}</div>
              </div>)}
              {picking && pickable.length > 0 ? <div className="step-picker">
                <label>Imagen para «{imageChoiceTitle[picking]}»<select value={choice} onChange={(event) => setChoice(event.target.value)}>
                  <option value="">Elige una imagen</option>
                  {pickable.map((item) => <option key={item.id} value={item.id}>{item.title} — {stimulusSummary(item)}</option>)}
                </select></label>
                <div className="inline-actions">
                  <Button variant="primary" disabled={!choice} onClick={addPicked}>Agregar paso</Button>
                  <Button variant="ghost" onClick={() => { setPicking(null); setChoice(""); }}>Cancelar</Button>
                </div>
                {picking !== "stimulus" && <p className="muted">Solo aparecen imágenes emocionales con una expresión esperada: es la respuesta del paso.</p>}
              </div> : !stimuliQuery.loading && (offered.length === 0 || picking) && <div className="empty-state step-picker">
                <p>{offered.length === 0
                  ? `${draft.for_children ? "No hay imágenes «Para niños» aprobadas." : "No hay imágenes disponibles."} Los juegos, el dibujo y la práctica no las necesitan.`
                  : "Ninguna imagen disponible indica una expresión esperada."}
                  {isDocente ? " Sube una en Estímulos." : " Sube las tuyas en Imágenes: se usan cuando tu docente las aprueba."}</p>
                <div className="inline-actions"><ButtonLink variant="secondary" to={isDocente ? paths.stimuli : paths.images}>
                  {isDocente ? "Ir a Estímulos" : "Ir a Imágenes"}</ButtonLink></div>
              </div>}
            </div>
            </div>
          </li>
          <li className="protocol-moment">
            <h4>Al terminar</h4>
            {questionnaireSelect("post")}
          </li>
        </ol>
      </section>

      {!ready && <p className="protocol-missing" role="status">{missing.length > 0
        ? `Para guardar falta: ${missing.join(", ")}.`
        : stepProblems > 0 ? "Para guardar, corrige los pasos marcados." : ""}</p>}
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
        <ActionsMenu name={item.name} items={actions(item)} />
      </div>
    </li>)}</ul>}

    <Modal open={preview !== null} title={preview ? `Vista previa: ${preview.name}` : "Vista previa"} onClose={() => setPreview(null)}>
      {preview && <div className="protocol-preview">
        <p className="muted">{preview.for_children ? "Para niños" : "Para adultos"} · Versión {preview.version}{preview.description ? ` · ${preview.description}` : ""}</p>
        <ol>
          {questionnaireTitle(preview.pre_questionnaire_id) && <li>Antes de empezar: cuestionario {questionnaireTitle(preview.pre_questionnaire_id)}</li>}
          {protocolStepLines(preview.steps, (id) => byId.get(id)?.title).map((line, index) => <li key={index}>{line}</li>)}
          {questionnaireTitle(preview.post_questionnaire_id) && <li>Al terminar: cuestionario {questionnaireTitle(preview.post_questionnaire_id)}</li>}
        </ol>
      </div>}
    </Modal>

    <ConfirmDialog open={removing !== null} title="Eliminar protocolo" confirmLabel="Eliminar" confirming={busy}
      message={removing ? `Se eliminará «${removing.name}» de tus protocolos y ya no se podrá usar en el Analizador. Las sesiones que lo usaron conservan su registro${removing.shared_with_group ? ", y tu grupo deja de verlo como plantilla" : ""}.` : ""}
      onConfirm={() => { void remove(); }} onCancel={() => setRemoving(null)} />
  </section>;
}
