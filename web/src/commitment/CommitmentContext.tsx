import { createContext, useCallback, useContext, useEffect, useState } from "react";
import type { PropsWithChildren } from "react";
import { apiRequest } from "../api/http";
import { isConductor } from "../auth/roles";
import { useAuth } from "../auth/useAuth";

export interface VersionedText {
  kind: "commitment" | "child_notice";
  version: string;
  provisional: boolean;
  content: string;
  required: boolean;
  accepted: boolean;
}

type CommitmentState = "loading" | "required" | "accepted" | "not_applicable";

interface CommitmentValue {
  state: CommitmentState;
  text: VersionedText | null;
  error: string;
  reload(): Promise<void>;
  accept(version: string): Promise<void>;
}

const CommitmentContext = createContext<CommitmentValue | null>(null);

/**
 * Compromiso de confidencialidad de usuarios y docentes. Sin aceptar la versión
 * vigente no pueden registrar participantes ni iniciar sesiones (el servidor
 * también lo exige). El administrador y el superadministrador no lo aceptan.
 */
export function CommitmentProvider({ children }: PropsWithChildren) {
  const { token, user } = useAuth();
  const applies = isConductor(user?.role);
  const [state, setState] = useState<CommitmentState>(applies ? "loading" : "not_applicable");
  const [text, setText] = useState<VersionedText | null>(null);
  const [error, setError] = useState("");

  const reload = useCallback(async () => {
    if (!applies || !token) { setState("not_applicable"); return; }
    setState("loading"); setError("");
    try {
      const current = await apiRequest<VersionedText>("/commitment", { token });
      setText(current);
      setState(current?.required ? "required" : "accepted");
    } catch (reason) {
      // Sin respuesta no se bloquea la navegación: el servidor rechaza igual
      // las acciones que requieren el compromiso.
      setError(reason instanceof Error ? reason.message : "No se pudo consultar el compromiso.");
      setState("accepted");
    }
  }, [applies, token]);

  useEffect(() => { void reload(); }, [reload, user?.id]);

  const accept = useCallback(async (version: string) => {
    const current = await apiRequest<VersionedText>("/commitment/accept", {
      method: "POST", token, body: JSON.stringify({ version }),
    });
    setText(current);
    setState(current?.required ? "required" : "accepted");
  }, [token]);

  return <CommitmentContext.Provider value={{ state, text, error, reload, accept }}>{children}</CommitmentContext.Provider>;
}

export function useCommitment(): CommitmentValue {
  const value = useContext(CommitmentContext);
  if (!value) throw new Error("useCommitment requiere CommitmentProvider");
  return value;
}
