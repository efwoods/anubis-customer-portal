import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import { withAppReturnUrl } from "../appReturn";
import type { SubscriptionActionResult, SubscriptionStatus } from "../types";
import { TierSwitcher } from "./TierSwitcher";

const PENDING_TIER_STORAGE_KEY = "nn-portal-pending-tier";

interface SubscriptionSectionProps {
  isVerified: boolean;
  refreshCounter: number;
  onChanged: () => void;
  /** Anonymous: open sign-in, then complete checkout for this tier after OTP. */
  onRequestSignupForTier?: (tier: string) => void;
}

function formatDate(isoDate: string | null): string {
  if (!isoDate) {
    return "";
  }
  return new Date(isoDate).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

export function readPendingTierChange(): string | null {
  try {
    return sessionStorage.getItem(PENDING_TIER_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function clearPendingTierChange(): void {
  try {
    sessionStorage.removeItem(PENDING_TIER_STORAGE_KEY);
  } catch {
    // ignore
  }
}

export function storePendingTierChange(tier: string): void {
  try {
    sessionStorage.setItem(PENDING_TIER_STORAGE_KEY, tier);
  } catch {
    // ignore
  }
}

/**
 * Send the browser to a Stripe-hosted page, such as a Checkout session.
 *
 * Stripe refuses to be framed: every Stripe-hosted page answers with
 * `X-Frame-Options: SAMEORIGIN` and a `frame-ancestors 'self'` content security
 * policy. The Neural Nexus billing page embeds this portal in an iframe, so
 * navigating this window while embedded hands the frame a document the browser
 * then declines to render, and the customer sees a blank white frame instead of
 * a payment page. Navigating the top-level window takes the whole tab to
 * Stripe, which is where a payment page belongs. Cross-origin top navigation is
 * permitted here because the navigation happens under the click that asked for
 * the plan change.
 *
 * @param stripeHostedPageUrl The URL Stripe returned for the page to open.
 */
export function navigateToStripeHostedPage(stripeHostedPageUrl: string): void {
  const topWindow = window.top;
  const isEmbeddedInAnotherPage = topWindow !== null && topWindow !== window.self;

  if (isEmbeddedInAnotherPage) {
    try {
      topWindow.location.href = stripeHostedPageUrl;
      return;
    } catch {
      // A frame that is not allowed to navigate its top-level window throws
      // here. A new tab still gets the customer to Stripe, so the plan change
      // completes rather than dead-ending.
      const openedTab = window.open(stripeHostedPageUrl, "_blank", "noopener");
      if (openedTab) {
        return;
      }
    }
  }

  window.location.href = stripeHostedPageUrl;
}

export async function startPendingTierCheckout(): Promise<boolean> {
  const tier = readPendingTierChange();
  if (!tier) {
    return false;
  }
  clearPendingTierChange();
  const result = await apiRequest<SubscriptionActionResult>("/subscription/change", {
    method: "POST",
    body: withAppReturnUrl({ tier }),
  });
  if (result.action === "start_checkout" && result.url) {
    navigateToStripeHostedPage(result.url);
    return true;
  }
  return false;
}

export function SubscriptionSection({
  isVerified,
  refreshCounter,
  onChanged,
  onRequestSignupForTier,
}: SubscriptionSectionProps) {
  const [subscription, setSubscription] = useState<SubscriptionStatus | null>(null);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    apiRequest<SubscriptionStatus>("/subscription")
      .then(setSubscription)
      .catch((loadError) =>
        setErrorMessage(
          loadError instanceof Error ? loadError.message : "Could not load subscription.",
        ),
      );
  }, [refreshCounter]);

  const runAction = async (
    actionName: string,
    path: string,
    body?: unknown,
  ): Promise<void> => {
    setBusyAction(actionName);
    setActionMessage(null);
    setErrorMessage(null);
    try {
      const result = await apiRequest<SubscriptionActionResult>(path, {
        method: "POST",
        body: withAppReturnUrl(body),
      });
      if (result.action === "start_checkout" && result.url) {
        navigateToStripeHostedPage(result.url);
        return;
      }
      setActionMessage(result.message);
      onChanged();
    } catch (actionError) {
      setErrorMessage(
        actionError instanceof Error ? actionError.message : "The action failed.",
      );
    } finally {
      setBusyAction(null);
    }
  };

  if (!subscription) {
    return (
      <section className="card">
        <h2>Current subscription</h2>
        {errorMessage ? <p className="error-text">{errorMessage}</p> : <p>Loading…</p>}
      </section>
    );
  }

  const tierEntry = subscription.tier_catalog.find(
    (entry) => entry.tier === subscription.tier,
  );
  const isTrialing = subscription.status === "trialing";
  const daysRemaining = subscription.trial_days_remaining;
  // "Free trial" alone never told the customer whether theirs was still running
  // or how much was left, which is exactly what they need to decide about a
  // plan. Lead with the countdown and fall back to the end date.
  const trialCountdownText =
    daysRemaining !== null && daysRemaining > 0
      ? `Free trial: ${daysRemaining} day${daysRemaining === 1 ? "" : "s"} left`
      : daysRemaining === 0
        ? "Free trial ended"
        : `Free trial ends ${formatDate(subscription.trial_end)}`;
  const cancelDate = subscription.cancel_at || subscription.current_period_end;
  const pendingDowngradeEntry = subscription.pending_downgrade_tier
    ? subscription.tier_catalog.find(
        (entry) => entry.tier === subscription.pending_downgrade_tier,
      )
    : undefined;
  const pendingDowngradeName =
    pendingDowngradeEntry?.display_name ||
    (subscription.pending_downgrade_tier
      ? `${subscription.pending_downgrade_tier[0].toUpperCase()}${subscription.pending_downgrade_tier.slice(1)} tier`
      : null);

  return (
    <section className="card">
      <div className="card-header-row">
        <h2>Current subscription</h2>
        {subscription.cancel_at_period_end ? (
          <span className="badge badge-warning">Cancels {formatDate(cancelDate)}</span>
        ) : pendingDowngradeName ? (
          <span className="badge badge-warning">
            Switches to {pendingDowngradeName} {formatDate(subscription.current_period_end)}
          </span>
        ) : isTrialing ? (
          <span className="badge badge-info">{trialCountdownText}</span>
        ) : subscription.status ? (
          <span className="badge badge-success">{subscription.status}</span>
        ) : (
          <span className="badge badge-info">anonymous free tier</span>
        )}
      </div>

      <p className="plan-name">
        {tierEntry?.display_name ||
          `Neural Nexus ${subscription.tier[0].toUpperCase()}${subscription.tier.slice(1)} Tier`}
      </p>
      <p className="muted">Price varies with usage</p>
      {subscription.monthly_base_fee_usd > 0 ? (
        <p className="muted">
          Base subscription: ${subscription.monthly_base_fee_usd.toFixed(2)} / month
        </p>
      ) : null}

      {isTrialing ? (
        <p>
          Your free trial includes the full pro-tier monthly allotment of messaging
          and document-upload tokens at no charge, and{" "}
          {daysRemaining !== null && daysRemaining > 0
            ? `${daysRemaining} day${daysRemaining === 1 ? "" : "s"} of it remain`
            : "it has now run out"}
          . After the trial ends on {formatDate(subscription.trial_end)}, the
          service continues automatically when a payment method is on file —
          otherwise the account drops to the free tier.
        </p>
      ) : !subscription.trial_already_used && subscription.trial_tier ? (
        <p className="muted">
          Your free trial has not been used yet — it is included with the{" "}
          {subscription.trial_tier} tier below.
        </p>
      ) : null}

      {subscription.cancel_at_period_end ? (
        <>
          <p>
            Your <strong>{tierEntry?.display_name || subscription.tier}</strong> plan
            stays active until {formatDate(cancelDate)}, then the account drops to the
            free tier. Your current allotment continues until then.
          </p>
          {isVerified ? (
            <button
              className="primary-button"
              disabled={busyAction !== null}
              onClick={() => runAction("reactivate", "/subscription/reactivate")}
            >
              {busyAction === "reactivate" ? "Working…" : "Keep my plan"}
            </button>
          ) : null}
        </>
      ) : pendingDowngradeName ? (
        <>
          <p>
            Your <strong>{tierEntry?.display_name || subscription.tier}</strong> plan is
            active until {formatDate(subscription.current_period_end)}, then it switches
            to <strong>{pendingDowngradeName}</strong>. Your current allotment continues
            until then.
          </p>
          {isVerified ? (
            <button
              className="primary-button"
              disabled={busyAction !== null}
              onClick={() =>
                runAction(`keep:${subscription.tier}`, "/subscription/change", {
                  tier: subscription.tier,
                })
              }
            >
              {busyAction === `keep:${subscription.tier}`
                ? "Working…"
                : `Keep ${tierEntry?.display_name || subscription.tier} plan`}
            </button>
          ) : null}
        </>
      ) : isVerified && subscription.subscription_id ? (
        <button
          className="danger-button"
          disabled={busyAction !== null}
          onClick={() => runAction("cancel", "/subscription/cancel")}
        >
          {busyAction === "cancel" ? "Working…" : "Cancel subscription"}
        </button>
      ) : null}

      {isVerified ? (
        <TierSwitcher
          subscription={subscription}
          busy={busyAction !== null}
          mode="switch"
          onSelectTier={(tier) =>
            runAction(`change:${tier}`, "/subscription/change", { tier })
          }
        />
      ) : (
        <TierSwitcher
          subscription={subscription}
          busy={busyAction !== null}
          mode="signup"
          onSelectTier={(tier) => {
            if (onRequestSignupForTier) {
              onRequestSignupForTier(tier);
              return;
            }
            storePendingTierChange(tier);
          }}
        />
      )}

      {actionMessage ? <p className="success-text">{actionMessage}</p> : null}
      {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
    </section>
  );
}
