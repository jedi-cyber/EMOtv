// Traducción provisional de las claves del modelo; se reemplazará por el catálogo de expresiones.
const expressionNames: Record<string, string> = {
  neutral: "Neutral",
  happiness: "Felicidad",
  surprise: "Sorpresa",
  sadness: "Tristeza",
  anger: "Enojo",
  disgust: "Desagrado",
  fear: "Miedo",
  contempt: "Desprecio",
};

export function expressionName(key: string | null | undefined): string {
  if (!key) return "—";
  return expressionNames[key] ?? key;
}
