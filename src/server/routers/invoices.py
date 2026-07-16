"""Invoice history and self-service refunds (verified users only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from security.identity import CustomerIdentity, require_verified_identity
from stripe_gateway import invoices as stripe_invoices

router = APIRouter(tags=["Invoices"])


@router.get("/invoices")
async def list_invoices(
    identity: CustomerIdentity = Depends(require_verified_identity),
) -> dict:
    invoice_list = await stripe_invoices.list_invoices(identity.customer_id)
    return {"invoices": invoice_list}


@router.post("/invoices/{invoice_id}/refund")
async def refund_invoice(
    invoice_id: str,
    identity: CustomerIdentity = Depends(require_verified_identity),
) -> dict:
    return await stripe_invoices.refund_invoice(identity.customer_id, invoice_id)
