import type { MeterUsage } from "../types";

const METER_LABELS: Record<string, string> = {
  messaging_tokens: "Messaging tokens",
  document_upload_tokens: "Document upload tokens",
  adapter_training_units: "Adapter training",
  adapter_inference_tokens: "Adapter inference tokens",
};

interface UsageMeterBarProps {
  meterEventName: string;
  usage: MeterUsage;
  /** With pay-per-use on, usage past the allotment bills instead of blocking. */
  payPerUseEnabled: boolean;
}

export function UsageMeterBar({
  meterEventName,
  usage,
  payPerUseEnabled,
}: UsageMeterBarProps) {
  const label = METER_LABELS[meterEventName] || meterEventName;
  const allotment = usage.monthly_allotment;
  const used = usage.used_to_date;
  // Prefer the server's figure; fall back to deriving it so an older response
  // shape still renders the overage segment.
  const overage = usage.over_allotment ?? Math.max(0, used - allotment);
  const includedUsed = Math.min(used, allotment);
  const includedPercent = allotment > 0 ? (includedUsed / allotment) * 100 : 0;
  // When there is overage, the bar shows included usage plus a distinct overage
  // segment scaled against total usage so the whole bar stays within bounds.
  const scaleTotal = overage > 0 ? used : allotment;
  const includedWidth = scaleTotal > 0 ? (includedUsed / scaleTotal) * 100 : 0;
  const overageWidth = scaleTotal > 0 ? (overage / scaleTotal) * 100 : 0;

  const overageRateText =
    usage.overage_price_per_unit_usd !== null
      ? `$${usage.overage_price_per_unit_usd.toFixed(2)} per ${usage.unit.replace(/s$/, "")} over allotment`
      : usage.overage_price_per_million !== null
        ? `$${usage.overage_price_per_million.toFixed(2)} per 1,000,000 ${usage.unit} over allotment`
        : "";

  return (
    <div className="usage-meter">
      <div className="usage-meter-header">
        <span className="usage-meter-label">{label}</span>
        <span className="usage-meter-numbers">
          {used.toLocaleString()} / {allotment.toLocaleString()} {usage.unit}
          {overage > 0 ? (
            <span className="overage-text"> (+{overage.toLocaleString()} over)</span>
          ) : null}
        </span>
      </div>
      <div
        className="usage-bar-track"
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={allotment}
        aria-valuenow={used}
        aria-label={`${label} usage`}
      >
        <div
          className={`usage-bar-fill${includedPercent >= 90 ? " usage-bar-warning" : ""}`}
          style={{ width: `${includedWidth}%` }}
        />
        {overage > 0 ? (
          <div className="usage-bar-overage" style={{ width: `${overageWidth}%` }} />
        ) : null}
      </div>
      <div className="usage-meter-footer">
        {/* "0 remaining" on its own reads as "you are cut off", which is wrong
            when pay-per-use is on and the account is still working — and is the
            whole story when it is off. Say which one applies. */}
        <span className={overage > 0 && !payPerUseEnabled ? "error-text" : "muted"}>
          {overage > 0
            ? payPerUseEnabled
              ? `Allotment used; ${overage.toLocaleString()} ${usage.unit} billing as pay-per-use`
              : `Allotment exhausted — enable pay-per-use or upgrade to continue`
            : `${usage.remaining.toLocaleString()} ${usage.unit} remaining`}
        </span>
        {overageRateText ? <span className="muted">{overageRateText}</span> : null}
      </div>
    </div>
  );
}
