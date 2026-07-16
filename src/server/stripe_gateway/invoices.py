"""Invoice history and self-service refunds."""

from __future__ import annotations

import asyncio

import stripe
from fastapi import HTTPException


def _refund_state(invoice: dict) -> tuple[bool, str | None]:
    """Return ``(refundable, payment_intent_id)`` for one expanded invoice."""
    if invoice.get("status") != "paid" or (invoice.get("amount_paid") or 0) <= 0:
        return False, None
    payment_intent = invoice.get("payment_intent")
    if not isinstance(payment_intent, dict):
        return False, payment_intent if isinstance(payment_intent, str) else None
    latest_charge = payment_intent.get("latest_charge")
    if isinstance(latest_charge, dict) and latest_charge.get("refunded"):
        return False, payment_intent.get("id")
    return True, payment_intent.get("id")


def _summarize_invoice(invoice: dict) -> dict:
    line_descriptions = [
        line.get("description")
        for line in (invoice.get("lines", {}) or {}).get("data", [])
        if line.get("description")
    ]
    refundable, _ = _refund_state(invoice)
    payment_intent = invoice.get("payment_intent")
    already_refunded = False
    if isinstance(payment_intent, dict):
        latest_charge = payment_intent.get("latest_charge")
        if isinstance(latest_charge, dict):
            already_refunded = bool(latest_charge.get("refunded"))
    return {
        "invoice_id": invoice.get("id"),
        "created": invoice.get("created"),
        "status": invoice.get("status"),
        "amount_due": invoice.get("amount_due"),
        "amount_paid": invoice.get("amount_paid"),
        "currency": invoice.get("currency"),
        "hosted_invoice_url": invoice.get("hosted_invoice_url"),
        "invoice_pdf": invoice.get("invoice_pdf"),
        "line_descriptions": line_descriptions[:4],
        "refundable": refundable,
        "refunded": already_refunded,
    }


async def list_invoices(customer_id: str, limit: int = 24) -> list[dict]:
    def _list() -> list[dict]:
        invoice_list = stripe.Invoice.list(
            customer=customer_id,
            limit=limit,
            expand=["data.payment_intent.latest_charge"],
        ).to_dict()
        return [_summarize_invoice(invoice) for invoice in invoice_list.get("data", [])]

    return await asyncio.to_thread(_list)


async def refund_invoice(customer_id: str, invoice_id: str) -> dict:
    """Fully refund one paid invoice belonging to this customer."""

    def _refund() -> dict:
        invoice = stripe.Invoice.retrieve(
            invoice_id, expand=["payment_intent.latest_charge"]
        ).to_dict()
        if invoice.get("customer") != customer_id:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        refundable, payment_intent_id = _refund_state(invoice)
        if not refundable or not payment_intent_id:
            raise HTTPException(
                status_code=409,
                detail="This invoice cannot be refunded (it is unpaid, zero-amount, "
                "or already refunded).",
            )
        refund = stripe.Refund.create(payment_intent=payment_intent_id).to_dict()
        return {
            "refund_id": refund.get("id"),
            "status": refund.get("status"),
            "amount": refund.get("amount"),
            "currency": refund.get("currency"),
            "invoice_id": invoice_id,
        }

    return await asyncio.to_thread(_refund)
