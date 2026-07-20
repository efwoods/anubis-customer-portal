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

function buttonLabel(
  mode: "switch" | "signup",
  tier: string,
  isCurrent: boolean,
  cancelAtPeriodEnd: boolean,
  trialPeriodDays: number,
): string {
  if (mode === "signup") {
    if (isCurrent) {
      return "Current plan";
    }
    if (tier === "pro" && trialPeriodDays > 0) {
      return "Sign up for free Pro trial";
    }
    return "Sign in to subscribe";
  }
  if (isCurrent) {
    return cancelAtPeriodEnd ? "Keep this plan" : "Current plan";
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
          const label = buttonLabel(
            mode,
            tierEntry.tier,
            isCurrent,
            subscription.cancel_at_period_end,
            tierEntry.trial_period_days,
          );
          const isProTrialCta =
            mode === "signup" &&
            tierEntry.tier === "pro" &&
            tierEntry.trial_period_days > 0 &&
            !isCurrent;
          const disabled =
            busy ||
            (mode === "switch" && isCurrent && !subscription.cancel_at_period_end) ||
            (mode === "signup" && isCurrent);

          return (
            <div
              key={tierEntry.tier}
              className={`tier-card${isCurrent ? " tier-card-current" : ""}${
                isProTrialCta ? " tier-card-highlight" : ""
              }`}
            >
              <h4>{tierEntry.display_name}</h4>
              <p className="tier-price">
                {tierEntry.monthly_base_fee_usd > 0
                  ? `$${tierEntry.monthly_base_fee_usd.toFixed(2)}/month`
                  : "$0/month"}
              </p>
              {tierEntry.trial_period_days > 0 ? (
                <p className="badge badge-info">
                  {tierEntry.trial_period_days}-day free trial
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
