import { useState } from "react";
import { apiRequest } from "../api";

interface PayPerUseToggleProps {
  enabled: boolean;
  onChanged: () => void;
}

export function PayPerUseToggle({ enabled, onChanged }: PayPerUseToggleProps) {
  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const toggle = async () => {
    setBusy(true);
    setErrorMessage(null);
    try {
      await apiRequest<{ pay_per_use_enabled: boolean }>("/pay_per_use", {
        method: "POST",
        body: { enabled: !enabled },
      });
      onChanged();
    } catch (toggleError) {
      setErrorMessage(
        toggleError instanceof Error ? toggleError.message : "The toggle failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="pay-per-use">
      <div className="pay-per-use-row">
        <div>
          <h3>Pay-per-use past allotment</h3>
          <p className="muted">
            {enabled
              ? "Usage past your monthly allotment continues and bills at your tier's overage rate."
              : "Requests stop once a meter's monthly allotment is exhausted (HTTP 402)."}
          </p>
        </div>
        <button
          className={enabled ? "danger-button" : "primary-button"}
          disabled={busy}
          onClick={toggle}
          aria-pressed={enabled}
        >
          {busy ? "Working…" : enabled ? "Disable pay-per-use" : "Enable pay-per-use"}
        </button>
      </div>
      {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
    </div>
  );
}
