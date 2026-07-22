import { useEffect, useMemo, useState } from "react";
import { loadStripe } from "@stripe/stripe-js";
import { AddressElement, Elements, useElements } from "@stripe/react-stripe-js";
import { apiRequest } from "../api";
import type { BillingInformation } from "../types";

interface BillingInformationSectionProps {
  publishableKey: string;
  refreshCounter: number;
}

/** The Stripe Address Element form. Prefilled from the customer's billing
 *  information; on save it reads the element's structured value and writes it
 *  to the Stripe customer via /billing_info. */
function BillingAddressForm({
  billingInformation,
  onSaved,
  onCancel,
}: {
  billingInformation: BillingInformation;
  onSaved: (updated: BillingInformation) => void;
  onCancel: () => void;
}) {
  const elements = useElements();
  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const defaultValues = {
    name: billingInformation.name || undefined,
    phone: billingInformation.phone || undefined,
    address: {
      line1: billingInformation.address?.line1 || "",
      line2: billingInformation.address?.line2 || undefined,
      city: billingInformation.address?.city || "",
      state: billingInformation.address?.state || "",
      postal_code: billingInformation.address?.postal_code || "",
      country: billingInformation.address?.country || "US",
    },
  };

  const save = async () => {
    if (!elements) {
      return;
    }
    setBusy(true);
    setErrorMessage(null);
    const addressElement = elements.getElement("address");
    if (!addressElement) {
      setErrorMessage("The address form is not ready yet.");
      setBusy(false);
      return;
    }
    const { complete, value } = await addressElement.getValue();
    if (!complete) {
      setErrorMessage("Please complete the required billing address fields.");
      setBusy(false);
      return;
    }
    try {
      const updated = await apiRequest<BillingInformation>("/billing_info", {
        method: "PUT",
        body: {
          name: value.name,
          phone: value.phone,
          address: {
            line1: value.address.line1,
            line2: value.address.line2,
            city: value.address.city,
            state: value.address.state,
            postal_code: value.address.postal_code,
            country: value.address.country,
          },
        },
      });
      onSaved(updated);
    } catch (saveError) {
      setErrorMessage(
        saveError instanceof Error ? saveError.message : "The update failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="stacked-form">
      <AddressElement
        options={{
          mode: "billing",
          display: { name: "full" },
          fields: { phone: "always" },
          defaultValues,
        }}
      />
      <div className="button-row">
        <button
          className="primary-button"
          disabled={busy}
          onClick={() => {
            void save();
          }}
        >
          {busy ? "Saving…" : "Save"}
        </button>
        <button
          type="button"
          className="link-button"
          disabled={busy}
          onClick={onCancel}
        >
          Cancel
        </button>
      </div>
      {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
    </div>
  );
}

export function BillingInformationSection({
  publishableKey,
  refreshCounter,
}: BillingInformationSectionProps) {
  const [billingInformation, setBillingInformation] =
    useState<BillingInformation | null>(null);
  const [editing, setEditing] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const stripePromise = useMemo(
    () => (publishableKey ? loadStripe(publishableKey) : null),
    [publishableKey],
  );

  useEffect(() => {
    apiRequest<BillingInformation>("/billing_info")
      .then((information) => {
        setBillingInformation(information);
        setErrorMessage(null);
      })
      .catch((loadError) =>
        setErrorMessage(
          loadError instanceof Error
            ? loadError.message
            : "Could not load billing information.",
        ),
      );
  }, [refreshCounter]);

  return (
    <section className="card">
      <h2>Billing information</h2>
      {!billingInformation && !errorMessage ? <p>Loading…</p> : null}

      {billingInformation && !editing ? (
        <>
          <dl className="billing-details">
            <dt>Name</dt>
            <dd>{billingInformation.name || "—"}</dd>
            <dt>Email</dt>
            <dd>{billingInformation.email || "—"}</dd>
            <dt>Billing address</dt>
            <dd>
              {billingInformation.address?.line1 ? (
                <>
                  {billingInformation.address.line1}
                  {billingInformation.address.line2 ? (
                    <>
                      <br />
                      {billingInformation.address.line2}
                    </>
                  ) : null}
                  <br />
                  {[
                    billingInformation.address.city,
                    billingInformation.address.state,
                    billingInformation.address.postal_code,
                  ]
                    .filter(Boolean)
                    .join(", ")}{" "}
                  {billingInformation.address.country}
                </>
              ) : (
                "—"
              )}
            </dd>
            <dt>Phone number</dt>
            <dd>{billingInformation.phone || "—"}</dd>
          </dl>
          <button className="secondary-button" onClick={() => setEditing(true)}>
            Update information
          </button>
        </>
      ) : null}

      {billingInformation && editing ? (
        stripePromise ? (
          <Elements stripe={stripePromise}>
            <BillingAddressForm
              billingInformation={billingInformation}
              onSaved={(updated) => {
                setBillingInformation(updated);
                setEditing(false);
              }}
              onCancel={() => setEditing(false)}
            />
          </Elements>
        ) : (
          <p className="error-text">
            Billing address editing is unavailable: the Stripe publishable key is
            not configured.
          </p>
        )
      ) : null}

      {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
    </section>
  );
}
