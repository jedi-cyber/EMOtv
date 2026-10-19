import { useState } from "react";
import { ApiError, apiRequest } from "../api/http";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip, type StatusTone } from "../components/StatusChip";
import { emotionModelName } from "../sessions/labels";

type ModelState = "SUPPORTED" | "WARNING" | "BLOCKED";

export interface LocalModelStatus {
  model_id: string;
  name: string;
  version: string;
  state: ModelState;
  reasons: string[];
  checks: { weights_verified: boolean; benchmark_current: boolean };
  p95_ms: number | null;
  /** p95 del cuadro completo por sesiones simultáneas según el benchmark; solo informativo. */
  concurrent_frame_p95_ms: Record<string, number> | null;
  is_default: boolean;
}

export interface LocalModelSettings {
  default_model_id: string;
  changed_by: string | null;
  changed_at: string | null;
  fallback_model_id: string | null;
  fallback_at: string | null;
  models: LocalModelStatus[];
}

const stateText: Record<ModelState, string> = { SUPPORTED: "Admitido", WARNING: "Admitido con advertencias", BLOCKED: "Sin admisión vigente" };
const stateTone: Record<ModelState, StatusTone> = { SUPPORTED: "success", WARNING: "progress", BLOCKED: "error" };
const dateTime = (value: string) => new Date(value).toLocaleString("es-PE", { dateStyle: "long", timeStyle: "short" });
function concurrencyText(values: Record<string, number> | null): string | null {
  if (!values || Object.keys(values).length === 0) return null;
  return Object.entries(values).sort(([a], [b]) => Number(a) - Number(b))
    .map(([sessions, p95]) => `${sessions} ${sessions === "1" ? "sesión" : "sesiones"}: ${Math.round(p95)} ms`).join(" · ");
}
const yesNo = (value: boolean) => <StatusChip tone={value ? "success" : "error"}>{value ? "Sí" : "No"}</StatusChip>;

export function AdminModelsPage() {
  const { token } = useAuth();
  const query = useApiQuery<LocalModelSettings>("/admin/models");
  const settings = query.data;
  const [saving, setSaving] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function makeDefault(model: LocalModelStatus) {
    setSaving(model.model_id); setMessage(""); setError("");
    try {
      await apiRequest<LocalModelSettings>("/admin/models/default", {
        method: "PUT", token, body: JSON.stringify({ model_id: model.model_id }),
      });
      setMessage(`${emotionModelName(model.model_id)} es ahora el modelo predeterminado. Rige desde la próxima sesión, sin reiniciar el servidor.`);
      await query.reload();
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "No se pudo cambiar el modelo predeterminado");
    } finally { setSaving(""); }
  }

  return <section>
    <PageHeader title="Modelos"
      description="Modelos locales de estimación de la expresión facial. El predeterminado se usa cuando quien conduce la sesión no elige otro." />
    {message && <Callout variant="success">{message}</Callout>}
    {error && <Callout variant="error">{error}</Callout>}
    <PageState {...query} onRetry={query.reload} />
    {settings && <>
      {settings.fallback_model_id && settings.fallback_at && <Callout variant="warning">
        El {dateTime(settings.fallback_at)} el modelo predeterminado no tenía admisión vigente y se usó {emotionModelName(settings.fallback_model_id)} como respaldo.
      </Callout>}
      <div className="table-wrap"><table><thead><tr>
        <th>Modelo</th><th>Estado</th><th>Pesos verificados</th><th>Medición vigente</th><th>Latencia p95</th><th>Predeterminado</th>
      </tr></thead><tbody>
        {settings.models.map((model) => <tr key={model.model_id}>
          <td>{emotionModelName(model.model_id)}<br /><small className="muted">Versión {model.version.slice(0, 12)}</small></td>
          <td><StatusChip tone={stateTone[model.state]}>{stateText[model.state]}</StatusChip>
            {model.reasons.length > 0 && <><br /><small className="muted">{model.reasons.join("; ")}</small></>}</td>
          <td>{yesNo(model.checks.weights_verified)}</td>
          <td>{yesNo(model.checks.benchmark_current)}</td>
          <td>{model.p95_ms == null ? "—" : `${Math.round(model.p95_ms)} ms`}
            {concurrencyText(model.concurrent_frame_p95_ms) && <><br /><small className="muted">Cuadro completo: {concurrencyText(model.concurrent_frame_p95_ms)}</small></>}</td>
          <td>{model.is_default ? <StatusChip tone="success">Predeterminado</StatusChip>
            : <Button variant="secondary" size="sm" disabled={Boolean(saving) || model.state === "BLOCKED"}
              aria-label={`Usar ${emotionModelName(model.model_id)} como predeterminado`}
              onClick={() => { void makeDefault(model); }}>{saving === model.model_id ? "Guardando…" : "Usar como predeterminado"}</Button>}</td>
        </tr>)}
      </tbody></table></div>
      <p className="muted">{settings.changed_at
        ? `Último cambio: ${settings.changed_by ?? "cuenta eliminada"}, el ${dateTime(settings.changed_at)}.`
        : "Rige el modelo predeterminado inicial; nadie lo ha cambiado todavía."}</p>
      <p className="muted">La latencia es la del benchmark medido en este servidor; describe el tiempo de respuesta, no la calidad de la estimación.</p>
      <p className="muted">Solo se puede elegir un modelo con admisión vigente. Si el predeterminado la pierde, el sistema usa el otro modelo y lo registra aquí.</p>
    </>}
  </section>;
}
