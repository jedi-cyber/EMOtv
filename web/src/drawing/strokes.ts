/**
 * Trazos del dibujo táctil, solo en la memoria de la página. Cada punto se
 * guarda relativo al lienzo (de 0 a 1) para que el dibujo se adapte si la
 * pantalla gira o cambia de tamaño. Nada de esto se envía ni se guarda.
 */

export type DrawingTool = "pen" | "eraser";

export interface Stroke {
  tool: DrawingTool;
  color: string;
  /** Grosor relativo al lado menor del lienzo. */
  width: number;
  points: [number, number][];
}

export interface InkColor { key: string; name: string; value: string }

/** Cada color lleva su nombre: la elección no depende solo de verlo. */
export const INK_COLORS: InkColor[] = [
  { key: "black", name: "Negro", value: "#1f2328" },
  { key: "red", name: "Rojo", value: "#cf222e" },
  { key: "blue", name: "Azul", value: "#0969da" },
  { key: "green", name: "Verde", value: "#1a7f37" },
  { key: "yellow", name: "Amarillo", value: "#d4a72c" },
  { key: "purple", name: "Morado", value: "#8250df" },
  { key: "brown", name: "Café", value: "#8a5a2b" },
];

export interface InkSize { key: string; name: string; width: number }

export const INK_SIZES: InkSize[] = [
  { key: "thin", name: "Fino", width: 0.008 },
  { key: "medium", name: "Medio", width: 0.018 },
  { key: "thick", name: "Grueso", width: 0.035 },
];

/** El borrador es más ancho que el lápiz del mismo grosor. */
export const ERASER_FACTOR = 2.5;

/** Tope de puntos por dibujo: la memoria no crece sin límite. */
export const MAX_POINTS = 40000;

export function pointCount(strokes: Stroke[]): number {
  return strokes.reduce((total, stroke) => total + stroke.points.length, 0);
}

/** Un punto de la pantalla, relativo al lienzo y dentro de él. */
export function relativePoint(clientX: number, clientY: number, rect: { left: number; top: number; width: number; height: number }): [number, number] {
  const clamp = (value: number) => Math.min(1, Math.max(0, value));
  return [clamp((clientX - rect.left) / (rect.width || 1)), clamp((clientY - rect.top) / (rect.height || 1))];
}

/** Dibuja un trazo completo (o su último tramo, con from) en un lienzo de width × height píxeles. */
export function drawStroke(ctx: CanvasRenderingContext2D, stroke: Stroke, width: number, height: number, from = 0): void {
  const points = stroke.points;
  if (points.length === 0) return;
  const size = Math.max(1, stroke.width * Math.min(width, height) * (stroke.tool === "eraser" ? ERASER_FACTOR : 1));
  ctx.save();
  ctx.globalCompositeOperation = stroke.tool === "eraser" ? "destination-out" : "source-over";
  ctx.strokeStyle = stroke.color;
  ctx.fillStyle = stroke.color;
  ctx.lineWidth = size;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  const start = Math.max(0, from - 1);
  if (points.length === 1 || points.length - start === 1) {
    // Un toque sin arrastrar deja un punto.
    const [x, y] = points[points.length - 1];
    ctx.beginPath();
    ctx.arc(x * width, y * height, size / 2, 0, Math.PI * 2);
    ctx.fill();
  } else {
    ctx.beginPath();
    ctx.moveTo(points[start][0] * width, points[start][1] * height);
    for (let index = start + 1; index < points.length; index += 1) {
      ctx.lineTo(points[index][0] * width, points[index][1] * height);
    }
    ctx.stroke();
  }
  ctx.restore();
}

/** Borra el lienzo y vuelve a dibujar todos los trazos (deshacer, girar la pantalla). */
export function redraw(ctx: CanvasRenderingContext2D, strokes: Stroke[], width: number, height: number): void {
  ctx.clearRect(0, 0, width, height);
  for (const stroke of strokes) drawStroke(ctx, stroke, width, height);
}
