import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import type { SubscriptionActionResult, SubscriptionStatus } from "../types";
import { TierSwitcher } from "./TierSwitcher";

interface SubscriptionSectionProps {
  isVerified: boolean;
  refreshCounter: number;
  onChanged: () => void;
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

export function SubscriptionSection({
  isVerified,
  refreshCounter,
  onChanged,
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
        body,
      });
      if (result.action === "start_checkout" && result.url) {
        window.location.href = result.url;
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
  const cancelDate = subscription.cancel_at || subscription.current_period_end;

  return (
    <section className="card">
      <div className="card-header-row">
        <h2>Current subscription</h2>
        {subscription.cancel_at_period_end ? (
          <span className="badge badge-warning">Cancels {formatDate(cancelDate)}</span>
        ) : isTrialing ? (
          <span className="badge badge-info">
            Free trial ends {formatDate(subscription.trial_end)}
          </span>
        ) : subscription.status ? (
          <span className="badge badge-success">{subscription.status}</span>
        ) : null}
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
          and document-upload tokens at no charge. After the trial ends on{" "}
          {formatDate(subscription.trial_end)}, the service continues automatically
          when a payment method is on file — otherwise the account drops to the free
          tier.
        </p>
      ) : null}

      {subscription.cancel_at_period_end ? (
        <>
          <p>Your service will end on {formatDate(cancelDate)}.</p>
          {isVerified ? (
            <button
              className="primary-button"
              disabled={busyAction !== null}
              onClick={() => runAction("reactivate", "/subscription/reactivate")}
            >
              {busyAction === "reactivate" ? "Working…" : "Don't cancel subscription"}
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
          onSelectTier={(tier) =>
            runAction(`change:${tier}`, "/subscription/change", { tier })
          }
        />
      ) : null}

      {actionMessage ? <p className="success-text">{actionMessage}</p> : null}
      {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
    </section>
  );
}
