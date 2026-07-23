"""Invoice history and self-service refunds (verified users only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from security.identity import CustomerIdentity, require_verified_identity
from stripe_gateway import invoices as stripe_invoices
from stripe_gateway import subscriptions as stripe_subscriptions
from stripe_gateway.catalog import get_tier_catalog

router = APIRouter(tags=["Invoices"])

_REFUND_OUTCOME_MESSAGES = {
    "none": "The refund was issued. You have no live subscription to change.",
    "canceled_immediately": (
        "The refund was issued and your subscription ended immediately. Your "
        "account is on the free tier now, with the free-tier allotment. "
        "Resubscribing before this period ends keeps the allotment you already "
        "paid for."
    ),
    "ends_at_period_end": (
        "The refund was issued. Your free trial continues until the end of the "
        "current period, then the account moves to the free tier."
    ),
    "downgraded_to_trial_tier_and_ends_at_period_end": (
        "The refund was issued and the paid upgrade was removed immediately. "
        "Your free trial continues at its original allotment until the end of "
        "the current period, then the account moves to the free tier."
    ),
}


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
    """Refund one paid invoice and settle the subscription it paid for.

    A refund is never only a money movement here: leaving the subscription
    running would give the customer a period they no longer paid for. After the
    refund succeeds, ``apply_refund_to_subscription`` ends a paid subscription
    immediately (dropping the account to the free-tier allotment at once via the
    Neural Nexus webhook) or, during a free trial, retains the trial to the
    period boundary while unwinding any paid upgrade above the trial tier.

    The refund is reported as successful even when the follow-up subscription
    change fails — the money has already moved, and reporting failure would
    invite a duplicate refund attempt. The failure is surfaced in
    ``subscription_change_error`` so the customer knows to check their plan.
    """
    refund = await stripe_invoices.refund_invoice(identity.customer_id, invoice_id)
    catalog = await get_tier_catalog()
    try:
        outcome = await stripe_subscriptions.apply_refund_to_subscription(
            identity.customer_id, catalog
        )
    except Exception as subscription_error:  # noqa: BLE001 - refund already settled
        return {
            **refund,
            "subscription_action": "failed",
            "subscription_change_error": str(subscription_error),
            "message": (
                "The refund was issued, but your subscription could not be "
                "updated automatically. Check your plan below, or contact "
                "support."
            ),
        }
    return {
        **refund,
        "subscription_action": outcome["action"],
        "subscription_tier": outcome["tier"],
        "message": _REFUND_OUTCOME_MESSAGES.get(
            outcome["action"], "The refund was issued."
        ),
    }
