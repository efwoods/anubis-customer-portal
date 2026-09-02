// src/client/src/appReturn.ts
//
// Getting the customer back to the Neural Nexus application after Stripe.
//
// Stripe refuses to be framed, so a plan change navigates the whole tab out of
// the application to Stripe (see navigateToStripeHostedPage). Checkout then
// returns that tab to THIS portal, because the landing here reconciles the card
// Checkout charged with. The customer is now standing in the portal, at the top
// level, with the application they started in nowhere in sight — and before
// this module, with nothing to click to get back.
//
// The application says where it sent them from by embedding this portal with
// `?return_to=<its own URL>`; the portal server carries that through Stripe on
// the success and cancel URLs, and the landing brings the customer home.
//
// Both ends validate it. The server checks the origin against its configured
// APP_RETURN_ORIGIN before putting it in a Stripe URL; this file checks it
// again on the way out, because by then the value has been through an address
// bar and a link that could have been handed to the customer by anyone.

const APP_RETURN_ORIGINS: string[] = (
  import.meta.env.VITE_NEURAL_NEXUS_APP_ORIGINS || "https://www.neuralnexus.site,https://neuralnexus.site"
)
  .split(",")
  .map((origin: string) => origin.trim().replace(/\/$/, ""))
  .filter(Boolean);

/** The application to offer as "back", when no specific page was named. */
export const NEURAL_NEXUS_APP_URL: string =
  APP_RETURN_ORIGINS[0] ?? "https://www.neuralnexus.site";

/**
 * Whether this URL is one of the application origins the portal returns to.
 *
 * @param candidateUrl A URL that arrived from outside this code.
 */
function isReturnableApplicationUrl(candidateUrl: string): boolean {
  try {
    const parsed = new URL(candidateUrl);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      return false;
    }
    return APP_RETURN_ORIGINS.includes(parsed.origin.replace(/\/$/, ""));
  } catch {
    return false;
  }
}

/**
 * The application URL this session should return to, if there is a safe one.
 *
 * @param search The query string to read; defaults to the current one.
 * @returns The URL, or null when none was passed or it is not returnable.
 */
export function readAppReturnUrl(
  search: string = window.location.search,
): string | null {
  const returnTo = new URLSearchParams(search).get("return_to");
  if (!returnTo || !isReturnableApplicationUrl(returnTo)) {
    return null;
  }
  return returnTo;
}

/**
 * The application screen the portal's own way-out leads to: the avatar gallery.
 *
 * Not the page the customer came from, which is what `return_to` names and what
 * the post-Checkout return uses. Those are two different journeys. Coming back
 * from Stripe should resume where the plan change broke off — the billing page
 * — but someone pressing "back" out of the portal is done with billing and
 * wants the application, and the application is its avatars.
 *
 * The origin is taken from `return_to` when one was passed, so a customer sent
 * here by a development or preview deployment is returned to THAT deployment
 * rather than to production. That value has already been checked against the
 * allowlist by readAppReturnUrl, so its origin is one of ours.
 *
 * @returns An absolute URL to the application's avatar gallery.
 */
export function resolveApplicationAvatarsUrl(): string {
  const returnUrl = readAppReturnUrl();
  let applicationOrigin = NEURAL_NEXUS_APP_URL;
  if (returnUrl) {
    try {
      applicationOrigin = new URL(returnUrl).origin;
    } catch {
      // readAppReturnUrl already parsed it; this is unreachable in practice and
      // falls back to the configured application origin if it ever is not.
    }
  }
  return `${applicationOrigin.replace(/\/$/, "")}/avatars`;
}

/**
 * Whether this portal is running inside another page's frame.
 *
 * Comparing the two window references is allowed across origins; reading
 * anything off the top window is not, which is why nothing here does.
 */
export function isEmbeddedInAnotherPage(): boolean {
  const topWindow = window.top;
  return topWindow !== null && topWindow !== window.self;
}

/**
 * Attach the return target to a request body, when there is one.
 *
 * Applied to every subscription action rather than to the two that visibly
 * start Checkout, because which action ends up at Stripe is the server's
 * decision: a tier change made with no live subscription comes back as
 * `start_checkout`. A body that is not an object (an action that sends none) is
 * returned untouched.
 *
 * @param body The request body the caller built.
 */
export function withAppReturnUrl<BodyType>(body: BodyType): BodyType {
  const applicationUrl = readAppReturnUrl();
  if (!applicationUrl || typeof body !== "object" || body === null) {
    return body;
  }
  return { ...body, return_to: applicationUrl };
}

/**
 * Send the customer back to the application.
 *
 * Navigates the TOP window for the same reason the Stripe hop does: while this
 * portal is embedded, navigating its own frame would load the application
 * inside a frame of itself. After Checkout the portal is already the top-level
 * document, and this is then an ordinary navigation.
 *
 * @param applicationUrl A URL that has passed isReturnableApplicationUrl.
 */
export function navigateToApplication(applicationUrl: string): void {
  const topWindow = window.top;
  if (topWindow !== null && isEmbeddedInAnotherPage()) {
    try {
      topWindow.location.href = applicationUrl;
      return;
    } catch {
      // A frame not permitted to navigate its top-level window. Falling through
      // leaves the customer in the frame rather than stranded.
    }
  }
  window.location.href = applicationUrl;
}
