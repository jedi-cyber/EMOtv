import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiRequest } from "../api/http";
import type { ExamDetail, ExamSummary } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip } from "../components/StatusChip";
import { examStateNames, examStateTone, formatDateTime } from "../exams/labels";
import { paths } from "../routes/paths";

/** Exámenes simulados del docente: crear con un clic y ver los anteriores. */
export function ExamsPage() {
  const { token } = useAuth();
  const navigate = useNavigate();
  const result = useApiQuery<ExamSummary[]>("/exams");
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState("");
  const exams = result.data ?? [];

  async function create() {
    setCreating(true); setError("");
    try {
      const exam = await apiRequest<ExamDetail>("/exams", { method: "POST", token });
      navigate(paths.exam(exam.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "No se pudo crear el examen.");
      setCreating(false);
    }
  }

  const createButton = <Button loading={creating} onClick={() => { void create(); }}>Crear examen</Button>;
  return <>
    <PageHeader title="Exámenes"
      description="EMOtv registra la expresión estimada de cada estación durante todo el examen. Tú solo creas el examen, confirmas los consentimientos, lo inicias y lo terminas."
      actions={exams.length > 0 ? createButton : undefined} />
    {error && <Callout variant="error"><p>{error}</p></Callout>}
    <PageState loading={result.loading} error={result.error} connectionError={result.connectionError} errorStatus={result.errorStatus}
      empty={!result.loading && !result.error && exams.length === 0} emptyMessage="Aún no tienes exámenes." emptyAction={createButton}
      onRetry={() => { void result.reload(); }} />
    {!result.loading && exams.length > 0 && <div className="table-wrap"><table className="data-table">
      <thead><tr><th>Código</th><th>Creado</th><th>Estado</th><th>Estaciones</th></tr></thead>
      <tbody>{exams.map((exam) => <tr key={exam.id}>
        <td data-label="Código"><Link to={paths.exam(exam.id)}><strong className="exam-code-inline">{exam.join_code}</strong></Link></td>
        <td data-label="Creado">{formatDateTime(exam.created_at)}</td>
        <td data-label="Estado"><StatusChip tone={examStateTone[exam.state]}>{examStateNames[exam.state]}</StatusChip></td>
        <td data-label="Estaciones">{exam.station_count}</td>
      </tr>)}</tbody>
    </table></div>}
  </>;
}
