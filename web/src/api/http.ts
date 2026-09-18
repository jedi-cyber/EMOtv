const API_URL = import.meta.env.VITE_API_URL?.replace(/\/$/, "") ?? "";
export const AUTH_UNAUTHORIZED_EVENT = "emotv:auth-unauthorized";
export const API_UNAVAILABLE_EVENT = "emotv:api-unavailable";
export const API_RECOVERED_EVENT = "emotv:api-recovered";

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

export function isConnectionError(reason: unknown): reason is ApiError {
  return reason instanceof ApiError && (reason.status === 0 || reason.status >= 500);
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
  let response: Response;
  try {
    response = await fetch(`${API_URL}${path}`, {
      ...request,
      headers: {
        Accept: "application/json",
        ...(hasJsonBody ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...headers,
      },
    });
  } catch {
    window.dispatchEvent(new Event(API_UNAVAILABLE_EVENT));
    throw new ApiError(0, "No se pudo conectar con EMOtv. Comprueba tu conexión e inténtalo de nuevo.");
  }

  window.dispatchEvent(new Event(response.status >= 500 ? API_UNAVAILABLE_EVENT : API_RECOVERED_EVENT));

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
