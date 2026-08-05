import { useCallback, useEffect, useState } from "react";
import { apiRequest, subscribeToUsageStream } from "../api";
import type { UsageReport } from "../types";
import { PayPerUseToggle } from "./PayPerUseToggle";
import { UsageMeterBar } from "./UsageMeterBar";

interface UsageSectionProps {
  isVerified: boolean;
  refreshCounter: number;
  onChanged: () => void;
}

// Usage is spent in the chat app, not this portal. The server pushes each new
// figure over the usage stream the moment a turn is metered, so the meters move
// immediately; this poll remains as the reconciliation path, re-reading Stripe
// (the billing source of truth) and correcting the display if a push was ever
// missed or the stream was down.
const USAGE_POLL_INTERVAL_MS = 20_000;

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

  // /usage reports the pay-per-use flag alongside the meters it governs, so the
  // toggle and the bars are always read from one response — a second request to
  // /subscription could answer differently mid-flight and show a bar labelled
  // "billing as pay-per-use" beside a toggle switched off.
  const loadUsage = useCallback(() => {
    apiRequest<UsageReport>("/usage")
      .then((report) => {
        setUsage(report);
        setPayPerUseEnabled(report.pay_per_use_enabled);
        setErrorMessage(null);
      })
      .catch((usageError) =>
        setErrorMessage(
          usageError instanceof Error ? usageError.message : "Could not load usage.",
        ),
      );
  }, []);

  useEffect(() => {
    loadUsage();
  }, [loadUsage, refreshCounter]);

  // Apply a pushed figure to the meter it names, without waiting for a poll.
  // The pushed value is only ever taken as a floor, for the same reason the
  // server reconciles with max(): usage within a period never decreases, so a
  // late or out-of-order frame must not walk a meter backwards. A frame from a
  // different period means the period rolled over, so the whole report is
  // re-read rather than patched.
  useEffect(() => {
    const unsubscribe = subscribeToUsageStream((event) => {
      setUsage((currentReport) => {
        if (currentReport === null) {
          return currentReport;
        }
        if (
          event.usage_period_start !== null &&
          event.usage_period_start !== currentReport.usage_period_start
        ) {
          loadUsage();
          return currentReport;
        }
        const meter = currentReport.meters[event.meter_event_name];
        if (meter === undefined || event.used_to_date <= meter.used_to_date) {
          return currentReport;
        }
        const usedToDate = event.used_to_date;
        return {
          ...currentReport,
          meters: {
            ...currentReport.meters,
            [event.meter_event_name]: {
              ...meter,
              used_to_date: usedToDate,
              remaining: Math.max(0, meter.monthly_allotment - usedToDate),
              over_allotment: Math.max(0, usedToDate - meter.monthly_allotment),
            },
          },
        };
      });
    });
    return unsubscribe;
  }, [loadUsage]);

  // Keep the meters current without a manual reload: poll on an interval and
  // refetch immediately when the user returns to the tab. Polling pauses while
  // the tab is hidden to avoid pointless background requests.
  useEffect(() => {
    const refetchIfVisible = () => {
      if (document.visibilityState === "visible") {
        loadUsage();
      }
    };
    const intervalId = window.setInterval(refetchIfVisible, USAGE_POLL_INTERVAL_MS);
    document.addEventListener("visibilitychange", refetchIfVisible);
    window.addEventListener("focus", refetchIfVisible);
    return () => {
      window.clearInterval(intervalId);
      document.removeEventListener("visibilitychange", refetchIfVisible);
      window.removeEventListener("focus", refetchIfVisible);
    };
  }, [loadUsage]);

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
              payPerUseEnabled={usage.pay_per_use_enabled}
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
