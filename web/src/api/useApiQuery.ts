import { useCallback, useEffect, useState } from "react";
import { apiRequest } from "./http";
import { useAuth } from "../auth/useAuth";

export function useApiQuery<T>(path: string | null) {
  const { token } = useAuth();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const reload = useCallback(async () => {
    if (path === null) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError("");
    try {
      setData(await apiRequest<T>(path, { token }));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Error inesperado");
    } finally {
      setLoading(false);
    }
  }, [path, token]);

  useEffect(() => { void reload(); }, [reload]);
  return { data, error, loading, reload };
}
