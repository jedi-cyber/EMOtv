import { FormEvent, useEffect, useRef, useState } from "react";
import { apiRequest, ApiError } from "../api/http";
import { useAuth } from "../auth/useAuth";
import { Alert } from "../components/Alert";

interface Message { role: "user" | "assistant"; text: string }

export function ChatConversation({ open }: { open: boolean }) {
  const { token } = useAuth();
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const messagesRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    if (open) inputRef.current?.focus();
  }, [open]);
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
      const result = await apiRequest<{ answer: string }>("/chat", {
        method: "POST", token, body: JSON.stringify({ question: text }),
      });
      setMessages((current) => [...current, { role: "assistant", text: result.answer }]);
    } catch (reason) {
      setError(reason instanceof ApiError ? reason.message : "No se pudo consultar al asistente");
    } finally { setSending(false); }
  }

  return <div className="chat-panel">
      <Alert variant="info">Este asistente ofrece orientación sobre EMOtv; no reemplaza la atención psicológica ni los servicios de emergencia.</Alert>
      <div ref={messagesRef} className="chat-messages" role="log" aria-label="Conversación con el asistente" aria-live="polite">
        {messages.length === 0 && <div className="assistant-welcome"><strong>Hola, soy tu asistente EMOtv</strong><p>Puedo orientarte sobre la plataforma y sus actividades. ¿En qué te ayudo?</p></div>}
        {messages.map((message, index) => <div key={index} className={`chat-message ${message.role}`}>
          <strong>{message.role === "user" ? "Tú" : "Asistente"}</strong><p>{message.text}</p>
        </div>)}
        {sending && <p role="status" className="muted">El asistente está respondiendo…</p>}
      </div>
      {error && <Alert variant="error">{error}</Alert>}
      <form className="chat-form" onSubmit={send}>
        <label htmlFor="chat-question">Tu pregunta</label>
        <textarea ref={inputRef} id="chat-question" value={question} maxLength={2000} rows={3} aria-busy={sending}
          onChange={(event) => setQuestion(event.target.value)} placeholder="¿Cómo funciona una actividad?" />
        <button className="button primary" disabled={sending || !question.trim()}>{sending ? "Enviando…" : "Enviar"}</button>
      </form>
    </div>;
}
