import { createContext, useContext, useMemo } from "react";
import type { ReactNode } from "react";
import { useApiQuery } from "../api/useApiQuery";
import { useAuth } from "../auth/useAuth";

export interface ExpressionInfo {
  expression_key: string;
  label_es: string;
  what_it_is: string;
  why_it_occurs: string;
  facial_cues: string;
  practice_tip: string;
  limitation_note: string;
  common_limitation: string;
  review_status: "draft" | "reviewed";
  reviewed_by_user_id: string | null;
  reviewed_at: string | null;
  updated_at: string;
}

export const COMMON_LIMITATION =
  "El reconocimiento facial estima una expresión a partir de la imagen y no determina por sí mismo el estado emocional ni psicológico de la persona.";

// Respaldo si la API no responde: solo etiquetas, nunca textos educativos inventados.
const FALLBACK_LABELS: Record<string, string> = {
  neutral: "Neutral",
  happiness: "Felicidad",
  surprise: "Sorpresa",
  sadness: "Tristeza",
  anger: "Enojo",
  disgust: "Desagrado",
  fear: "Miedo",
  contempt: "Desprecio",
};

interface ExpressionCatalogValue {
  items: ExpressionInfo[];
  info: (key: string | null | undefined) => ExpressionInfo | null;
  label: (key: string | null | undefined) => string;
  reload: () => Promise<void>;
}

function build(items: ExpressionInfo[], reload: () => Promise<void>): ExpressionCatalogValue {
  const byKey = new Map(items.map((item) => [item.expression_key, item]));
  return {
    items,
    reload,
    info: (key) => (key ? byKey.get(key) ?? null : null),
    label: (key) => {
      if (!key) return "—";
      return byKey.get(key)?.label_es ?? FALLBACK_LABELS[key] ?? key;
    },
  };
}

const fallbackCatalog = build([], async () => undefined);
const ExpressionCatalogContext = createContext<ExpressionCatalogValue>(fallbackCatalog);

/** Carga una vez el catálogo para traducir etiquetas en toda la interfaz. */
export function ExpressionCatalogProvider({ children }: { children: ReactNode }) {
  const { token, user } = useAuth();
  const query = useApiQuery<ExpressionInfo[]>(token && user ? "/expressions" : null);
  const items = query.data;
  const value = useMemo(() => build(Array.isArray(items) ? items : [], query.reload), [items, query.reload]);
  return <ExpressionCatalogContext.Provider value={value}>{children}</ExpressionCatalogContext.Provider>;
}

export function useExpressionCatalog(): ExpressionCatalogValue {
  return useContext(ExpressionCatalogContext);
}

// Preguntas generales para Emi: nunca incluyen confianza, fecha ni datos de la sesión.
const EMI_QUESTIONS: Record<string, string> = {
  neutral: "¿Cómo se distingue en el rostro una expresión neutral de una tristeza leve?",
  happiness: "¿Cómo se diferencia en el rostro una sonrisa espontánea de una sonrisa de cortesía?",
  surprise: "¿Qué diferencia hay entre la sorpresa y el miedo en el rostro?",
  sadness: "¿Qué es la tristeza y cómo se reconoce en el rostro?",
  anger: "¿Cómo se reconoce el enojo en el rostro?",
  disgust: "¿Qué diferencia hay entre el desagrado y el desprecio en el rostro?",
  fear: "¿Qué diferencia hay entre el miedo y la sorpresa en el rostro?",
  contempt: "¿Qué es el desprecio y cómo se reconoce en el rostro?",
};

export function emiQuestionFor(key: string, label: string): string {
  return EMI_QUESTIONS[key] ?? `¿Cómo se reconoce en el rostro la expresión «${label}»?`;
}
