import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import type { SubscriptionStatus, UsageReport } from "../types";
import { PayPerUseToggle } from "./PayPerUseToggle";
import { UsageMeterBar } from "./UsageMeterBar";

interface UsageSectionProps {
  isVerified: boolean;
  refreshCounter: number;
  onChanged: () => void;
}

function formatDate(isoDate: string): string {
  return new Date(isoDate).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function UsageSection({ isVerified, refreshCounter, onChanged }: UsageSectionProps) {
  const [usage, setUsage] = useState<UsageReport | null>(null);
  const [payPerUseEnabled, setPayPerUseEnabled] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    apiRequest<UsageReport>("/usage")
      .then(setUsage)
      .catch((usageError) =>
        setErrorMessage(
          usageError instanceof Error ? usageError.message : "Could not load usage.",
        ),
      );
    if (isVerified) {
      apiRequest<SubscriptionStatus>("/subscription")
        .then((subscription) => setPayPerUseEnabled(subscription.pay_per_use_enabled))
        .catch(() => undefined);
    }
  }, [refreshCounter, isVerified]);

  return (
    <section className="card">
      <div className="card-header-row">
        <h2>Usage this period</h2>
        {usage ? (
          <span className="muted">
            {formatDate(usage.usage_period_start)} – {formatDate(usage.usage_period_end)}
          </span>
        ) : null}
      </div>

      {usage?.trialing ? (
        <p className="badge badge-info">
          Free trial: this usage is free up to the full pro-tier allotment shown below.
        </p>
      ) : null}

      {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
      {!usage && !errorMessage ? <p>Loading…</p> : null}

      {usage
        ? Object.entries(usage.meters).map(([meterEventName, meterUsage]) => (
            <UsageMeterBar
              key={meterEventName}
              meterEventName={meterEventName}
              usage={meterUsage}
            />
          ))
        : null}

      {usage && Object.keys(usage.meters).length === 0 ? (
        <p className="muted">No usage meters are provisioned for this account yet.</p>
      ) : null}

      {isVerified ? (
        <PayPerUseToggle enabled={payPerUseEnabled} onChanged={onChanged} />
      ) : null}
    </section>
  );
}
