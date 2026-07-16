const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8080";

const SESSION_TOKEN_STORAGE_KEY = "neural_nexus_portal_session_token";

export function getSessionToken(): string | null {
  return localStorage.getItem(SESSION_TOKEN_STORAGE_KEY);
}

export function setSessionToken(token: string): void {
  localStorage.setItem(SESSION_TOKEN_STORAGE_KEY, token);
}

export function clearSessionToken(): void {
  localStorage.removeItem(SESSION_TOKEN_STORAGE_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, detail: string) {
    super(detail);
    this.status = status;
  }
}

export async function apiRequest<ResponseType>(
  path: string,
  options: { method?: string; body?: unknown } = {},
): Promise<ResponseType> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  const sessionToken = getSessionToken();
  if (sessionToken) {
    headers["Authorization"] = `Bearer ${sessionToken}`;
  }
  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method || "GET",
    headers,
    body: options.body === undefined ? undefined : JSON.stringify(options.body),
  });
  if (response.status === 401 && sessionToken) {
    // The session expired; drop the token so the app falls back to login.
    clearSessionToken();
  }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`;
    try {
      const errorDocument = await response.json();
      if (typeof errorDocument.detail === "string") {
        detail = errorDocument.detail;
      }
    } catch {
      // Keep the generic message when the body is not JSON.
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) {
    return undefined as ResponseType;
  }
  return (await response.json()) as ResponseType;
}
