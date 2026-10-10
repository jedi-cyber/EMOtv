import { FormEvent, useEffect, useRef, useState } from "react";
import { apiRequest, ApiError } from "../api/http";
import { useAuth } from "../auth/useAuth";
import { Alert } from "../components/Alert";
import type { AssistantDraft } from "./AssistantContext";

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
    setQuestion(""); setSending(true); setError(null);
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

  async function newConversation() {
    if (sending || starting) return;
    setStarting(true); setError(null);
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
      <Alert variant="info">Emi ofrece orientación educativa sobre EMOtv; no reemplaza la atención psicológica ni los servicios de emergencia.</Alert>
      <div className="inline-actions">
        <button type="button" className="button secondary" disabled={sending || starting} onClick={() => { void newConversation(); }}>Nueva conversación</button>
      </div>
      <div ref={messagesRef} className="chat-messages" role="log" aria-label="Conversación con Emi" aria-live="polite">
        {messages.length === 0 && <div className="assistant-welcome"><strong>Hola, soy Emi</strong><p>Puedo orientarte sobre la plataforma, sus actividades y las expresiones faciales. ¿En qué te ayudo?</p></div>}
        {messages.map((message, index) => <div key={index} className={`chat-message ${message.role}`}>
          <strong>{message.role === "user" ? "Tú" : "Emi"}</strong><p>{message.text}</p>
        </div>)}
        {sending && <p role="status" className="muted">Emi está escribiendo… La respuesta puede tardar unos segundos.</p>}
      </div>
      {error && <Alert variant="error">{error}</Alert>}
      <form className="chat-form" onSubmit={send}>
        <label htmlFor="chat-question">Tu pregunta</label>
        <textarea ref={inputRef} id="chat-question" value={question} maxLength={MAX_QUESTION_CHARS} rows={3} aria-busy={sending}
          onChange={(event) => setQuestion(event.target.value)} placeholder="¿Cómo funciona una actividad?" />
        <button className="button primary" disabled={sending || !question.trim()}>{sending ? "Enviando…" : "Enviar"}</button>
      </form>
    </div>;
}
