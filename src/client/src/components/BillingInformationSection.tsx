import { FormEvent, useEffect, useState } from "react";
import { apiRequest } from "../api";
import type { BillingInformation } from "../types";

export function BillingInformationSection({ refreshCounter }: { refreshCounter: number }) {
  const [billingInformation, setBillingInformation] =
    useState<BillingInformation | null>(null);
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [line1, setLine1] = useState("");
  const [line2, setLine2] = useState("");
  const [city, setCity] = useState("");
  const [state, setState] = useState("");
  const [postalCode, setPostalCode] = useState("");
  const [country, setCountry] = useState("");

  const applyToForm = (information: BillingInformation) => {
    setName(information.name || "");
    setPhone(information.phone || "");
    setLine1(information.address?.line1 || "");
    setLine2(information.address?.line2 || "");
    setCity(information.address?.city || "");
    setState(information.address?.state || "");
    setPostalCode(information.address?.postal_code || "");
    setCountry(information.address?.country || "");
  };

  useEffect(() => {
    apiRequest<BillingInformation>("/billing_info")
      .then((information) => {
        setBillingInformation(information);
        applyToForm(information);
      })
      .catch((loadError) =>
        setErrorMessage(
          loadError instanceof Error
            ? loadError.message
            : "Could not load billing information.",
        ),
      );
  }, [refreshCounter]);

  const save = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setErrorMessage(null);
    try {
      const updated = await apiRequest<BillingInformation>("/billing_info", {
        method: "PUT",
        body: {
          name,
          phone,
          address: {
            line1,
            line2,
            city,
            state,
            postal_code: postalCode,
            country,
          },
        },
      });
      setBillingInformation(updated);
      applyToForm(updated);
      setEditing(false);
    } catch (saveError) {
      setErrorMessage(
        saveError instanceof Error ? saveError.message : "The update failed.",
      );
    } finally {
      setBusy(false);
    }
  };

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
        <form onSubmit={save} className="stacked-form">
          <label>
            Name
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            Phone number
            <input value={phone} onChange={(event) => setPhone(event.target.value)} />
          </label>
          <label>
            Address line 1
            <input value={line1} onChange={(event) => setLine1(event.target.value)} />
          </label>
          <label>
            Address line 2
            <input value={line2} onChange={(event) => setLine2(event.target.value)} />
          </label>
          <div className="form-grid">
            <label>
              City
              <input value={city} onChange={(event) => setCity(event.target.value)} />
            </label>
            <label>
              State
              <input value={state} onChange={(event) => setState(event.target.value)} />
            </label>
            <label>
              Postal code
              <input
                value={postalCode}
                onChange={(event) => setPostalCode(event.target.value)}
              />
            </label>
            <label>
              Country (2-letter code)
              <input
                value={country}
                maxLength={2}
                onChange={(event) => setCountry(event.target.value.toUpperCase())}
              />
            </label>
          </div>
          <div className="button-row">
            <button className="primary-button" disabled={busy}>
              {busy ? "Saving…" : "Save"}
            </button>
            <button
              type="button"
              className="link-button"
              disabled={busy}
              onClick={() => {
                applyToForm(billingInformation);
                setEditing(false);
              }}
            >
              Cancel
            </button>
          </div>
        </form>
      ) : null}

      {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
    </section>
  );
}
