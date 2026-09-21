import { createContext, useContext, useState, type ReactNode } from "react";

interface ActiveSession {
  id: string;
  activityId?: string;
}

interface ActiveSessionContextValue {
  activeSession: ActiveSession | null;
  setActiveSession(session: ActiveSession | null): void;
}

const ActiveSessionContext = createContext<ActiveSessionContextValue>({ activeSession: null, setActiveSession: () => undefined });

export function ActiveSessionProvider({ children }: { children: ReactNode }) {
  const [activeSession, setActiveSession] = useState<ActiveSession | null>(null);
  return <ActiveSessionContext.Provider value={{ activeSession, setActiveSession }}>{children}</ActiveSessionContext.Provider>;
}

export function useActiveSession() {
  return useContext(ActiveSessionContext);
}
