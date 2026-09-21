import { describe, expect, it, vi } from "vitest";
import { drawPoseOverlay } from "../src/analysis/drawPoseOverlay";

function surface() {
  const context = {
    clearRect: vi.fn(), beginPath: vi.fn(), moveTo: vi.fn(), lineTo: vi.fn(),
    stroke: vi.fn(), arc: vi.fn(), fill: vi.fn(),
  };
  const canvas = { width: 640, height: 480, getContext: () => context } as unknown as HTMLCanvasElement;
  return { canvas, context };
}

describe("superposición de pose", () => {
  it("une puntos corporales visibles y dibuja sus extremos", () => {
    const { canvas, context } = surface();
    drawPoseOverlay(canvas, {
      left_shoulder: { x: .25, y: .2, visibility: .9 },
      left_elbow: { x: .2, y: .4, visibility: .8 },
    });
    expect(context.moveTo).toHaveBeenCalledWith(160, 96);
    expect(context.lineTo).toHaveBeenCalledWith(128, 192);
    expect(context.stroke).toHaveBeenCalledTimes(1);
    expect(context.arc).toHaveBeenCalledTimes(2);
  });

  it("no une puntos poco visibles y borra el dibujo al desactivar", () => {
    const { canvas, context } = surface();
    const landmarks = {
      left_shoulder: { x: .25, y: .2, visibility: .9 },
      left_elbow: { x: .2, y: .4, visibility: .2 },
    };
    drawPoseOverlay(canvas, landmarks);
    expect(context.stroke).not.toHaveBeenCalled();
    expect(context.arc).toHaveBeenCalledTimes(1);
    drawPoseOverlay(canvas, landmarks, false);
    expect(context.clearRect).toHaveBeenCalledTimes(2);
    expect(context.arc).toHaveBeenCalledTimes(1);
  });
});
