const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8080";

const SESSION_TOKEN_STORAGE_KEY = "neural_nexus_portal_session_token";

// The session token lives in localStorage, which every tab of this origin
// shares. Without this flag an anonymous tab would start sending a token the
// moment the user signed in from a DIFFERENT tab — its next usage poll would
// return the signed-in customer's meters while its header and subscription card
// still described the anonymous visitor, showing one page built from two
// identities. So each tab decides once, at load, which identity it is, and
// keeps it: an anonymous tab keeps reporting its own hashed-ip usage until it
// is reloaded or signs in itself.
let tabIsAnonymous = localStorage.getItem(SESSION_TOKEN_STORAGE_KEY) === null;

export function isTabAnonymous(): boolean {
  return tabIsAnonymous;
}

export function getSessionToken(): string | null {
  return localStorage.getItem(SESSION_TOKEN_STORAGE_KEY);
}

/** The token this tab should authenticate with, or null while it is anonymous. */
export function getActiveSessionToken(): string | null {
  return tabIsAnonymous ? null : getSessionToken();
}

export function setSessionToken(token: string): void {
  localStorage.setItem(SESSION_TOKEN_STORAGE_KEY, token);
  // Signing in happened in THIS tab, so this tab stops being anonymous.
  tabIsAnonymous = false;
}

export function clearSessionToken(): void {
  localStorage.removeItem(SESSION_TOKEN_STORAGE_KEY);
  tabIsAnonymous = true;
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
  const sessionToken = getActiveSessionToken();
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

/** One meter's usage as pushed by the server the moment a turn is metered. */
export interface UsageStreamEvent {
  meter_event_name: string;
  used_to_date: number;
  usage_period_start: string | null;
  usage_period_end: string | null;
}

// Reconnect backoff after a stream drops. EventSource retries on its own, but a
// verified stream is opened with a ticket that expires in a minute, so its
// built-in retry would loop forever against a URL that can no longer authorize.
// Reconnecting is therefore done here, with a fresh ticket each time.
const USAGE_STREAM_RECONNECT_DELAY_MS = 5_000;

/**
 * Subscribe to this customer's usage stream. Returns an unsubscribe function.
 *
 * Usage is spent in the chat app, so the portal would otherwise only learn about
 * it on its next poll, and then only once Stripe had finished aggregating. The
 * server pushes the reconciled figure as soon as a turn is metered; the poll
 * stays in place as the reconciliation path against Stripe.
 */
export function subscribeToUsageStream(
  onUsage: (event: UsageStreamEvent) => void,
): () => void {
  let eventSource: EventSource | null = null;
  let reconnectTimer: number | undefined;
  let stopped = false;

  const scheduleReconnect = () => {
    if (stopped || reconnectTimer !== undefined) {
      return;
    }
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = undefined;
      void open();
    }, USAGE_STREAM_RECONNECT_DELAY_MS);
  };

  const open = async () => {
    if (stopped) {
      return;
    }
    let streamUrl = `${API_BASE_URL}/usage/stream`;
    if (!isTabAnonymous()) {
      // EventSource cannot send an Authorization header, so a verified tab
      // trades its session for a short-lived, stream-only ticket.
      try {
        const { ticket } = await apiRequest<{ ticket: string }>(
          "/usage/stream-ticket",
          { method: "POST" },
        );
        streamUrl += `?ticket=${encodeURIComponent(ticket)}`;
      } catch {
        // No billing record yet, or the session expired. The poll still works.
        scheduleReconnect();
        return;
      }
    }
    if (stopped) {
      return;
    }
    eventSource = new EventSource(streamUrl);
    eventSource.addEventListener("usage", (message) => {
      try {
        onUsage(JSON.parse((message as MessageEvent).data) as UsageStreamEvent);
      } catch {
        // A malformed frame must not tear down the stream.
      }
    });
    eventSource.onerror = () => {
      eventSource?.close();
      eventSource = null;
      scheduleReconnect();
    };
  };

  void open();

  return () => {
    stopped = true;
    if (reconnectTimer !== undefined) {
      window.clearTimeout(reconnectTimer);
    }
    eventSource?.close();
    eventSource = null;
  };
}
