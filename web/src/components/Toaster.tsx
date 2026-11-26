import { useEffect, useRef, useSyncExternalStore } from "react";

export type ToastTone = "success" | "error" | "info";

interface ToastItem {
  id: number;
  tone: ToastTone;
  text: string;
}

// Un aviso de éxito se lee en unos segundos; un error se queda más para que dé tiempo a leerlo.
const DURATION: Record<ToastTone, number> = { success: 5000, info: 5000, error: 9000 };
const MAX_VISIBLE = 3;

let items: ToastItem[] = [];
let nextId = 1;
const listeners = new Set<() => void>();

function emit() { for (const listener of listeners) listener(); }

function subscribe(listener: () => void) {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

function dismiss(id: number) {
  items = items.filter((item) => item.id !== id);
  emit();
}

function push(tone: ToastTone, text: string) {
  if (!text) return;
  // El mismo texto repetido no se apila: se reemplaza para que vuelva a contar el tiempo.
  items = [...items.filter((item) => item.text !== text), { id: nextId++, tone, text }].slice(-MAX_VISIBLE);
  emit();
}

/** Avisos breves que aparecen abajo y se cierran solos. Se pueden llamar desde cualquier página. */
export const toast = {
  success: (text: string) => push("success", text),
  error: (text: string) => push("error", text),
  info: (text: string) => push("info", text),
  /** Solo para pruebas: vacía la pila entre casos. */
  clear: () => { items = []; emit(); },
};

function ToastCard({ item }: { item: ToastItem }) {
  const timer = useRef<number | undefined>(undefined);
  const start = () => { timer.current = window.setTimeout(() => dismiss(item.id), DURATION[item.tone]); };
  const stop = () => window.clearTimeout(timer.current);
  useEffect(() => { start(); return stop; }, [item.id]); // eslint-disable-line react-hooks/exhaustive-deps

  return <div className={`toast toast-${item.tone}`} role={item.tone === "error" ? "alert" : "status"}
    onMouseEnter={stop} onMouseLeave={start} onFocus={stop} onBlur={start}>
    <span className="toast-icon" aria-hidden="true">{item.tone === "success" ? "✓" : item.tone === "error" ? "!" : "i"}</span>
    <p className="toast-text">{item.text}</p>
    <button type="button" className="toast-close" onClick={() => dismiss(item.id)} aria-label="Cerrar aviso">×</button>
  </div>;
}

/** Zona de avisos: se monta una sola vez, sobre todas las rutas. */
export function Toaster() {
  const current = useSyncExternalStore(subscribe, () => items, () => items);
  return <section className="toaster" aria-label="Avisos">
    {current.map((item) => <ToastCard key={item.id} item={item} />)}
  </section>;
}
