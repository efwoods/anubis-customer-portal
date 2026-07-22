import { FormEvent, useEffect, useMemo, useState } from "react";
import { loadStripe } from "@stripe/stripe-js";
import {
  Elements,
  PaymentElement,
  useElements,
  useStripe,
} from "@stripe/react-stripe-js";
import { apiRequest } from "../api";
import type { BillingInformation, PaymentMethodSummary } from "../types";

interface PaymentMethodsSectionProps {
  publishableKey: string;
  refreshCounter: number;
  onChanged: () => void;
}

function AddPaymentMethodForm({
  billingDefaults,
  onSaved,
  onCancel,
}: {
  billingDefaults: BillingInformation | null;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const stripe = useStripe();
  const elements = useElements();
  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Seed the card's billing details from the customer's billing information so
  // a newly added card starts in sync with the billing form.
  const paymentElementOptions = billingDefaults
    ? {
        defaultValues: {
          billingDetails: {
            name: billingDefaults.name || undefined,
            phone: billingDefaults.phone || undefined,
            address: billingDefaults.address
              ? {
                  line1: billingDefaults.address.line1 || undefined,
                  line2: billingDefaults.address.line2 || undefined,
                  city: billingDefaults.address.city || undefined,
                  state: billingDefaults.address.state || undefined,
                  postal_code: billingDefaults.address.postal_code || undefined,
                  country: billingDefaults.address.country || undefined,
                }
              : undefined,
          },
        },
      }
    : undefined;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!stripe || !elements) {
      return;
    }
    setBusy(true);
    setErrorMessage(null);
    const result = await stripe.confirmSetup({
      elements,
      redirect: "if_required",
    });
    setBusy(false);
    if (result.error) {
      setErrorMessage(result.error.message || "The card could not be saved.");
      return;
    }
    onSaved();
  };

  return (
    <form onSubmit={submit} className="stacked-form add-card-form">
      <PaymentElement options={paymentElementOptions} />
      <div className="button-row">
        <button className="primary-button" disabled={busy || !stripe}>
          {busy ? "Saving…" : "Save card"}
        </button>
        <button type="button" className="link-button" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
      {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
    </form>
  );
}

export function PaymentMethodsSection({
  publishableKey,
  refreshCounter,
  onChanged,
}: PaymentMethodsSectionProps) {
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethodSummary[]>([]);
  const [setupClientSecret, setSetupClientSecret] = useState<string | null>(null);
  const [billingDefaults, setBillingDefaults] = useState<BillingInformation | null>(
    null,
  );
  const [busyId, setBusyId] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const stripePromise = useMemo(
    () => (publishableKey ? loadStripe(publishableKey) : null),
    [publishableKey],
  );

  useEffect(() => {
    apiRequest<{ payment_methods: PaymentMethodSummary[] }>("/payment_methods")
      .then((response) => setPaymentMethods(response.payment_methods))
      .catch((loadError) =>
        setErrorMessage(
          loadError instanceof Error
            ? loadError.message
            : "Could not load payment methods.",
        ),
      );
  }, [refreshCounter]);

  const startAddCard = async () => {
    setErrorMessage(null);
    try {
      const [setupIntent, billingInformation] = await Promise.all([
        apiRequest<{ client_secret: string }>("/payment_methods/setup_intent", {
          method: "POST",
        }),
        apiRequest<BillingInformation>("/billing_info").catch(() => null),
      ]);
      setBillingDefaults(billingInformation);
      setSetupClientSecret(setupIntent.client_secret);
    } catch (setupError) {
      setErrorMessage(
        setupError instanceof Error ? setupError.message : "Could not start card setup.",
      );
    }
  };

  const makeDefault = async (paymentMethodId: string) => {
    setBusyId(paymentMethodId);
    setErrorMessage(null);
    try {
      await apiRequest<void>(`/payment_methods/${paymentMethodId}/default`, {
        method: "POST",
      });
      onChanged();
    } catch (defaultError) {
      setErrorMessage(
        defaultError instanceof Error ? defaultError.message : "The update failed.",
      );
    } finally {
      setBusyId(null);
    }
  };

  const removeCard = async (paymentMethodId: string) => {
    if (!window.confirm("Remove this card?")) {
      return;
    }
    setBusyId(paymentMethodId);
    setErrorMessage(null);
    try {
      await apiRequest<void>(`/payment_methods/${paymentMethodId}`, {
        method: "DELETE",
      });
      onChanged();
    } catch (removeError) {
      setErrorMessage(
        removeError instanceof Error ? removeError.message : "The removal failed.",
      );
    } finally {
      setBusyId(null);
    }
  };

  return (
    <section className="card">
      <h2>Payment method</h2>
      {paymentMethods.length === 0 ? (
        <p className="muted">No payment method on file.</p>
      ) : (
        <ul className="payment-method-list">
          {paymentMethods.map((paymentMethod) => (
            <li key={paymentMethod.payment_method_id} className="payment-method-row">
              <span className="payment-method-summary">
                {(paymentMethod.brand || "card").toUpperCase()} ••••{" "}
                {paymentMethod.last4}
                <span className="muted">
                  {" "}
                  Expires {String(paymentMethod.exp_month).padStart(2, "0")}/
                  {paymentMethod.exp_year}
                </span>
                {paymentMethod.is_default ? (
                  <span className="badge badge-success">Default</span>
                ) : null}
              </span>
              <span className="button-row">
                {!paymentMethod.is_default ? (
                  <button
                    className="link-button"
                    disabled={busyId !== null}
                    onClick={() => makeDefault(paymentMethod.payment_method_id)}
                  >
                    Make default
                  </button>
                ) : null}
                <button
                  className="link-button danger-link"
                  disabled={busyId !== null}
                  onClick={() => removeCard(paymentMethod.payment_method_id)}
                >
                  Remove
                </button>
              </span>
            </li>
          ))}
        </ul>
      )}

      {setupClientSecret && stripePromise ? (
        <Elements
          stripe={stripePromise}
          options={{ clientSecret: setupClientSecret }}
        >
          <AddPaymentMethodForm
            billingDefaults={billingDefaults}
            onSaved={() => {
              setSetupClientSecret(null);
              onChanged();
            }}
            onCancel={() => setSetupClientSecret(null)}
          />
        </Elements>
      ) : (
        <button className="secondary-button" onClick={startAddCard}>
          Add payment method
        </button>
      )}

      {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
    </section>
  );
}
