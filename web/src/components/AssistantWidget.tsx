import { useRef, useState } from "react";
import { useAuth } from "../auth/useAuth";
import { useAssistant } from "./AssistantContext";
import { ChatConversation } from "./ChatConversation";
import { NavIcon } from "./NavIcon";

export function AssistantWidget() {
  const { user, token, loading } = useAuth();
  if (!user || !token || loading) return null;
  return <AssistantPanel key={user.id} />;
}

function AssistantPanel() {
  // Sin AssistantProvider el panel conserva su propio estado de apertura.
  const shared = useAssistant();
  const [localOpen, setLocalOpen] = useState(false);
  const open = shared?.open ?? localOpen;
  const setOpen = shared?.setOpen ?? setLocalOpen;
  const launcherRef = useRef<HTMLButtonElement>(null);
  function minimize() {
    setOpen(false);
    launcherRef.current?.focus();
  }
  return <aside className="assistant-widget" aria-label="Emi, asistente de EMOtv">
    <section id="assistant-panel" className="assistant-panel" hidden={!open} aria-labelledby="assistant-title"
      onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); minimize(); } }}>
      <header className="assistant-header">
        <div className="assistant-identity"><NavIcon name="chat" /><div><h2 id="assistant-title">Emi</h2><p>Asistente educativo de EMOtv</p></div></div>
        <button type="button" className="assistant-minimize" onClick={minimize} aria-label="Minimizar a Emi">−</button>
      </header>
      <ChatConversation open={open} draft={shared?.draft ?? null} />
    </section>
    <button ref={launcherRef} type="button" className="assistant-launcher" aria-expanded={open} aria-controls="assistant-panel"
      onClick={() => open ? minimize() : setOpen(true)} aria-label={open ? "Minimizar a Emi" : "Abrir a Emi"}>
      <NavIcon name="chat" /><span>Emi</span>
    </button>
  </aside>;
}
