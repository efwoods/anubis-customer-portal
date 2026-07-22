import { useEffect, useState } from "react";
import { apiRequest } from "../api";

interface PayPerUseToggleProps {
  enabled: boolean;
  onChanged: () => void;
}

export function PayPerUseToggle({ enabled, onChanged }: PayPerUseToggleProps) {
  // Track the flag locally so the button reflects the value the server actually
  // stored the instant a toggle succeeds, rather than waiting for the parent's
  // refetch (which can re-infer a stale value).
  const [localEnabled, setLocalEnabled] = useState(enabled);
  const [busy, setBusy] = useState(false);
  const [savedNote, setSavedNote] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    setLocalEnabled(enabled);
  }, [enabled]);

  const toggle = async () => {
    setBusy(true);
    setErrorMessage(null);
    setSavedNote(null);
    try {
      const result = await apiRequest<{ pay_per_use_enabled: boolean }>(
        "/pay_per_use",
        { method: "POST", body: { enabled: !localEnabled } },
      );
      // Trust the value the server confirms it stored, not the requested value.
      setLocalEnabled(result.pay_per_use_enabled);
      setSavedNote(
        "Saved. Changes can take up to 5 minutes to apply to the Neural Nexus " +
          "API (it caches account lookups).",
      );
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
            {localEnabled
              ? "Usage past your monthly allotment continues and bills at your tier's overage rate."
              : "Requests stop once a meter's monthly allotment is exhausted (HTTP 402)."}
          </p>
        </div>
        <button
          className={localEnabled ? "danger-button" : "primary-button"}
          disabled={busy}
          onClick={toggle}
          aria-pressed={localEnabled}
        >
          {busy
            ? "Working…"
            : localEnabled
              ? "Disable pay-per-use"
              : "Enable pay-per-use"}
        </button>
      </div>
      {savedNote ? <p className="muted">{savedNote}</p> : null}
      {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
    </div>
  );
}
