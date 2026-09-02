// src/client/src/singleSignOn.ts
//
// Accepting a session handed over by the Neural Nexus application.
//
// The application embeds this portal on its billing page. Somebody who reaches
// that page has already signed in to the application, and before this module
// they were met by this portal's sign-in card anyway, because the portal is a
// separate application on a separate origin with its own session. A shared
// cookie is not an option — inside the frame it would be a third-party cookie,
// which current browsers block by default — so the handoff is explicit.
//
// The application posts a **billing portal exchange code** into this frame: a
// short-lived, single-use credential minted by the Neural Nexus API, carrying
// only "this account is authenticated right now". This module spends it through
// the portal server's /auth/single_sign_on, which returns an ordinary portal
// session token — the same one a password sign-in returns. The application's own
// credential never reaches this origin.
//
// What guards it:
//
// * The listener is registered before the first render, because the application
//   starts posting as soon as the frame's load event fires and a listener
//   registered inside a component would miss the first messages. It retries, so
//   a late listener still works; registering early only avoids a visible flash
//   of the anonymous view.
// * `event.origin` is checked against the allowlist of Neural Nexus application
//   origins — the same list appReturn.ts validates `return_to` against. Without
//   that check any page that framed this portal could post a code of its own
//   choosing and this module would spend it.
// * The acknowledgement goes back to `event.source` at that same checked origin,
//   never "*", so the message that stops the sender's retries cannot be used to
//   probe some other frame.
// * Every failure is silent. The account is simply not signed in, this portal's
//   own sign-in card is right there, and there is nothing the person reading the
//   page could do about a misconfigured secret anyway.

import { apiRequest, setSessionToken } from "./api";

/** Message the application posts into this frame, carrying the code. */
const SINGLE_SIGN_ON_MESSAGE_TYPE = "neural-nexus-portal-single-sign-on";

/** Message this portal posts back once it has accepted the code. */
const SINGLE_SIGN_ON_ACKNOWLEDGEMENT_MESSAGE_TYPE =
  "neural-nexus-portal-single-sign-on-acknowledged";

const NEURAL_NEXUS_APP_ORIGINS: string[] = (
  import.meta.env.VITE_NEURAL_NEXUS_APP_ORIGINS || "https://neuralnexus.site"
)
  .split(",")
  .map((origin: string) => origin.trim().replace(/\/$/, ""))
  .filter(Boolean);

/** Called once a handed-over session has been accepted, so the app reloads. */
type SingleSignOnListener = () => void;

const singleSignOnListeners = new Set<SingleSignOnListener>();

/**
 * Be told when a session arrives from the application.
 *
 * The exchange finishes after the first render — it is a round trip through two
 * servers — so whatever drew the anonymous view has to be asked to look again.
 *
 * @param listener Run when a session has been accepted.
 * @returns A function that stops listening.
 */
export function subscribeToSingleSignOn(
  listener: SingleSignOnListener,
): () => void {
  singleSignOnListeners.add(listener);
  return () => {
    singleSignOnListeners.delete(listener);
  };
}

interface SingleSignOnResponse {
  token: string;
  email: string;
  customer_id: string;
}

// One code is spendable once, and the application posts the same code every 400
// milliseconds until this portal acknowledges it. Without this the retries that
// arrive before the first exchange completes would each start an exchange of
// their own, and every one after the first would be refused as already spent.
let exchangeInProgressOrDone = false;

/**
 * Listen for a session handed over by the Neural Nexus application.
 *
 * Call once, before the first render. Safe to call when this portal is not
 * embedded: no message ever arrives and nothing happens.
 */
export function startSingleSignOnListener(): void {
  window.addEventListener("message", (event: MessageEvent) => {
    const messageOrigin = event.origin.replace(/\/$/, "");
    if (!NEURAL_NEXUS_APP_ORIGINS.includes(messageOrigin)) {
      return;
    }
    const message = event.data;
    if (
      typeof message !== "object" ||
      message === null ||
      message.type !== SINGLE_SIGN_ON_MESSAGE_TYPE ||
      typeof message.exchangeCode !== "string" ||
      !message.exchangeCode
    ) {
      return;
    }
    if (exchangeInProgressOrDone) {
      return;
    }
    exchangeInProgressOrDone = true;

    // event.source is typed as the union of everything that can post a
    // message; only a window can have sent this one, and only a window accepts
    // the targetOrigin form the acknowledgement has to be pinned with.
    const senderWindow = event.source as Window | null;
    void apiRequest<SingleSignOnResponse>("/auth/single_sign_on", {
      method: "POST",
      body: { exchange_code: message.exchangeCode },
    })
      .then((session) => {
        setSessionToken(session.token);
        // Acknowledged only on success. A failed exchange leaves the sender
        // retrying with the same code until its own cap, which costs a few
        // messages and is the honest signal that nothing was accepted.
        senderWindow?.postMessage(
          { type: SINGLE_SIGN_ON_ACKNOWLEDGEMENT_MESSAGE_TYPE },
          event.origin,
        );
        singleSignOnListeners.forEach((listener) => listener());
      })
      .catch(() => {
        // 503 when the shared secret is unset on either side, 401 when the code
        // is expired or already spent, 403 when the account has no Stripe
        // customer yet. In every case this portal's own sign-in card is the
        // fallback — but a later code should still get a turn, so the guard is
        // released.
        exchangeInProgressOrDone = false;
      });
  });
}
