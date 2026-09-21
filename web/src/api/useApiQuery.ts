import { useCallback, useEffect, useState } from "react";
import { ApiError, apiRequest, isConnectionError } from "./http";
import { useAuth } from "../auth/useAuth";

export function useApiQuery<T>(path: string | null) {
  const { token } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [connectionError, setConnectionError] = useState(false);
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    if (path === null) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    setConnectionError(false);
    try {
      setData(await apiRequest<T>(path, { token }));
    } catch (reason) {
      if (reason instanceof ApiError && reason.status === 401) return;
      setConnectionError(isConnectionError(reason));
      setError(isConnectionError(reason)
        ? "No pudimos cargar esta información porque el servicio no responde."
        : reason instanceof Error ? reason.message : "Error inesperado");
    } finally {
      setLoading(false);
    }
  }, [path, token]);

  useEffect(() => { void reload(); }, [reload]);
  return { data, error, connectionError, loading, reload };
}
