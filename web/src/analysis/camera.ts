/** Motivo por el que no se pudo abrir la cámara, deducido del error de getUserMedia. */
export type CameraProblem = "insecure" | "denied" | "busy" | "not_found" | "unknown";

export const cameraProblemMessages: Record<CameraProblem, string> = {
  insecure: "La cámara solo funciona en una conexión segura. Abre EMOtv con una dirección https:// (o en localhost si estás probando en este equipo).",
  denied: "El navegador bloqueó la cámara. Pulsa el icono de la cámara o del candado junto a la dirección, elige «Permitir» y vuelve a probar.",
  busy: "Otra aplicación está usando la cámara. Cierra las videollamadas u otras pestañas que la usen y vuelve a probar.",
  not_found: "No encontramos ninguna cámara. Conecta una cámara o revisa que esté activada y vuelve a probar.",
  unknown: "No se pudo abrir la cámara. Vuelve a probar; si continúa, reinicia el navegador.",
};

/** Sin contexto seguro (HTTPS o localhost) el navegador no expone getUserMedia. */
export function cameraUnavailableReason(): CameraProblem | null {
  if (typeof window !== "undefined" && window.isSecureContext === false) return "insecure";
  if (!navigator.mediaDevices?.getUserMedia) return "insecure";
  return null;
}

export function cameraProblem(reason: unknown): CameraProblem {
  const name = reason instanceof DOMException || reason instanceof Error ? reason.name : "";
  switch (name) {
    case "NotAllowedError":
    case "PermissionDeniedError":
      return "denied";
    case "SecurityError":
      return "insecure";
    case "NotReadableError":
    case "TrackStartError":
    case "AbortError":
      return "busy";
    case "NotFoundError":
    case "DevicesNotFoundError":
    case "OverconstrainedError":
    case "ConstraintNotSatisfiedError":
      return "not_found";
    default:
      return "unknown";
  }
}

export function cameraErrorMessage(reason: unknown): string {
  return cameraProblemMessages[cameraProblem(reason)];
}

/** Detiene todas las pistas del MediaStream: el indicador de cámara del sistema se apaga. */
export function stopStream(stream: MediaStream | null | undefined) {
  stream?.getTracks().forEach((track) => track.stop());
}
