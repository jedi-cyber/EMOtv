import { createContext, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { PropsWithChildren } from "react";
import { AUTH_UNAUTHORIZED_EVENT, ApiError, apiRequest } from "../api/http";
import { tokenStorage } from "./tokenStorage";
import type { CurrentUser, TokenResponse } from "./types";

interface AuthContextValue {
  user: CurrentUser | null;
  token: string | null;
  loading: boolean;
  notice: string;
  login(email: string, password: string): Promise<void>;
  logout(notice?: string): void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: PropsWithChildren) {
  const [token, setToken] = useState<string | null>(() => tokenStorage.get());
  const [user, setUser] = useState<CurrentUser | null>(null);
  const [loading, setLoading] = useState(Boolean(token));
  const [notice, setNotice] = useState("");
  const generation = useRef(0);

  const logout = useCallback((message = "") => {
    generation.current += 1;
    tokenStorage.clear();
    setToken(null);
    setUser(null);
    setNotice(message);
  }, []);

  useEffect(() => {
    const handleUnauthorized = () => logout("Tu sesión venció. Ingresa nuevamente.");
    window.addEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
    return () => window.removeEventListener(AUTH_UNAUTHORIZED_EVENT, handleUnauthorized);
  }, [logout]);

  useEffect(() => {
    if (!token) return;
    try {
      const encodedPayload = token.split(".")[1].replace(/-/g, "+").replace(/_/g, "/");
      const paddedPayload = encodedPayload.padEnd(
        encodedPayload.length + ((4 - encodedPayload.length % 4) % 4),
        "=",
      );
      const payload = JSON.parse(atob(paddedPayload)) as { exp?: number };
      if (!payload.exp) return;
      const remaining = payload.exp * 1000 - Date.now();
      if (remaining <= 0) {
        logout("Tu sesión venció. Ingresa nuevamente.");
        return;
      }
      const timer = window.setTimeout(
        () => logout("Tu sesión venció. Ingresa nuevamente."),
        remaining,
      );
      return () => window.clearTimeout(timer);
    } catch {
      logout("La sesión almacenada no es válida. Ingresa nuevamente.");
    }
  }, [logout, token]);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      return;
    }
    setLoading(true);
    let active = true;
    apiRequest<CurrentUser>("/auth/me", { token })
      .then((current) => { if (active) setUser(current); })
      .catch((reason: unknown) => { if (active) logout(
        reason instanceof ApiError && reason.status === 401
          ? "Tu sesión venció. Ingresa nuevamente."
          : "No fue posible verificar la sesión. Ingresa nuevamente.",
      ); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [logout, token]);

  const login = useCallback(async (email: string, password: string) => {
    const attempt = ++generation.current;
    setNotice("");
    const form = new URLSearchParams({ username: email, password });
    const result = await apiRequest<TokenResponse>("/auth/token", {
      method: "POST",
      body: form,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    if (attempt !== generation.current) return;
    const currentUser = await apiRequest<CurrentUser>("/auth/me", {
      token: result.access_token,
    });
    if (attempt !== generation.current) return;
    tokenStorage.set(result.access_token);
    setToken(result.access_token);
    setUser(currentUser);
  }, []);

  const value = useMemo(
    () => ({ user, token, loading, notice, login, logout }),
    [user, token, loading, notice, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
