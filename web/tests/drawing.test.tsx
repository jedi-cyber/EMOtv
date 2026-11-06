import { act, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DrawingActivity, DRAWING_EMOTIONS } from "../src/drawing/DrawingActivity";
import { MAX_POINTS, drawStroke, redraw, relativePoint, type Stroke } from "../src/drawing/strokes";
import { DrawingPage } from "../src/pages/DrawingPage";

// Bloque 4: dibujo táctil. El dibujo vive solo en la memoria de la pantalla.

class FakePointerEvent extends MouseEvent {
  pointerId: number;
  isPrimary: boolean;
  pointerType: string;
  coalesced: { clientX: number; clientY: number }[];
  constructor(type: string, init: PointerEventInit & { coalesced?: { clientX: number; clientY: number }[] } = {}) {
    super(type, init);
    this.pointerId = init.pointerId ?? 1;
    this.isPrimary = init.isPrimary ?? true;
    this.pointerType = init.pointerType ?? "touch";
    this.coalesced = init.coalesced ?? [];
  }
  /** Como el navegador: varios puntos de un mismo movimiento rápido. */
  getCoalescedEvents() { return this.coalesced; }
}

function fakeContext() {
  return {
    save: vi.fn(), restore: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(), stroke: vi.fn(),
    arc: vi.fn(), fill: vi.fn(), clearRect: vi.fn(),
    globalCompositeOperation: "source-over", strokeStyle: "", fillStyle: "", lineWidth: 1, lineCap: "butt", lineJoin: "miter",
  };
}

let ctx: ReturnType<typeof fakeContext>;
beforeEach(() => {
  ctx = fakeContext();
  vi.stubGlobal("PointerEvent", FakePointerEvent);
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockImplementation(() => ctx as never);
  // El lienzo mide 200 × 100 px en pantalla (jsdom no calcula tamaños).
  Object.defineProperty(HTMLCanvasElement.prototype, "clientWidth", { configurable: true, get: () => 200 });
  Object.defineProperty(HTMLCanvasElement.prototype, "clientHeight", { configurable: true, get: () => 100 });
  vi.spyOn(HTMLCanvasElement.prototype, "getBoundingClientRect").mockReturnValue(
    { left: 0, top: 0, width: 200, height: 100, right: 200, bottom: 100, x: 0, y: 0, toJSON: () => ({}) });
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  Reflect.deleteProperty(HTMLCanvasElement.prototype, "clientWidth");
  Reflect.deleteProperty(HTMLCanvasElement.prototype, "clientHeight");
});

function canvas() { return screen.getByRole("img", { name: /Lienzo/ }); }

/** Un trazo con el dedo: tocar, arrastrar y soltar. */
function stroke(target: HTMLElement, points: [number, number][], pointerId = 1, isPrimary = true) {
  const [first, ...rest] = points;
  fireEvent.pointerDown(target, { pointerId, isPrimary, clientX: first[0], clientY: first[1] });
  for (const [x, y] of rest) fireEvent.pointerMove(target, { pointerId, isPrimary, clientX: x, clientY: y });
  fireEvent.pointerUp(target, { pointerId, isPrimary, clientX: rest.at(-1)?.[0] ?? first[0], clientY: rest.at(-1)?.[1] ?? first[1] });
}

describe("trazos", () => {
  it("los puntos se guardan relativos al lienzo y dentro de él", () => {
    const rect = { left: 10, top: 20, width: 200, height: 100 };
    expect(relativePoint(110, 70, rect)).toEqual([0.5, 0.5]);
    expect(relativePoint(-50, 500, rect)).toEqual([0, 1]);
  });

  it("se redibujan a la escala del lienzo; el borrador quita tinta", () => {
    const pen: Stroke = { tool: "pen", color: "#000", width: 0.01, points: [[0, 0], [0.5, 0.5]] };
    const eraser: Stroke = { tool: "eraser", color: "#000", width: 0.01, points: [[0.5, 0.5], [1, 1]] };
    const operations: string[] = [];
    const recorder = { ...fakeContext() };
    recorder.stroke = vi.fn(() => { operations.push(recorder.globalCompositeOperation); });
    redraw(recorder as never, [pen, eraser], 400, 200);
    expect(recorder.clearRect).toHaveBeenCalledWith(0, 0, 400, 200);
    expect(recorder.lineTo).toHaveBeenCalledWith(200, 100);
    expect(operations).toEqual(["source-over", "destination-out"]);
  });

  it("un toque sin arrastrar deja un punto", () => {
    const recorder = fakeContext();
    drawStroke(recorder as never, { tool: "pen", color: "#000", width: 0.02, points: [[0.5, 0.5]] }, 100, 100);
    expect(recorder.arc).toHaveBeenCalledWith(50, 50, 1, 0, Math.PI * 2);
    expect(recorder.fill).toHaveBeenCalled();
  });
});

describe("actividad de dibujo", () => {
  it("el lienzo no desplaza la página al dibujar y el dedo dibuja", () => {
    render(<DrawingActivity />);
    expect(canvas()).toHaveClass("drawing-canvas");
    // touch-action: none está en la hoja de estilos; además se bloquea touchmove en el propio lienzo.
    const move = new Event("touchmove", { bubbles: true, cancelable: true });
    canvas().dispatchEvent(move);
    expect(move.defaultPrevented).toBe(true);
    stroke(canvas(), [[10, 10], [50, 40], [100, 50]]);
    expect(ctx.lineTo).toHaveBeenCalledWith(100, 50);
    expect(canvas()).toHaveAccessibleName("Lienzo con tu dibujo");
  });

  it("deshacer quita el último trazo; limpiar pide confirmación", async () => {
    render(<DrawingActivity />);
    const undo = screen.getByRole("button", { name: "Deshacer" });
    expect(undo).toBeDisabled();
    stroke(canvas(), [[10, 10], [20, 20]]);
    stroke(canvas(), [[30, 30], [40, 40]]);
    ctx.lineTo.mockClear();
    await userEvent.click(undo);
    // Se redibuja solo el primer trazo.
    expect(ctx.clearRect).toHaveBeenCalled();
    expect(ctx.lineTo).toHaveBeenCalledWith(20, 20);
    expect(ctx.lineTo).not.toHaveBeenCalledWith(40, 40);

    await userEvent.click(screen.getByRole("button", { name: "Limpiar" }));
    const dialog = screen.getByRole("alertdialog", { name: "Limpiar el lienzo" });
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancelar" }));
    expect(screen.getByRole("button", { name: "Deshacer" })).toBeEnabled();
    await userEvent.click(screen.getByRole("button", { name: "Limpiar" }));
    await userEvent.click(within(screen.getByRole("alertdialog")).getByRole("button", { name: "Limpiar" }));
    expect(screen.getByRole("button", { name: "Deshacer" })).toBeDisabled();
    expect(canvas()).toHaveAccessibleName(/Lienzo en blanco/);
  });

  it("colores con nombre, grosor y borrador se eligen y se marcan sin depender del color", async () => {
    render(<DrawingActivity />);
    const colors = screen.getByRole("group", { name: "Color" });
    await userEvent.click(within(colors).getByRole("button", { name: "Rojo" }));
    expect(within(colors).getByRole("button", { name: "Rojo" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(within(screen.getByRole("group", { name: "Grosor" })).getByRole("button", { name: "Grueso" }));
    stroke(canvas(), [[0, 0], [100, 100]]);
    expect(ctx.strokeStyle).toBe("#cf222e");
    expect(ctx.lineWidth).toBeCloseTo(0.035 * 100);
    await userEvent.click(screen.getByRole("button", { name: "Borrador" }));
    expect(screen.getByRole("button", { name: "Borrador" })).toHaveAttribute("aria-pressed", "true");
    expect(within(colors).getByRole("button", { name: "Rojo" })).toHaveAttribute("aria-pressed", "false");
    const operations: string[] = [];
    ctx.stroke.mockImplementation(() => { operations.push(ctx.globalCompositeOperation); });
    stroke(canvas(), [[0, 0], [50, 50]]);
    expect(operations).toContain("destination-out");
  });

  it("un segundo dedo (o la palma) no dibuja mientras el primero dibuja", () => {
    render(<DrawingActivity />);
    fireEvent.pointerDown(canvas(), { pointerId: 1, clientX: 10, clientY: 10 });
    fireEvent.pointerDown(canvas(), { pointerId: 2, isPrimary: false, clientX: 150, clientY: 90 });
    fireEvent.pointerMove(canvas(), { pointerId: 2, isPrimary: false, clientX: 160, clientY: 95 });
    fireEvent.pointerMove(canvas(), { pointerId: 1, clientX: 20, clientY: 20 });
    fireEvent.pointerUp(canvas(), { pointerId: 1, clientX: 20, clientY: 20 });
    expect(ctx.lineTo).not.toHaveBeenCalledWith(160, 95);
    expect(ctx.lineTo).toHaveBeenCalledWith(20, 20);
  });

  it("terminar, señalar la emoción y dibujar otra vez; no se clasifica ni se envía nada", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const storage = vi.spyOn(Storage.prototype, "setItem");
    render(<DrawingActivity />);
    expect(screen.getByRole("button", { name: "Terminé" })).toBeDisabled();
    stroke(canvas(), [[10, 10], [60, 60]]);
    await userEvent.click(screen.getByRole("button", { name: "Terminé" }));
    expect(screen.getByText("¿Qué emoción quisiste dibujar?")).toBeInTheDocument();
    expect(screen.getAllByRole("button").filter((item) => item.classList.contains("recognition-option"))).toHaveLength(DRAWING_EMOTIONS.length);
    // Mientras elige, el lienzo no dibuja.
    ctx.lineTo.mockClear();
    stroke(canvas(), [[100, 10], [150, 60]]);
    expect(ctx.lineTo).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: /Alegría/ }));
    expect(screen.getByRole("status")).toHaveTextContent("Dibujaste alegría.");
    expect(screen.queryByText(/coincid|correct|bien|mal/i)).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Dibujar otra vez" }));
    expect(canvas()).toHaveAccessibleName(/Lienzo en blanco/);
    expect(screen.getByRole("button", { name: "Terminé" })).toBeDisabled();
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(storage).not.toHaveBeenCalled();
  });

  it("«Seguir dibujando» vuelve al lienzo con el dibujo", async () => {
    render(<DrawingActivity />);
    stroke(canvas(), [[10, 10], [60, 60]]);
    await userEvent.click(screen.getByRole("button", { name: "Terminé" }));
    await userEvent.click(screen.getByRole("button", { name: "Seguir dibujando" }));
    expect(screen.getByRole("button", { name: "Deshacer" })).toBeEnabled();
  });

  it("la memoria tiene tope: pasado el máximo de puntos no se agregan más", () => {
    render(<DrawingActivity />);
    fireEvent.pointerDown(canvas(), { pointerId: 1, clientX: 0, clientY: 0 });
    const many = Array.from({ length: MAX_POINTS + 50 }, (_, index) => ({ clientX: index % 200, clientY: 50 }));
    ctx.lineTo.mockClear();
    fireEvent.pointerMove(canvas(), { pointerId: 1, clientX: 0, clientY: 50, coalesced: many } as never);
    // El trazo llega hasta el tope: el punto inicial y MAX_POINTS - 1 más.
    expect(ctx.lineTo).toHaveBeenCalledTimes(MAX_POINTS - 1);
    ctx.lineTo.mockClear();
    fireEvent.pointerMove(canvas(), { pointerId: 1, clientX: 199, clientY: 99 });
    expect(ctx.lineTo).not.toHaveBeenCalled();
    fireEvent.pointerUp(canvas(), { pointerId: 1 });
    // Un trazo nuevo tampoco empieza.
    ctx.arc.mockClear();
    fireEvent.pointerDown(canvas(), { pointerId: 2, clientX: 5, clientY: 5 });
    expect(ctx.arc).not.toHaveBeenCalled();
  });
});

describe("salida accidental", () => {
  function page() {
    const router = createMemoryRouter([
      { path: "/drawing", element: <DrawingPage /> },
      { path: "/analysis", element: <p>Analizador</p> },
    ], { initialEntries: ["/drawing"] });
    render(<RouterProvider router={router} />);
    return router;
  }

  it("sin dibujo, salir no pregunta", async () => {
    const router = page();
    await userEvent.click(screen.getByRole("button", { name: "Salir" }));
    expect(router.state.location.pathname).toBe("/analysis");
  });

  it("con un dibujo, salir pide confirmación y avisa que se borra; cerrar la pestaña también avisa", async () => {
    const router = page();
    stroke(canvas(), [[10, 10], [60, 60]]);
    const unload = new Event("beforeunload", { cancelable: true });
    act(() => { window.dispatchEvent(unload); });
    expect(unload.defaultPrevented).toBe(true);

    await userEvent.click(screen.getByRole("button", { name: "Salir" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Salir del dibujo" });
    expect(dialog).toHaveTextContent("el dibujo se borra");
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancelar" }));
    expect(router.state.location.pathname).toBe("/drawing");
    await userEvent.click(screen.getByRole("button", { name: "Salir" }));
    await userEvent.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Salir y borrar" }));
    expect(await screen.findByText("Analizador")).toBeInTheDocument();
  });
});
