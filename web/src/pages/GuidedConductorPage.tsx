import { useCallback, useEffect, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { apiRequest } from "../api/http";
import type { GuidedPhase, GuidedState, MarkerKind, Questionnaire } from "../api/types";
import { useAuth } from "../auth/useAuth";
import { Button, ButtonLink } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { PageHeader } from "../components/PageHeader";
import { StatusChip } from "../components/StatusChip";
import { useExpressionCatalog } from "../expressions/ExpressionCatalog";
import { readViewToken, storeViewToken } from "../guided/viewToken";
import { SessionQuestionnaire } from "../questionnaires/SessionQuestionnaire";
import { paths } from "../routes/paths";

const POLL_MS = 1000;
const phaseNames: Record<GuidedPhase, string> = {
  confirmation: "Confirmación",
  pre_questionnaire: "Cuestionario previo",
  before_analyzer: "Imágenes antes del analizador",
  calibration: "Calibración neutral",
  stimuli: "Estímulos",
  post_questionnaire: "Cuestionario posterior",
  finished: "Sesión terminada",
  stopped: "Sesión detenida",
};
export const markerButtons: { kind: Exclude<MarkerKind, "note">; label: string; key: string }[] = [
  { kind: "distracted", label: "Se distrajo", key: "d" },
  { kind: "laughed", label: "Se rió", key: "r" },
  { kind: "cried", label: "Lloró", key: "l" },
  { kind: "asked_to_stop", label: "Pidió parar", key: "p" },
];
const markerNames: Record<MarkerKind, string> = {
  distracted: "Se distrajo", laughed: "Se rió", cried: "Lloró", asked_to_stop: "Pidió parar", note: "Nota",
};
const issueNames: Record<string, string> = {
  no_frame: "no llegó imagen de la cámara", no_face: "no se ve el rostro", off_center: "rostro no centrado",
  too_small: "rostro muy lejos", too_dark: "poca luz", too_bright: "demasiada luz", tilted: "cabeza inclinada",
};
const stopNames = { participant: "el participante pidió parar", guardian: "el padre, la madre o el tutor pidió parar", conductor: "quien conduce la sesión la terminó" };
const time = (value: string) => new Date(value).toLocaleTimeString("es-PE", { timeStyle: "medium" });

/** Vista de quien conduce: progreso, estado de la captura y marcadores. */
export function GuidedConductorPage() {
  const { sessionId = "" } = useParams();
  const { token } = useAuth();
  const { label: expressionLabel } = useExpressionCatalog();
  const base = `/guided-sessions/${encodeURIComponent(sessionId)}`;
  const [state, setState] = useState<GuidedState | null>(null);
  const [questionnaire, setQuestionnaire] = useState<Questionnaire | null>(null);
  const [viewToken, setViewToken] = useState<string | null>(() => readViewToken(sessionId));
  const [confirm, setConfirm] = useState({ commitment_reminder: false, authorization_confirmed: false, guardian_present: false, child_assent: false });
  const [note, setNote] = useState("");
  const [verbal, setVerbal] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const stateRef = useRef<GuidedState | null>(null);
  stateRef.current = state;

  const reload = useCallback(async () => {
    try { setState(await apiRequest<GuidedState>(base, { token })); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo cargar la sesión."); }
  }, [base, token]);

  useEffect(() => {
    void reload();
    const timer = window.setInterval(() => {
      if (stateRef.current && ["finished", "stopped"].includes(stateRef.current.phase)) return;
      void reload();
    }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [reload]);

  const phase = state?.phase;
  useEffect(() => {
    if (phase !== "pre_questionnaire" && phase !== "post_questionnaire") { setQuestionnaire(null); return; }
    const moment = phase === "pre_questionnaire" ? "pre" : "post";
    apiRequest<{ questionnaire: Questionnaire; answered: boolean }>(`/sessions/${encodeURIComponent(sessionId)}/questionnaires/${moment}`, { token })
      .then((data) => setQuestionnaire(data.answered ? null : data.questionnaire))
      .catch(() => setQuestionnaire(null));
  }, [phase, sessionId, token]);

  async function act(path: string, body?: unknown) {
    setBusy(true); setError("");
    try {
      await apiRequest(`${base}${path}`, { method: "POST", token, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
      await reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo completar la acción."); }
    finally { setBusy(false); }
  }

  const active = state != null && !["finished", "stopped"].includes(state.phase);
  function addMarker(kind: MarkerKind, text?: string) {
    void act("/markers", { kind, ...(text ? { note: text } : {}) });
  }
  const addMarkerRef = useRef(addMarker);
  addMarkerRef.current = addMarker;

  // Teclas rápidas de los marcadores (fuera de los campos de texto).
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (!active || event.ctrlKey || event.metaKey || event.altKey) return;
      if (target && ["INPUT", "TEXTAREA", "SELECT"].includes(target.tagName)) return;
      const marker = markerButtons.find((item) => item.key === event.key.toLowerCase());
      if (marker) { event.preventDefault(); addMarkerRef.current(marker.kind); }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [active]);

  async function newLink() {
    setBusy(true);
    try {
      const data = await apiRequest<{ view_token: string }>(`${base}/view-link`, { method: "POST", token });
      storeViewToken(sessionId, data.view_token); setViewToken(data.view_token);
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudo crear el enlace."); }
    finally { setBusy(false); }
  }

  const viewUrl = viewToken ? `${window.location.origin}${paths.participantView(viewToken)}` : null;
  const step = state?.step_index != null ? state.steps[state.step_index] : null;
  const stepCaptures = state && step ? state.captures.filter((item) => item.step_index === step.index) : [];
  const child = state?.participant_kind === "child";
  const confirmReady = confirm.commitment_reminder && (state?.participant_kind == null
    || (child ? confirm.guardian_present && confirm.child_assent : confirm.authorization_confirmed));

  return <section>
    <ButtonLink variant="ghost" className="back-link" to={paths.session(sessionId)}>← Detalle de la sesión</ButtonLink>
    <PageHeader title="Sesión guiada" description={state ? phaseNames[state.phase] : "Cargando la sesión…"} />
    {error && <Callout variant="error">{error}</Callout>}
    {state?.abstract_notice && <Callout variant="info" role="note">{state.abstract_notice}</Callout>}

    {state && active && <div className="card form-stack">
      <h2>Vista del participante</h2>
      <p className="muted">Ábrela en esta computadora (en otra ventana, a pantalla completa) o en otro dispositivo con el enlace. No muestra resultados ni notas.</p>
      {viewUrl ? <div className="inline-actions">
        <Button onClick={() => window.open(viewUrl, "emotv-participante", "noopener")}>Abrir vista del participante</Button>
        <Button variant="ghost" onClick={() => { void navigator.clipboard?.writeText(viewUrl); }}>Copiar enlace</Button>
      </div> : <Button disabled={busy} onClick={() => { void newLink(); }}>Crear enlace de la vista del participante</Button>}
    </div>}

    {state?.phase === "confirmation" && <div className="card form-stack">
      <h2>Antes de empezar</h2>
      <Callout variant="info" role="note">
        Recuerda tu compromiso de confidencialidad: los datos de la sesión son solo para tu práctica y la de tu docente.
        No escribas nombres ni datos que identifiquen a la persona. EMOtv estima expresiones; no diagnostica.
      </Callout>
      <Checkbox checked={confirm.commitment_reminder} onChange={(event) => setConfirm({ ...confirm, commitment_reminder: event.target.checked })}>
        Leí el recordatorio del compromiso de confidencialidad
      </Checkbox>
      {state.participant_kind === "adult" && <Checkbox checked={confirm.authorization_confirmed}
        onChange={(event) => setConfirm({ ...confirm, authorization_confirmed: event.target.checked })}>
        El participante dio su autorización firmada para participar y para el uso de la cámara
      </Checkbox>}
      {child && <>
        <Checkbox checked={confirm.guardian_present} onChange={(event) => setConfirm({ ...confirm, guardian_present: event.target.checked })}>
          El padre, la madre o el tutor está presente
        </Checkbox>
        <Checkbox checked={confirm.child_assent} onChange={(event) => setConfirm({ ...confirm, child_assent: event.target.checked })}>
          El niño o la niña dio su asentimiento
        </Checkbox>
      </>}
      <Button variant="primary" disabled={busy || !confirmReady} onClick={() => { void act("/confirm", confirm); }}>Confirmar y empezar</Button>
    </div>}

    {(state?.phase === "pre_questionnaire" || state?.phase === "post_questionnaire") && <div className="card">
      {questionnaire
        ? <SessionQuestionnaire sessionId={sessionId} moment={state.phase === "pre_questionnaire" ? "pre" : "post"}
          questionnaire={questionnaire} onDone={() => { void act("/advance"); }} />
        : <Button variant="primary" disabled={busy} onClick={() => { void act("/advance"); }}>Continuar</Button>}
    </div>}

    {state?.phase === "calibration" && <div className="card form-stack">
      <h2>Calibración neutral</h2>
      <p>Pide al participante que mire la pantalla con el rostro relajado unos segundos.</p>
      {state.calibration.notice && <Callout variant="warning">{state.calibration.notice}</Callout>}
      {state.calibration.state === "calibrating"
        ? <p role="status">Calibrando… {Math.round(state.calibration.progress * 100)} %</p>
        : <Button variant="primary" disabled={busy} onClick={() => { void act("/calibration"); }}>Iniciar calibración</Button>}
    </div>}

    {step && state && <div className="card form-stack">
      <p className="step-caption">Estímulo {step.index + 1} de {state.step_count}{state.phase === "before_analyzer" ? " · antes del analizador, sin capturas" : ""}</p>
      <h2>{step.title}</h2>
      <p className="readout-md" role="timer">{Math.ceil(state.remaining_seconds ?? 0)} s</p>
      {state.phase === "stimuli" && <p role="status">{state.capture_status.length > 0
        ? `Reintentando la captura: ${state.capture_status.map((item) => issueNames[item] ?? item).join(", ")}.`
        : stepCaptures.length > 0 ? "Captura registrada." : `Captura automática a los ${step.capture_after_seconds} s.`}</p>}
      {stepCaptures.length > 0 && <ul className="card-list">{stepCaptures.map((item) => <li key={item.id} className="row-card">
        <span>{item.seconds_since_stimulus} s · {item.emotion ? `${expressionLabel(item.emotion)} (estimada)` : "Sin expresión estimada"}</span>
        {item.quality === "good" ? <StatusChip tone="success">Buena calidad</StatusChip>
          : <StatusChip tone="neutral">Marcada: {item.quality_issues.map((issue) => issueNames[issue] ?? issue).join(", ")}</StatusChip>}
      </li>)}</ul>}
      {step.record_verbal_response && <form className="form-stack" onSubmit={(event) => { event.preventDefault(); void act("/verbal-responses", { step_index: step.index, text: verbal }).then(() => setVerbal("")); }}>
        <label>Lo que el participante dice ver<input value={verbal} maxLength={300} onChange={(event) => setVerbal(event.target.value)} /></label>
        <small className="muted">Escríbelo tal como lo dijo. Se guarda cifrado. EMOtv no lo interpreta. No escribas nombres ni datos que identifiquen a la persona.</small>
        <Button type="submit" disabled={busy || !verbal.trim()}>Guardar lo que dice ver</Button>
      </form>}
      <Button disabled={busy} onClick={() => { void act("/skip"); }}>Saltar este estímulo</Button>
    </div>}

    {state && active && state.phase !== "confirmation" && <div className="card form-stack" aria-label="Marcadores">
      <h2>Marcadores</h2>
      <div className="inline-actions">{markerButtons.map((item) => <Button key={item.kind} disabled={busy}
        aria-keyshortcuts={item.key.toUpperCase()} onClick={() => addMarker(item.kind)}>
        {item.label} <kbd>{item.key.toUpperCase()}</kbd></Button>)}</div>
      <form className="form-stack" onSubmit={(event) => { event.preventDefault(); addMarker("note", note); setNote(""); }}>
        <label>Nota breve<input value={note} maxLength={300} onChange={(event) => setNote(event.target.value)} /></label>
        <small className="muted">Se guarda cifrada. No escribas nombres ni datos que identifiquen a la persona.</small>
        <Button type="submit" disabled={busy || !note.trim()}>Guardar nota</Button>
      </form>
      <h3>Terminar</h3>
      <div className="inline-actions">
        <Button variant="danger" disabled={busy} onClick={() => { void act("/stop", { reason: "participant" }); }}>El participante pidió parar</Button>
        {child && <Button variant="danger" disabled={busy} onClick={() => { void act("/stop", { reason: "guardian" }); }}>El tutor pidió parar</Button>}
        <Button variant="ghost" disabled={busy} onClick={() => { void act("/stop", { reason: "conductor" }); }}>Terminar la sesión</Button>
      </div>
    </div>}

    {state && !active && <Callout variant={state.phase === "finished" ? "success" : "info"}>
      {state.phase === "finished" ? "La sesión terminó y quedó registrada." : `La sesión se detuvo: ${stopNames[state.stop_reason ?? "conductor"]}.`}
    </Callout>}

    {state && state.markers.length > 0 && <section className="card">
      <h2>Registro de marcadores</h2>
      <ul className="card-list">{state.markers.map((item) => <li key={item.id} className="row-card">
        <span>{time(item.occurred_at)} · {markerNames[item.kind]}{item.note ? `: ${item.note}` : ""}</span>
      </li>)}</ul>
    </section>}
  </section>;
}
