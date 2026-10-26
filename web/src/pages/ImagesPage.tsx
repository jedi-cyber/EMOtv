import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { apiRequest } from "../api/http";
import type { ImageAudience, ImageUploadResult, UserImage } from "../api/types";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";
import { Button } from "../components/Button";
import { Callout } from "../components/Callout";
import { Checkbox } from "../components/Checkbox";
import { Modal } from "../components/Modal";
import { NoticeList } from "../components/NoticeList";
import { PageHeader } from "../components/PageHeader";
import { PageState } from "../components/PageState";
import { StatusChip } from "../components/StatusChip";
import { StimulusImage } from "../components/StimulusImage";
import { audienceNames } from "../stimuli/labels";

const MAX_BYTES = 5 * 1024 * 1024;
const MAX_BATCH = 20;
const TYPES = ["image/png", "image/jpeg", "image/webp"];
const RIGHTS = "No es una foto de una persona que pueda identificarse, y tengo derecho a usarla";

interface PendingFile {
  key: string;
  file: File;
  preview: string;
  title: string;
  origin: string;
  audience: ImageAudience | null;
  rights: boolean;
}

function formatDate(value: string) {
  return new Date(value).toLocaleDateString("es-PE", { day: "numeric", month: "long", year: "numeric" });
}

function titleOf(file: File) {
  return file.name.replace(/\.[^.]+$/, "").slice(0, 120) || "Imagen";
}

/** Imágenes propias del usuario: se suben por lote y se usan cuando su docente las aprueba. */
export function ImagesPage() {
  const { token } = useAuth();
  const query = useApiQuery<UserImage[]>("/own-stimuli");
  const items = query.data ?? [];
  const [adding, setAdding] = useState(false);
  const [files, setFiles] = useState<PendingFile[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [rejected, setRejected] = useState<{ title: string; message: string }[]>([]);
  const ready = files.length > 0 && files.every((item) => item.title.trim() && item.origin.trim() && item.audience && item.rights);

  useEffect(() => () => files.forEach((item) => URL.revokeObjectURL(item.preview)), [files]);

  function choose(list: FileList | null) {
    setError("");
    const chosen = Array.from(list ?? []);
    const invalid = chosen.filter((file) => !TYPES.includes(file.type) || file.size > MAX_BYTES);
    if (invalid.length > 0) setError(`Solo PNG, JPEG o WebP de hasta 5 MB: se omitió ${invalid.map((file) => `«${file.name}»`).join(", ")}.`);
    const valid = chosen.filter((file) => !invalid.includes(file)).slice(0, MAX_BATCH - files.length);
    setFiles((current) => [...current, ...valid.map((file, index) => ({
      key: `${Date.now()}-${index}-${file.name}`, file, preview: URL.createObjectURL(file), title: titleOf(file),
      origin: "", audience: null, rights: false,
    }))]);
  }

  function update(key: string, changes: Partial<PendingFile>) {
    setFiles((current) => current.map((item) => item.key === key ? { ...item, ...changes } : item));
  }

  function remove(key: string) {
    setFiles((current) => current.filter((item) => item.key !== key));
  }

  function close() { setFiles([]); setError(""); setAdding(false); }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!ready) return;
    setBusy(true); setError(""); setMessage(""); setRejected([]);
    const body = new FormData();
    for (const item of files) {
      body.append("files", item.file);
      body.append("titles", item.title.trim());
      body.append("origins", item.origin.trim());
      body.append("audiences", item.audience ?? "");
      body.append("rights_confirmed", String(item.rights));
    }
    try {
      const result = await apiRequest<ImageUploadResult>("/own-stimuli", { method: "POST", body, token });
      const accepted = result.results.filter((item) => item.accepted).length;
      setRejected(result.results.filter((item) => !item.accepted).map((item) => ({ title: item.title, message: item.message ?? "" })));
      setMessage(accepted > 0
        ? `${accepted === 1 ? "Se subió 1 imagen" : `Se subieron ${accepted} imágenes`}. Quedan «En revisión» hasta que tu docente las revise.`
        : "");
      close();
      await query.reload();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "No se pudieron subir las imágenes."); }
    finally { setBusy(false); }
  }

  return <section>
    <PageHeader title="Imágenes"
      description="Tus imágenes para usar en tus protocolos. Tu docente revisa cada una antes de que puedas elegirla."
      actions={<Button variant="primary" onClick={() => { setMessage(""); setRejected([]); setAdding(true); }}>Subir imágenes</Button>} />
    <Callout variant="info" role="note">
      No subas fotos de personas: el sistema revisa cada imagen y rechaza las que parecen mostrar a alguien. Esa revisión
      automática puede equivocarse, por eso tu docente también las revisa. Una imagen «En revisión» no se puede elegir en
      ningún protocolo.
    </Callout>
    <NoticeList />
    {message && <Callout variant="success">{message}</Callout>}
    {rejected.map((item, index) => <Callout key={`${item.title}-${index}`} variant="error">«{item.title}»: {item.message}</Callout>)}
    {error && !adding && <Callout variant="error">{error}</Callout>}

    <Modal open={adding} title="Subir imágenes" onClose={close} busy={busy}
      footer={<>
        <Button disabled={busy} onClick={close}>Cancelar</Button>
        <Button variant="primary" type="submit" form="images-form" disabled={busy || !ready}>
          {busy ? "Subiendo…" : files.length > 1 ? `Subir ${files.length} imágenes` : "Subir imagen"}
        </Button>
      </>}>
      <form id="images-form" className="form-stack" onSubmit={(event) => { void submit(event); }}>
        {error && <Callout variant="error">{error}</Callout>}
        {files.length < MAX_BATCH && <label>Imágenes (PNG, JPEG o WebP, hasta 5 MB cada una)
          <input type="file" multiple accept={TYPES.join(",")} value=""
            onChange={(event) => choose(event.target.files)} />
        </label>}
        <ol className="card-list upload-list">{files.map((item, index) => <li key={item.key} className="card upload-item">
          <img className="stimulus-thumb" src={item.preview} alt="" />
          <div className="form-stack">
            <label>Nombre<input value={item.title} maxLength={120} required
              onChange={(event) => update(item.key, { title: event.target.value })} /></label>
            <label>¿De dónde es esta imagen?<input value={item.origin} maxLength={500} required
              placeholder="Dibujo propio, banco de imágenes con licencia libre…"
              onChange={(event) => update(item.key, { origin: event.target.value })} /></label>
            <fieldset className="audience-choice">
              <legend>¿Para quién es?</legend>
              {(["children", "adults"] as const).map((audience) => <label key={audience}
                className={`audience-option${item.audience === audience ? " is-selected" : ""}`}>
                <input type="radio" name={`audience-${item.key}`} checked={item.audience === audience} required
                  onChange={() => update(item.key, { audience })} />
                <strong>{audienceNames[audience]}</strong>
                <span>{audience === "children" ? "Sirve con niños y con adultos." : "Solo en protocolos para adultos."}</span>
              </label>)}
            </fieldset>
            <Checkbox checked={item.rights} onChange={(event) => update(item.key, { rights: event.target.checked })}>{RIGHTS}</Checkbox>
            <div className="inline-actions">
              <Button size="sm" variant="ghost" onClick={() => remove(item.key)}>Quitar imagen {index + 1}</Button>
            </div>
          </div>
        </li>)}</ol>
      </form>
    </Modal>

    <PageState {...query} empty={!query.loading && !query.error && items.length === 0}
      emptyMessage="Todavía no subiste imágenes."
      emptyAction={<Button variant="primary" onClick={() => setAdding(true)}>Subir imágenes</Button>} onRetry={query.reload} />
    {items.length > 0 && <ul className="card-list stimulus-list">{items.map((item) => <li key={item.id} className="card row-card stimulus-row">
      <StimulusImage id={item.id} alt={item.title} path={`/own-stimuli/${encodeURIComponent(item.id)}/file`} />
      <div>
        <strong>{item.title}</strong>
        <span>Origen: {item.origin} · Subida el {formatDate(item.created_at)}</span>
        <span className="inline-actions">
          {item.status === "pending" ? <StatusChip tone="progress">En revisión</StatusChip> : <StatusChip tone="success">Aprobada</StatusChip>}
          <StatusChip tone="neutral">{audienceNames[item.audience]}</StatusChip>
        </span>
        {item.status === "pending" && item.expires_at && <span className="muted">
          Si tu docente no la revisa antes del {formatDate(item.expires_at)}, se eliminará.
        </span>}
      </div>
    </li>)}</ul>}
  </section>;
}
