import { describe, expect, it, vi } from "vitest";
import { apiRequest, ApiError, AUTH_UNAUTHORIZED_EVENT, apiWebSocketUrl } from "../src/api/http";

describe("contrato HTTP del frontend", () => {
  it("envía Bearer y JSON", async () => {
    const fetcher = vi.fn().mockResolvedValue(new Response(JSON.stringify({ id: "s" }), { status: 201 }));
    vi.stubGlobal("fetch", fetcher);
    expect(await apiRequest("/sessions", { method: "POST", body: "{}", token: "test" })).toEqual({ id: "s" });
    expect(fetcher).toHaveBeenCalledWith("/sessions", expect.objectContaining({ headers: expect.objectContaining({ Authorization: "Bearer test", "Content-Type": "application/json" }) }));
  });
  it("notifica vencimiento y conserva el error de consentimiento", async () => {
    const listener = vi.fn(); window.addEventListener(AUTH_UNAUTHORIZED_EVENT, listener);
    vi.stubGlobal("fetch", vi.fn().mockResolvedValueOnce(new Response('{"detail":"Token vencido"}', { status: 401 })).mockResolvedValueOnce(new Response('{"detail":"Consentimiento requerido"}', { status: 403 })));
    await expect(apiRequest("/auth/me", { token: "old" })).rejects.toBeInstanceOf(ApiError);
    expect(listener).toHaveBeenCalledOnce();
    await expect(apiRequest("/sessions", { token: "test" })).rejects.toThrow("Consentimiento requerido");
    window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, listener);
  });
  it("interpreta 204 y usa el mismo host para WebSocket", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    expect(await apiRequest("/activities/a", { method: "DELETE" })).toBeUndefined();
    expect(apiWebSocketUrl("/ws/activity")).toMatch(/^ws:\/\/.+\/ws\/activity$/);
  });
});
