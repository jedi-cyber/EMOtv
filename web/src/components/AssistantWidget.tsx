import { useRef, useState } from "react";
import { useAuth } from "../auth/useAuth";
import { ChatConversation } from "./ChatConversation";
import { NavIcon } from "./NavIcon";

export function AssistantWidget() {
  const { user, token, loading } = useAuth();
  if (!user || !token || loading) return null;
  return <AssistantPanel key={user.id} />;
}

function AssistantPanel() {
  const [open, setOpen] = useState(false);
  const launcherRef = useRef<HTMLButtonElement>(null);
  function minimize() {
    setOpen(false);
    launcherRef.current?.focus();
  }
  return <aside className="assistant-widget" aria-label="Asistente EMOtv">
    <section id="assistant-panel" className="assistant-panel" hidden={!open} aria-labelledby="assistant-title"
      onKeyDown={(event) => { if (event.key === "Escape") { event.stopPropagation(); minimize(); } }}>
      <header className="assistant-header">
        <div className="assistant-identity"><NavIcon name="chat" /><div><h2 id="assistant-title">Asistente EMOtv</h2><p>Te acompaño en cada pantalla</p></div></div>
        <button type="button" className="assistant-minimize" onClick={minimize} aria-label="Minimizar asistente">−</button>
      </header>
      <ChatConversation open={open} />
    </section>
    <button ref={launcherRef} type="button" className="assistant-launcher" aria-expanded={open} aria-controls="assistant-panel"
      onClick={() => open ? minimize() : setOpen(true)} aria-label={open ? "Minimizar asistente" : "Abrir asistente EMOtv"}>
      <NavIcon name="chat" /><span>Asistente EMOtv</span>
    </button>
  </aside>;
}
