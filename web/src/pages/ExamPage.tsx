import { useCallback, useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { ApiError, apiRequest } from "../api/http";
import type { ExamDetail } from "../api/types";
import { useAuth } from "../auth/useAuth";
import { Button, ButtonLink } from "../components/Button";
import { Callout } from "../components/Callout";
import { Card } from "../components/Card";
import { ConfirmDialog } from "../components/ConfirmDialog";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip } from "../components/StatusChip";
import { examStateNames, examStateTone, formatDateTime, stationStatus } from "../exams/labels";
import { paths } from "../routes/paths";

const POLL_MS = 3000;

type Action = "consents" | "start" | "finish";

/**
 * Un examen simulado: el código para las estaciones y cuatro pasos (crear,
 * «Recibí los consentimientos de todos», Iniciar y Terminar). Cada estación se
 * muestra por su código y su estado; nunca con imágenes ni expresiones.
 */
export function ExamPage() {
  const { examId = "" } = useParams();
  const { token } = useAuth();
  const [exam, setExam] = useState<ExamDetail | null>(null);
  const [loadError, setLoadError] = useState<ApiError | null>(null);
  const [actionError, setActionError] = useState("");
  const [busy, setBusy] = useState<Action | null>(null);
  const [asking, setAsking] = useState<"consents" | "finish" | null>(null);
  const path = `/exams/${encodeURIComponent(examId)}`;

  const load = useCallback(async () => {
    try {
      setExam(await apiRequest<ExamDetail>(path, { token }));
      setLoadError(null);
    } catch (reason) {
      if (reason instanceof ApiError) setLoadError(reason);
    }
  }, [path, token]);

  const closed = exam?.state === "closed";
  useEffect(() => {
    void load();
    if (closed) return;
    const timer = window.setInterval(() => { void load(); }, POLL_MS);
    return () => window.clearInterval(timer);
  }, [load, closed]);

  async function act(action: Action) {
    setBusy(action); setActionError("");
    try {
      setExam(await apiRequest<ExamDetail>(`${path}/${action}`, { method: "POST", token }));
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : "No se pudo completar la acción.");
      void load();
    } finally {
      setBusy(null); setAsking(null);
    }
  }

  if (!exam) return <>
    <PageHeader title="Examen" />
    <PageState loading={!loadError} error={loadError?.message ?? ""} errorStatus={loadError?.status ?? null}
      connectionError={loadError ? loadError.status === 0 || loadError.status >= 500 : false} onRetry={() => { void load(); }} />
  </>;

  const pending = exam.stations.filter((item) => !item.consent_confirmed && !item.finished);
  const consented = exam.stations.some((item) => item.consent_confirmed);
  const stationUrl = `${window.location.origin}${paths.station}`;
  return <>
    <PageHeader title={`Examen ${exam.join_code}`}
      description={<StatusChip tone={examStateTone[exam.state]}>{examStateNames[exam.state]}</StatusChip>}
      actions={<ButtonLink variant="ghost" to={paths.exams}>Todos los exámenes</ButtonLink>} />

    {!closed && <Card className="exam-join">
      <p>En cada estación abre <strong>{stationUrl}</strong> y escribe este código:</p>
      <p className="exam-code" aria-label={`Código del examen: ${exam.join_code.split("").join(" ")}`}>{exam.join_code}</p>
      <p className="exam-join-hint">Cada estación muestra el código de su sesión para anotarlo en su consentimiento firmado.</p>
    </Card>}

    {actionError && <Callout variant="error"><p>{actionError}</p></Callout>}

    {!closed && <div className="inline-actions exam-steps">
      {pending.length > 0 && <Button loading={busy === "consents"} onClick={() => setAsking("consents")}>
        Recibí los consentimientos de todos
      </Button>}
      {exam.state === "open" && <Button variant={pending.length > 0 ? "secondary" : "primary"} loading={busy === "start"}
        disabled={!consented || busy !== null} onClick={() => { void act("start"); }}>Iniciar examen</Button>}
      <Button variant={exam.state === "in_progress" ? "primary" : "ghost"} loading={busy === "finish"} disabled={busy !== null}
        onClick={() => setAsking("finish")}>Terminar examen</Button>
    </div>}
    {!closed && <p className="exam-step-hint">{nextStep(exam.state, exam.stations.length, pending.length, consented)}</p>}
    {closed && <Callout variant="success"><p>
      Examen terminado{exam.closed_at ? ` el ${formatDateTime(exam.closed_at)}` : ""}. Cada estación mostró el mensaje final.
    </p></Callout>}

    <h2 className="exam-stations-title">Estaciones ({exam.stations.length})</h2>
    {exam.stations.length === 0
      ? <p className="empty-state">Aún no se unió ninguna estación.</p>
      : <div className="table-wrap"><table className="data-table">
        <thead><tr><th>Código de sesión</th><th>Se unió</th><th>Consentimiento</th><th>Estado</th></tr></thead>
        <tbody>{exam.stations.map((station) => {
          const status = stationStatus(station);
          return <tr key={station.code}>
            <td data-label="Código de sesión"><strong className="exam-code-inline">{station.code}</strong></td>
            <td data-label="Se unió">{formatDateTime(station.joined_at)}</td>
            <td data-label="Consentimiento">{station.consent_confirmed ? "Recibido" : "Pendiente"}</td>
            <td data-label="Estado"><StatusChip tone={status.tone}>{status.text}</StatusChip></td>
          </tr>;
        })}</tbody>
      </table></div>}

    <ConfirmDialog open={asking === "consents"} title="Consentimientos recibidos" confirmVariant="primary"
      confirmLabel="Sí, los recibí" confirming={busy === "consents"}
      message={`Confirmas que recibiste el consentimiento firmado de ${pending.length === 1 ? "la estación" : `las ${pending.length} estaciones`} que esperan (${pending.map((item) => item.code).join(", ")}). Con esto empiezan a calibrarse.`}
      onConfirm={() => { void act("consents"); }} onCancel={() => setAsking(null)} />
    <ConfirmDialog open={asking === "finish"} title="Terminar el examen" confirmLabel="Terminar examen" confirming={busy === "finish"}
      message="Todas las estaciones dejan de registrar y muestran el mensaje final. El examen no se puede reanudar."
      onConfirm={() => { void act("finish"); }} onCancel={() => setAsking(null)} />
  </>;
}

/** Qué falta para el siguiente paso, en una línea. */
function nextStep(state: ExamDetail["state"], stations: number, pending: number, consented: boolean) {
  if (state === "in_progress") return pending > 0
    ? "Examen en curso. Hay estaciones nuevas: confirma su consentimiento para que empiecen a registrar."
    : "Examen en curso. Cuando termine, pulsa «Terminar examen».";
  if (stations === 0) return "Espera a que las estaciones se unan con el código.";
  if (pending > 0) return "Cuando tengas los consentimientos firmados de las estaciones que esperan, confírmalos.";
  if (consented) return "Las estaciones se calibran solas. Cuando todas estén listas, inicia el examen.";
  return "Espera a que las estaciones se unan con el código.";
}
