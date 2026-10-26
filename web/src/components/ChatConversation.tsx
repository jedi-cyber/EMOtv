import { FormEvent, useEffect, useRef, useState } from "react";
import { apiRequest, ApiError } from "../api/http";
import { useAuth } from "../auth/useAuth";
import { Callout } from "../components/Callout";
import type { AssistantDraft } from "./AssistantContext";
import { Button } from "./Button";

interface Message { role: "user" | "assistant"; text: string }
interface StoredConversation { conversation_id: string | null; messages?: { role: "user" | "assistant"; content: string }[] }
interface ChatAnswer { conversation_id: string | null; answer: string; in_scope?: boolean }

/** Coincide con CHAT_MAX_QUESTION_CHARS del servidor (valor por defecto). */
const MAX_QUESTION_CHARS = 1000;

function errorMessage(reason: unknown): string {
  if (!(reason instanceof ApiError)) return "No se pudo consultar a Emi. Revisa tu conexión e intenta de nuevo.";
  if (reason.status === 429) return reason.message || "Enviaste muchos mensajes seguidos. Espera unos minutos.";
  if (reason.status === 503) return reason.message || "Emi no está disponible en este momento.";
  return reason.message || "No se pudo consultar a Emi.";
}

export function ChatConversation({ open, draft = null }: { open: boolean; draft?: AssistantDraft | null }) {
  const { token } = useAuth();
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const historyRequested = useRef(false);
  const [sending, setSending] = useState(false);
  const [starting, setStarting] = useState(false);
  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const messagesRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);
  // El historial se carga la primera vez que se abre a Emi.
  useEffect(() => {
    if (!open || historyRequested.current || !token) return;
    historyRequested.current = true;
    apiRequest<StoredConversation>("/chat/conversations/current", { token })
      .then((stored) => {
        if (!stored) return;
        // Si la persona ya empezó a escribir, su conversación en curso prevalece.
        setConversationId((current) => current ?? stored.conversation_id ?? null);
        setMessages((current) => current.length ? current
          : (stored.messages ?? []).map((item) => ({ role: item.role, text: item.content })));
      })
      .catch((reason) => setError(errorMessage(reason)));
  }, [open, token]);
  // Una pregunta sugerida solo rellena el campo; la persona la edita y decide si enviarla.
  useEffect(() => {
    if (draft) { setQuestion(draft.text); inputRef.current?.focus(); }
  }, [draft]);
  useEffect(() => {
    const container = messagesRef.current;
    if (open && container) container.scrollTop = container.scrollHeight;
  }, [messages, sending, open]);

  async function send(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || sending) return;
    setMessages((current) => [...current, { role: "user", text }]);
    setQuestion(""); setSending(true); setError(null); setNotice(null);
    try {
      const body = conversationId ? { conversation_id: conversationId, question: text } : { question: text };
      const result = await apiRequest<ChatAnswer>("/chat", { method: "POST", token, body: JSON.stringify(body) });
      if (result.conversation_id) setConversationId(result.conversation_id);
      setMessages((current) => [...current, { role: "assistant", text: result.answer }]);
    } catch (reason) {
      // La pregunta no se perdió: vuelve al campo para reenviarla cuando se pueda.
      setMessages((current) => current.slice(0, -1));
      setQuestion(text);
      setError(errorMessage(reason));
    } finally { setSending(false); }
  }

  async function deleteConversation() {
    if (sending || starting) return;
    setStarting(true); setError(null);
    try {
      // Sin conversación guardada (por ejemplo, solo mensajes bloqueados por los filtros) basta con limpiar la vista.
      if (conversationId) await apiRequest(`/chat/conversations/${encodeURIComponent(conversationId)}`, { method: "DELETE", token });
      setConversationId(null);
      setMessages([]);
      setNotice("Conversación borrada.");
      inputRef.current?.focus();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally { setStarting(false); setConfirmingDelete(false); }
  }

  async function newConversation() {
    if (sending || starting) return;
    setStarting(true); setError(null); setNotice(null);
    try {
      const created = await apiRequest<StoredConversation>("/chat/conversations", { method: "POST", token });
      setConversationId(created.conversation_id ?? null);
      setMessages([]);
      inputRef.current?.focus();
    } catch (reason) {
      setError(errorMessage(reason));
    } finally { setStarting(false); }
  }

  return <div className="chat-panel">
      <div className="chat-toolbar">
        <Button variant="secondary" size="sm" type="button" disabled={sending || starting} onClick={() => { void newConversation(); }}>Nueva conversación</Button>
        {!confirmingDelete && <Button variant="ghost" size="sm" type="button" disabled={sending || starting || (!conversationId && messages.length === 0)}
          onClick={() => { setConfirmingDelete(true); setNotice(null); }}>Borrar conversación</Button>}
      </div>
      {confirmingDelete && <div className="chat-toolbar" role="group" aria-label="Confirmar borrado">
        <span>¿Borrar esta conversación? No se puede recuperar.</span>
        <Button variant="danger" size="sm" type="button" disabled={starting} onClick={() => { void deleteConversation(); }}>Sí, borrar</Button>
        <Button variant="ghost" size="sm" type="button" disabled={starting} onClick={() => setConfirmingDelete(false)}>Cancelar</Button>
      </div>}
      {notice && <p role="status" className="muted">{notice}</p>}
      <div ref={messagesRef} className="chat-messages" role="log" aria-label="Conversación con Emi" aria-live="polite">
        {/* Encabeza el historial y se desplaza con él, para dejar espacio a la conversación. */}
        <p className="chat-disclaimer" role="note">Emi ofrece orientación educativa sobre Psicología y EMOtv; no diagnostica a nadie ni reemplaza a tu docente, la atención psicológica o los servicios de emergencia.</p>
        {messages.length === 0 && <div className="assistant-welcome"><strong>Hola, soy Emi</strong><p>Puedo orientarte sobre Psicología en general, la evaluación infantil y el uso de EMOtv. ¿En qué te ayudo?</p></div>}
        {messages.map((message, index) => <div key={index} className={`chat-message ${message.role}`}>
          <strong>{message.role === "user" ? "Tú" : "Emi"}</strong><p>{message.text}</p>
        </div>)}
        {sending && <p role="status" className="muted">Emi está escribiendo… La respuesta puede tardar unos segundos.</p>}
      </div>
      {error && <Callout variant="error">{error}</Callout>}
      <form className="chat-form" onSubmit={send}>
        {/* Aviso permanente junto al campo: el servidor además rechaza DNI, correos y teléfonos antes de llamar al asistente. */}
        <p className="chat-privacy" role="note" id="chat-privacy">No escribas nombres ni datos de niños o familias. Si describes un caso, hazlo sin datos que identifiquen a la persona.</p>
        <label htmlFor="chat-question" className="sr-only">Tu pregunta</label>
        <div className="chat-compose">
          <textarea ref={inputRef} id="chat-question" value={question} maxLength={MAX_QUESTION_CHARS} rows={2} aria-busy={sending}
            aria-describedby="chat-privacy" onChange={(event) => setQuestion(event.target.value)} placeholder="Escribe tu pregunta…" />
          <Button variant="primary" type="submit" disabled={sending || !question.trim()}>{sending ? "Enviando…" : "Enviar"}</Button>
        </div>
      </form>
    </div>;
}
