import { createContext, useCallback, useContext, useMemo, useState } from "react";
import type { ReactNode } from "react";

export interface AssistantDraft { text: string; id: number }

interface AssistantValue {
  open: boolean;
  setOpen: (open: boolean) => void;
  draft: AssistantDraft | null;
  /** Abre a Emi con una pregunta editable; no envía nada hasta que la persona pulse "Enviar". */
  askAssistant: (question: string) => void;
}

const AssistantContext = createContext<AssistantValue | null>(null);

export function AssistantProvider({ children }: { children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<AssistantDraft | null>(null);
  const askAssistant = useCallback((question: string) => {
    setDraft((current) => ({ text: question, id: (current?.id ?? 0) + 1 }));
    setOpen(true);
  }, []);
  const value = useMemo(() => ({ open, setOpen, draft, askAssistant }), [open, draft, askAssistant]);
  return <AssistantContext.Provider value={value}>{children}</AssistantContext.Provider>;
}

export function useAssistant(): AssistantValue | null {
  return useContext(AssistantContext);
}
