import { useEffect, useState } from "react";
import { apiBlob } from "../api/http";
import { useAuth } from "../auth/useAuth";

/** Imagen de un estímulo del banco. Se pide con el token, porque un <img> no lo envía.
 * path permite pedirla por otra ruta (las imágenes propias, o su vista ampliada). */
export function StimulusImage({ id, alt, path, className = "stimulus-thumb" }: { id: string; alt: string; path?: string; className?: string }) {
  const { token } = useAuth();
  const [url, setUrl] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    setFailed(false);
    apiBlob(path ?? `/stimuli/${encodeURIComponent(id)}/file`, token)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => { if (!cancelled) setFailed(true); });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [id, path, token]);

  if (failed) return <span className={`${className} stimulus-thumb-empty muted`}>Sin vista previa</span>;
  if (!url) return <span className={`${className} stimulus-thumb-empty`} aria-hidden="true" />;
  return <img className={className} src={url} alt={alt} />;
}
