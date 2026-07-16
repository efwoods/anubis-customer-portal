"""Subscription status, tier changes, cancellation, and pay-per-use."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

import auth0_gateway
from security.identity import (
    CustomerIdentity,
    require_verified_identity,
    resolve_customer_identity,
)
from settings import get_portal_settings
from stripe_gateway import customers as stripe_customers
from stripe_gateway import payment_methods as stripe_payment_methods
from stripe_gateway import subscriptions as stripe_subscriptions
from stripe_gateway.catalog import get_tier_catalog, public_tier_catalog

router = APIRouter(tags=["Subscription"])

SUBSCRIPTION_TIERS = ("free", "pro", "premium")


class TierChangeBody(BaseModel):
    tier: str


class PayPerUseBody(BaseModel):
    enabled: bool


def _iso_from_epoch(epoch_seconds: int | None) -> str | None:
    if not epoch_seconds:
        return None
    return datetime.datetime.fromtimestamp(
        epoch_seconds, tz=datetime.timezone.utc
    ).isoformat()


def _validate_tier(tier: str) -> str:
    normalized_tier = tier.strip().lower()
    if normalized_tier not in SUBSCRIPTION_TIERS:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown tier '{tier}'. Choose one of: free, pro, premium.",
        )
    return normalized_tier


async def _resolve_pay_per_use_enabled(
    identity: CustomerIdentity, subscription_status: str | None
) -> bool:
    if not identity.is_verified or not identity.email:
        return False
    explicit_flag = await auth0_gateway.read_pay_per_use_enabled(identity.email)
    if explicit_flag is not None:
        return explicit_flag
    return auth0_gateway.infer_pay_per_use_enabled(subscription_status)


@router.get("/subscription")
async def get_subscription_status(
    identity: CustomerIdentity = Depends(resolve_customer_identity),
) -> dict:
    """Subscription identity, trial/cancellation state, and the tier catalog."""
    catalog = await get_tier_catalog()
    response: dict = {
        "kind": identity.kind,
        "customer_id": identity.customer_id,
        "email": identity.email,
        "tier": "free",
        "status": None,
        "subscription_id": None,
        "trial_end": None,
        "cancel_at_period_end": False,
        "cancel_at": None,
        "current_period_start": None,
        "current_period_end": None,
        "pending_downgrade_tier": None,
        "monthly_base_fee_usd": 0.0,
        "pay_per_use_enabled": False,
        "tier_catalog": public_tier_catalog(catalog),
    }
    if identity.customer_id is None:
        return response

    subscription = await stripe_subscriptions.get_current_subscription(
        identity.customer_id
    )
    if subscription is not None:
        tier = stripe_subscriptions.subscription_tier(subscription, catalog)
        period_start, period_end = stripe_subscriptions.subscription_period_bounds(
            subscription
        )
        response.update(
            {
                "tier": tier,
                "status": subscription.get("status"),
                "subscription_id": subscription.get("id"),
                "trial_end": _iso_from_epoch(subscription.get("trial_end")),
                "cancel_at_period_end": bool(subscription.get("cancel_at_period_end")),
                "cancel_at": _iso_from_epoch(subscription.get("cancel_at")),
                "current_period_start": _iso_from_epoch(period_start),
                "current_period_end": _iso_from_epoch(period_end),
                "monthly_base_fee_usd": (catalog.get(tier) or {}).get(
                    "monthly_base_fee_usd", 0.0
                ),
            }
        )
    response["pay_per_use_enabled"] = await _resolve_pay_per_use_enabled(
        identity, response["status"]
    )
    return response


@router.post("/subscription/checkout")
async def create_subscription_checkout(
    body: TierChangeBody,
    identity: CustomerIdentity = Depends(require_verified_identity),
) -> dict:
    """Create a Stripe Checkout session when no live subscription exists."""
    target_tier = _validate_tier(body.tier)
    subscription = await stripe_subscriptions.get_current_subscription(
        identity.customer_id
    )
    if subscription is not None:
        raise HTTPException(
            status_code=409,
            detail="A live subscription already exists. Use the tier switcher "
            "(POST /subscription/change) instead of checkout.",
        )
    catalog = await get_tier_catalog()
    settings = get_portal_settings()
    customer = await stripe_customers.get_customer(identity.customer_id)
    trial_already_used = await stripe_subscriptions.customer_has_used_trial(
        customer, identity.customer_id
    )
    checkout_session = await stripe_subscriptions.create_checkout_session(
        identity.customer_id,
        target_tier,
        catalog,
        settings.client_origin_list[0],
        include_trial=not trial_already_used,
    )
    return {
        "action": "start_checkout",
        "url": checkout_session.get("url"),
        "message": "Follow this link to subscribe.",
    }


@router.post("/subscription/change")
async def change_subscription_tier(
    body: TierChangeBody,
    identity: CustomerIdentity = Depends(require_verified_identity),
) -> dict:
    """Switch tiers, mirroring the Neural Nexus API's /subscribe semantics.

    * No live subscription → returns a Checkout url (``start_checkout``).
    * Same tier, pending cancellation → reactivate.
    * Same tier, nothing pending → ``no_change_required``.
    * Higher tier → immediate item swap with prorations.
    * Lower paid tier → scheduled at the period boundary (allotment continues).
    * Free → subscription ends at the period boundary; the Neural Nexus webhook
      then drops the account to the $0 free-tier subscription.
    """
    target_tier = _validate_tier(body.tier)
    catalog = await get_tier_catalog()
    subscription = await stripe_subscriptions.get_current_subscription(
        identity.customer_id
    )

    if subscription is None:
        return await create_subscription_checkout(body, identity)

    current_tier = stripe_subscriptions.subscription_tier(subscription, catalog)
    cancellation_pending = bool(subscription.get("cancel_at_period_end"))
    tier_direction = stripe_subscriptions.compare_tiers(current_tier, target_tier)

    if tier_direction == 0:
        if cancellation_pending or subscription.get("schedule"):
            await stripe_subscriptions.release_pending_schedule(subscription)
            await stripe_subscriptions.set_cancel_at_period_end(
                subscription["id"], cancel=False
            )
            return {"action": "reactivate", "message": "Subscription reactivated."}
        return {
            "action": "no_change_required",
            "message": f"Already subscribed to the {target_tier} tier.",
        }

    # A pending cancellation or scheduled downgrade must be cleared before the
    # subscription can move to a different tier.
    await stripe_subscriptions.release_pending_schedule(subscription)
    if cancellation_pending:
        await stripe_subscriptions.set_cancel_at_period_end(
            subscription["id"], cancel=False
        )

    if tier_direction > 0:
        await stripe_subscriptions.upgrade_subscription_items(
            subscription, target_tier, catalog
        )
        return {
            "action": "change_tier",
            "message": f"Subscription changed to the {target_tier} tier.",
        }

    if target_tier == "free":
        await stripe_subscriptions.set_cancel_at_period_end(
            subscription["id"], cancel=True
        )
        return {
            "action": "change_tier",
            "message": "Subscription will end at the period boundary; you will "
            "drop to the free tier. Unused allotment continues until then.",
        }

    await stripe_subscriptions.schedule_downgrade_at_period_end(
        subscription, target_tier, catalog
    )
    return {
        "action": "change_tier",
        "message": f"Subscription will switch to the {target_tier} tier at the "
        "period boundary; your current allotment continues until then.",
    }


@router.post("/subscription/cancel")
async def cancel_subscription(
    identity: CustomerIdentity = Depends(require_verified_identity),
) -> dict:
    subscription = await stripe_subscriptions.get_current_subscription(
        identity.customer_id
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="No live subscription to cancel.")
    await stripe_subscriptions.release_pending_schedule(subscription)
    updated = await stripe_subscriptions.set_cancel_at_period_end(
        subscription["id"], cancel=True
    )
    _, period_end = stripe_subscriptions.subscription_period_bounds(updated)
    return {
        "action": "cancel",
        "cancel_at_period_end": True,
        "current_period_end": _iso_from_epoch(period_end),
        "message": "Subscription will cancel at the end of the current period.",
    }


@router.post("/subscription/reactivate")
async def reactivate_subscription(
    identity: CustomerIdentity = Depends(require_verified_identity),
) -> dict:
    subscription = await stripe_subscriptions.get_current_subscription(
        identity.customer_id
    )
    if subscription is None:
        raise HTTPException(
            status_code=404, detail="No live subscription to reactivate."
        )
    await stripe_subscriptions.release_pending_schedule(subscription)
    await stripe_subscriptions.set_cancel_at_period_end(subscription["id"], cancel=False)
    return {
        "action": "reactivate",
        "cancel_at_period_end": False,
        "message": "Subscription reactivated.",
    }


@router.post("/pay_per_use")
async def set_pay_per_use(
    body: PayPerUseBody,
    identity: CustomerIdentity = Depends(require_verified_identity),
) -> dict:
    """Enable or disable billing overage past the monthly allotment.

    Enabling requires a payment method on file; with the flag disabled, the
    Neural Nexus API refuses requests with HTTP 402 once a meter's allotment
    is exhausted.
    """
    if body.enabled:
        card_on_file = await stripe_payment_methods.has_payment_method_on_file(
            identity.customer_id
        )
        if not card_on_file:
            raise HTTPException(
                status_code=402,
                detail="Pay-per-use requires a payment method on file. Add a card "
                "in the Payment method section first.",
            )
    await auth0_gateway.write_pay_per_use_enabled(identity.email, body.enabled)
    return {"pay_per_use_enabled": body.enabled}
