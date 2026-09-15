const API_URL = import.meta.env.VITE_API_URL?.replace(/\/$/, "") ?? "";
export const AUTH_UNAUTHORIZED_EVENT = "emotv:auth-unauthorized";

export function apiWebSocketUrl(path: string): string {
  if (API_URL) {
    return `${API_URL.replace(/^http/, "ws")}${path}`;
  }
  const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${protocol}//${window.location.host}${path}`;
}

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

type RequestOptions = RequestInit & { token?: string | null };

export async function apiRequest<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const { token, headers, ...request } = options;
  const hasJsonBody =
    request.body != null &&
    !(request.body instanceof FormData) &&
    !(request.body instanceof URLSearchParams);
  const response = await fetch(`${API_URL}${path}`, {
    ...request,
    headers: {
      Accept: "application/json",
      ...(hasJsonBody ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
  });

  if (!response.ok) {
    const body = (await response.json().catch(() => null)) as
      | { detail?: string }
      | null;
    if (response.status === 401 && token) {
      window.dispatchEvent(new Event(AUTH_UNAUTHORIZED_EVENT));
    }
    throw new ApiError(response.status, body?.detail ?? "No se pudo completar la solicitud");
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}
