export type PoseLandmark = { x: number; y: number; visibility: number };
export type PoseLandmarks = Record<string, PoseLandmark>;

const connections = [
  ["left_shoulder", "right_shoulder"],
  ["left_shoulder", "left_elbow"], ["left_elbow", "left_wrist"],
  ["right_shoulder", "right_elbow"], ["right_elbow", "right_wrist"],
  ["left_shoulder", "left_hip"], ["right_shoulder", "right_hip"],
  ["left_hip", "right_hip"],
  ["left_hip", "left_knee"], ["left_knee", "left_ankle"],
  ["right_hip", "right_knee"], ["right_knee", "right_ankle"],
] as const;

const MIN_VISIBILITY = 0.5;

function visible(point: PoseLandmark | undefined): point is PoseLandmark {
  return point !== undefined && Number.isFinite(point.x) && Number.isFinite(point.y)
    && Number.isFinite(point.visibility) && point.visibility >= MIN_VISIBILITY;
}

/** Solo dibuja puntos y segmentos fiables; no interviene en la validación. */
export function drawPoseOverlay(
  canvas: HTMLCanvasElement | null,
  landmarks: PoseLandmarks | null | undefined,
  enabled = true,
): void {
  const context = canvas?.getContext("2d");
  if (!canvas || !context) return;
  context.clearRect(0, 0, canvas.width, canvas.height);
  if (!enabled || !landmarks) return;

  context.strokeStyle = "#5ef0ad";
  context.lineWidth = 3;
  for (const [from, to] of connections) {
    const start = landmarks[from];
    const end = landmarks[to];
    if (!visible(start) || !visible(end)) continue;
    context.beginPath();
    context.moveTo(start.x * canvas.width, start.y * canvas.height);
    context.lineTo(end.x * canvas.width, end.y * canvas.height);
    context.stroke();
  }

  context.fillStyle = "#ffffff";
  for (const point of Object.values(landmarks)) {
    if (!visible(point)) continue;
    context.beginPath();
    context.arc(point.x * canvas.width, point.y * canvas.height, 4, 0, Math.PI * 2);
    context.fill();
  }
}
