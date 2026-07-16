import type { SubscriptionStatus, TierCatalogMeter } from "../types";

interface TierSwitcherProps {
  subscription: SubscriptionStatus;
  busy: boolean;
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

export function TierSwitcher({ subscription, busy, onSelectTier }: TierSwitcherProps) {
  return (
    <div className="tier-switcher">
      <h3>Switch plan</h3>
      <p className="muted">
        Upgrades apply immediately (with proration). Downgrades apply at the end of
        the current billing period — unused allotment continues until then.
      </p>
      <div className="tier-grid">
        {subscription.tier_catalog.map((tierEntry) => {
          const isCurrent = tierEntry.tier === subscription.tier;
          return (
            <div
              key={tierEntry.tier}
              className={`tier-card${isCurrent ? " tier-card-current" : ""}`}
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
                className={isCurrent ? "secondary-button" : "primary-button"}
                disabled={busy || (isCurrent && !subscription.cancel_at_period_end)}
                onClick={() => onSelectTier(tierEntry.tier)}
              >
                {isCurrent
                  ? subscription.cancel_at_period_end
                    ? "Keep this plan"
                    : "Current plan"
                  : "Switch to this plan"}
              </button>
            </div>
          );
        })}
      </div>
    </div>
  );
}
