import type { SubscriptionStatus, TierCatalogMeter } from "../types";

interface TierSwitcherProps {
  subscription: SubscriptionStatus;
  busy: boolean;
  /** Verified users switch plans; anonymous users start the free Pro trial signup. */
  mode?: "switch" | "signup";
  onSelectTier: (tier: string) => void;
}

const METER_LABELS: Record<string, string> = {
  messaging_tokens: "Messaging tokens",
  document_upload_tokens: "Document upload tokens",
  adapter_training_units: "Adapter training",
  adapter_inference_tokens: "Adapter inference tokens",
};

function formatAllotment(meter: TierCatalogMeter): string {
  const label = METER_LABELS[meter.meter_event_name] || meter.meter_event_name;
  return `${label}: ${meter.monthly_allotment.toLocaleString()} ${meter.unit}/month`;
}

function formatOverageRate(meter: TierCatalogMeter): string {
  if (meter.overage_price_per_unit_usd !== null) {
    return `$${meter.overage_price_per_unit_usd.toFixed(2)} per unit over`;
  }
  if (meter.overage_price_per_million !== null) {
    return `$${meter.overage_price_per_million.toFixed(2)} per 1M over`;
  }
  return "";
}

function formatDate(isoDate: string | null): string {
  if (!isoDate) {
    return "the end of the current period";
  }
  return new Date(isoDate).toLocaleDateString(undefined, {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
}

/** Describes this customer's standing with the tier's free trial, or "" when none. */
function trialStatusText(
  subscription: SubscriptionStatus,
  tier: string,
  trialPeriodDays: number,
): string {
  if (trialPeriodDays <= 0) {
    return "";
  }
  // The trial belongs to whichever tier grants it, so a customer trialing on an
  // upgraded tier still sees the status on the tier that gave it to them.
  const isTrialTier = subscription.trial_tier === tier;
  if (subscription.trialing && isTrialTier) {
    const daysRemaining = subscription.trial_days_remaining;
    if (daysRemaining === null) {
      return "Free trial running";
    }
    return daysRemaining <= 0
      ? "Free trial ended"
      : `Free trial: ${daysRemaining} day${daysRemaining === 1 ? "" : "s"} left`;
  }
  if (subscription.trial_already_used) {
    return "Free trial already used";
  }
  return `${trialPeriodDays}-day free trial available`;
}

function trialBadgeClass(subscription: SubscriptionStatus, tier: string): string {
  if (subscription.trialing && subscription.trial_tier === tier) {
    return "badge badge-success";
  }
  return subscription.trial_already_used ? "badge badge-muted" : "badge badge-info";
}

function buttonLabel(
  mode: "switch" | "signup",
  tier: string,
  isCurrent: boolean,
  hasPendingChange: boolean,
  isPendingTarget: boolean,
  trialPeriodDays: number,
  trialAlreadyUsed: boolean,
): string {
  if (mode === "signup") {
    if (isCurrent) {
      return "Current plan";
    }
    if (tier === "pro" && trialPeriodDays > 0 && !trialAlreadyUsed) {
      return "Sign up for free Pro trial";
    }
    return "Sign in to subscribe";
  }
  if (isCurrent) {
    return hasPendingChange ? "Keep this plan" : "Current plan";
  }
  if (isPendingTarget) {
    return "Scheduled";
  }
  return "Switch to this plan";
}

export function TierSwitcher({
  subscription,
  busy,
  mode = "switch",
  onSelectTier,
}: TierSwitcherProps) {
  return (
    <div className="tier-switcher">
      <h3>{mode === "signup" ? "Upgrade from anonymous free tier" : "Switch plan"}</h3>
      <p className="muted">
        {mode === "signup" ? (
          <>
            Anonymous usage is tracked by a hash of your network address (the same
            scheme Neural Nexus uses). Create an account with email and password to
            start the free Pro trial, then open Stripe Checkout.
          </>
        ) : (
          <>
            Upgrades apply immediately (with proration). Downgrades apply at the end of
            the current billing period — unused allotment continues until then.
          </>
        )}
      </p>
      <div className="tier-grid">
        {subscription.tier_catalog.map((tierEntry) => {
          const isCurrent = tierEntry.tier === subscription.tier;
          const hasPendingChange =
            subscription.cancel_at_period_end ||
            subscription.pending_downgrade_tier !== null;
          const isPendingTarget =
            mode === "switch" &&
            tierEntry.tier === subscription.pending_downgrade_tier;
          const label = buttonLabel(
            mode,
            tierEntry.tier,
            isCurrent,
            hasPendingChange,
            isPendingTarget,
            tierEntry.trial_period_days,
            subscription.trial_already_used,
          );
          const isProTrialCta =
            mode === "signup" &&
            tierEntry.tier === "pro" &&
            tierEntry.trial_period_days > 0 &&
            !subscription.trial_already_used &&
            !isCurrent;
          const trialText = trialStatusText(
            subscription,
            tierEntry.tier,
            tierEntry.trial_period_days,
          );
          const disabled =
            busy ||
            (mode === "switch" && isCurrent && !hasPendingChange) ||
            (mode === "switch" && isPendingTarget) ||
            (mode === "signup" && isCurrent);
          const effectiveDate = formatDate(subscription.current_period_end);

          return (
            <div
              key={tierEntry.tier}
              className={`tier-card${isCurrent ? " tier-card-current" : ""}${
                isProTrialCta ? " tier-card-highlight" : ""
              }${isPendingTarget ? " tier-card-pending" : ""}`}
            >
              <h4>{tierEntry.display_name}</h4>
              {mode === "switch" && isCurrent && !hasPendingChange ? (
                <p className="badge badge-success">✓ Active plan</p>
              ) : null}
              {mode === "switch" && isCurrent && hasPendingChange ? (
                <p className="badge badge-warning">
                  Active until {effectiveDate}
                </p>
              ) : null}
              {isPendingTarget ? (
                <p className="badge badge-info">Starts {effectiveDate}</p>
              ) : null}
              <p className="tier-price">
                {tierEntry.monthly_base_fee_usd > 0
                  ? `$${tierEntry.monthly_base_fee_usd.toFixed(2)}/month`
                  : "$0/month"}
              </p>
              {trialText ? (
                <p className={trialBadgeClass(subscription, tierEntry.tier)}>
                  {trialText}
                </p>
              ) : null}
              <ul className="tier-meter-list">
                {tierEntry.meters.map((meter) => (
                  <li key={meter.meter_event_name}>
                    {formatAllotment(meter)}
                    <span className="muted"> · {formatOverageRate(meter)}</span>
                  </li>
                ))}
              </ul>
              <button
                className={
                  isCurrent
                    ? "secondary-button"
                    : isProTrialCta || mode === "switch"
                      ? "primary-button"
                      : "secondary-button"
                }
                disabled={disabled}
                onClick={() => onSelectTier(tierEntry.tier)}
              >
                {label}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
