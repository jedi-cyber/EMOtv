// El enlace de la vista del participante se entrega una sola vez; se guarda en
// esta pestaña para poder abrirlo de nuevo. No contiene datos del participante.
const key = (sessionId: string) => `emotv:participant-view:${sessionId}`;

export function storeViewToken(sessionId: string, token: string) {
  try { sessionStorage.setItem(key(sessionId), token); } catch { /* sin almacenamiento: se genera otro enlace */ }
}

export function readViewToken(sessionId: string): string | null {
  try { return sessionStorage.getItem(key(sessionId)); } catch { return null; }
}
