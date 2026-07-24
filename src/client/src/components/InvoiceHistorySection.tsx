import { useEffect, useState } from "react";
import { apiRequest } from "../api";
import type { InvoiceSummary, RefundResult } from "../types";

function formatAmount(amountInMinorUnits: number, currency: string): string {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format(amountInMinorUnits / 100);
}

function formatDate(epochSeconds: number): string {
  return new Date(epochSeconds * 1000).toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function InvoiceHistorySection({
  refreshCounter,
  onChanged,
}: {
  refreshCounter: number;
  /** A refund also changes the subscription, so the whole dashboard re-syncs. */
  onChanged: () => void;
}) {
  const [invoices, setInvoices] = useState<InvoiceSummary[] | null>(null);
  const [busyInvoiceId, setBusyInvoiceId] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [localRefreshCounter, setLocalRefreshCounter] = useState(0);

  useEffect(() => {
    apiRequest<{ invoices: InvoiceSummary[] }>("/invoices")
      .then((response) => setInvoices(response.invoices))
      .catch((loadError) =>
        setErrorMessage(
          loadError instanceof Error ? loadError.message : "Could not load invoices.",
        ),
      );
  }, [refreshCounter, localRefreshCounter]);

  const refundInvoice = async (invoiceId: string) => {
    if (
      !window.confirm(
        "Issue a full refund for this invoice? Refunding also ends the plan it " +
          "paid for: a paid plan drops to the free tier immediately, and a free " +
          "trial runs to the end of the current period. This cannot be undone.",
      )
    ) {
      return;
    }
    setBusyInvoiceId(invoiceId);
    setMessage(null);
    setErrorMessage(null);
    try {
      const refund = await apiRequest<RefundResult>(
        `/invoices/${invoiceId}/refund`,
        { method: "POST" },
      );
      // The server's message already spells out what happened to the plan
      // (immediate free tier vs trial retained to period end), so surface it
      // verbatim rather than restating just the refund id.
      setMessage(refund.message);
      setLocalRefreshCounter((previous) => previous + 1);
      // The subscription changed too — re-sync the subscription and usage cards.
      onChanged();
    } catch (refundError) {
      setErrorMessage(
        refundError instanceof Error ? refundError.message : "The refund failed.",
      );
    } finally {
      setBusyInvoiceId(null);
    }
  };

  return (
    <section className="card">
      <h2>Invoice history</h2>
      {!invoices && !errorMessage ? <p>Loading…</p> : null}
      {invoices && invoices.length === 0 ? (
        <p className="muted">No invoices yet.</p>
      ) : null}

      {invoices && invoices.length > 0 ? (
        <ul className="invoice-list">
          {invoices.map((invoice) => (
            <li key={invoice.invoice_id} className="invoice-row">
              <div className="invoice-main">
                <span className="invoice-date">{formatDate(invoice.created)}</span>
                <span className="invoice-amount">
                  {formatAmount(invoice.amount_paid || invoice.amount_due, invoice.currency)}
                </span>
                <span
                  className={`badge ${
                    invoice.refunded
                      ? "badge-warning"
                      : invoice.status === "paid"
                        ? "badge-success"
                        : "badge-info"
                  }`}
                >
                  {invoice.refunded ? "Refunded" : invoice.status}
                </span>
              </div>
              {invoice.line_descriptions.length > 0 ? (
                <div className="invoice-lines muted">
                  {invoice.line_descriptions.join(" · ")}
                </div>
              ) : null}
              <div className="button-row">
                {invoice.hosted_invoice_url ? (
                  <a
                    className="link-button"
                    href={invoice.hosted_invoice_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    View
                  </a>
                ) : null}
                {invoice.invoice_pdf ? (
                  <a className="link-button" href={invoice.invoice_pdf}>
                    PDF
                  </a>
                ) : null}
                {invoice.refundable ? (
                  <button
                    className="link-button danger-link"
                    disabled={busyInvoiceId !== null}
                    onClick={() => refundInvoice(invoice.invoice_id)}
                  >
                    {busyInvoiceId === invoice.invoice_id ? "Refunding…" : "Refund"}
                  </button>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}

      {message ? <p className="success-text">{message}</p> : null}
      {errorMessage ? <p className="error-text">{errorMessage}</p> : null}
    </section>
  );
}
