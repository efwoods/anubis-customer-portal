"""Subscription reads and mutations, mirroring the Neural Nexus API semantics.

* No live subscription → Stripe Checkout session for the requested tier.
* Upgrade → immediate item swap with prorations.
* Downgrade to a paid tier → subscription schedule phase at the period boundary
  (the current allotment continues until then).
* Downgrade to free / cancel → ``cancel_at_period_end``; the Neural Nexus API's
  ``customer.subscription.deleted`` webhook creates the $0 free-tier
  subscription afterwards, so the portal never has to.

The Neural Nexus API's ``/stripe/webhook`` keeps Auth0 ``app_metadata`` in
sync with everything done here — the portal never writes subscription status.
"""

from __future__ import annotations

import asyncio
import logging

import stripe

from stripe_gateway.catalog import (
    catalog_prices_for_tier,
    catalog_trial_tier,
    tier_rank,
)
from stripe_gateway.payment_methods import reconcile_payment_methods

logger = logging.getLogger(__name__)

SUBSCRIPTION_TIER_METADATA_KEY = "neural_nexus_tier"
TRIAL_USED_CUSTOMER_METADATA_KEY = "neural_nexus_trial_used"

_LIVE_SUBSCRIPTION_STATUSES = ("active", "trialing", "past_due", "unpaid")


async def get_current_subscription(customer_id: str) -> dict | None:
    """Return the customer's newest live subscription, or None."""

    def _list_subscriptions() -> dict | None:
        subscription_list = stripe.Subscription.list(
            customer=customer_id, status="all", limit=20
        ).to_dict()
        live_subscriptions = [
            subscription
            for subscription in subscription_list.get("data", [])
            if subscription.get("status") in _LIVE_SUBSCRIPTION_STATUSES
        ]
        if not live_subscriptions:
            return None
        return max(live_subscriptions, key=lambda subscription: subscription.get("created", 0))

    return await asyncio.to_thread(_list_subscriptions)


def subscription_tier(subscription: dict | None, catalog: dict) -> str:
    """The tier a subscription represents; anonymous/no subscription → free."""
    if subscription is None:
        return "free"
    metadata_tier = (subscription.get("metadata") or {}).get(
        SUBSCRIPTION_TIER_METADATA_KEY
    )
    if metadata_tier in catalog:
        return metadata_tier
    # Fallback: match the base price against the catalog.
    subscription_price_ids = {
        item.get("price", {}).get("id")
        for item in (subscription.get("items", {}) or {}).get("data", [])
    }
    for tier, tier_entry in catalog.items():
        if tier_entry.get("base_price_id") in subscription_price_ids:
            return tier
    return "free"


def subscription_period_bounds(subscription: dict) -> tuple[int | None, int | None]:
    """Current period start/end epochs; falls back to the first item's bounds
    (newer Stripe API versions moved the fields onto subscription items)."""
    period_start = subscription.get("current_period_start")
    period_end = subscription.get("current_period_end")
    if period_start and period_end:
        return period_start, period_end
    item_list = (subscription.get("items", {}) or {}).get("data", [])
    if item_list:
        return (
            item_list[0].get("current_period_start"),
            item_list[0].get("current_period_end"),
        )
    return None, None


async def customer_has_used_trial(customer: dict, customer_id: str) -> bool:
    if (customer.get("metadata") or {}).get(TRIAL_USED_CUSTOMER_METADATA_KEY):
        return True

    def _any_prior_trial() -> bool:
        subscription_list = stripe.Subscription.list(
            customer=customer_id, status="all", limit=100
        ).to_dict()
        return any(
            subscription.get("trial_start")
            for subscription in subscription_list.get("data", [])
        )

    return await asyncio.to_thread(_any_prior_trial)


async def create_checkout_session(
    customer_id: str,
    tier: str,
    catalog: dict,
    client_base_url: str,
    include_trial: bool,
) -> dict:
    """Create a subscription-mode Checkout session for one tier.

    The free tier always collects a payment method (it is the pay-per-use
    billing vehicle). A pro trial does not require a card up front; the trial
    cancels at its end when no payment method was added (the Neural Nexus API
    webhook then drops the customer to the free tier).

    Saved cards are reconciled and then explicitly offered
    (``saved_payment_method_options``) so a customer who already has a card on
    file sees it here instead of an empty card form — and therefore does not
    retype the same card into a duplicate PaymentMethod. See
    ``payment_methods.reconcile_payment_methods`` for why the default Stripe
    behavior hides those cards.
    """
    ordered_price_ids = catalog_prices_for_tier(catalog, tier)
    line_items = [{"price": ordered_price_ids[0], "quantity": 1}] + [
        {"price": price_id} for price_id in ordered_price_ids[1:]
    ]
    trial_period_days = catalog[tier].get("trial_period_days", 0)

    await reconcile_payment_methods(customer_id)

    checkout_parameters: dict = {
        "mode": "subscription",
        "customer": customer_id,
        "line_items": line_items,
        "success_url": f"{client_base_url}?checkout=success",
        "cancel_url": f"{client_base_url}?checkout=canceled",
        "subscription_data": {
            "metadata": {SUBSCRIPTION_TIER_METADATA_KEY: tier},
        },
        "saved_payment_method_options": {
            "payment_method_save": "enabled",
            "allow_redisplay_filters": ["always", "limited", "unspecified"],
        },
    }
    if tier == "free":
        checkout_parameters["payment_method_collection"] = "always"
    elif include_trial and trial_period_days > 0:
        checkout_parameters["payment_method_collection"] = "if_required"
        checkout_parameters["subscription_data"]["trial_period_days"] = trial_period_days
        checkout_parameters["subscription_data"]["trial_settings"] = {
            "end_behavior": {"missing_payment_method": "cancel"}
        }

    def _create_session() -> dict:
        try:
            return stripe.checkout.Session.create(**checkout_parameters).to_dict()
        except stripe.error.InvalidRequestError as invalid_request_error:
            # ``allow_redisplay_filters`` postdates the pinned API version on
            # some accounts. Reconciling already promoted every saved card to
            # allow_redisplay="always", which Checkout prefills by default, so
            # dropping the filter costs nothing — but losing the session would.
            if "allow_redisplay_filters" not in str(invalid_request_error):
                raise
            logger.info(
                "Stripe rejected allow_redisplay_filters; retrying checkout "
                "without it (saved cards are already marked always-reusable)."
            )
            retry_parameters = dict(checkout_parameters)
            retry_parameters["saved_payment_method_options"] = {
                "payment_method_save": "enabled"
            }
            return stripe.checkout.Session.create(**retry_parameters).to_dict()

    return await asyncio.to_thread(_create_session)


async def release_pending_schedule(subscription: dict) -> None:
    """Release any not-yet-finished subscription schedule (pending downgrade)."""
    schedule_id = subscription.get("schedule")
    if not schedule_id:
        return

    def _release() -> None:
        schedule = stripe.SubscriptionSchedule.retrieve(schedule_id).to_dict()
        if schedule.get("status") in ("active", "not_started"):
            stripe.SubscriptionSchedule.release(schedule_id)

    await asyncio.to_thread(_release)


async def swap_subscription_items_immediately(
    subscription: dict,
    target_tier: str,
    catalog: dict,
    proration_behavior: str = "create_prorations",
) -> dict:
    """Immediately replace every subscription item with the target tier's prices.

    ``proration_behavior`` is ``create_prorations`` for an ordinary upgrade (the
    customer owes the difference for the rest of the period) and ``none`` when
    the money has already been settled another way — notably a refund, where
    charging or crediting a proration on top of the refund would double-count
    it.
    """
    ordered_price_ids = catalog_prices_for_tier(catalog, target_tier)
    existing_items = (subscription.get("items", {}) or {}).get("data", [])
    replacement_items = [
        {"id": item["id"], "deleted": True} for item in existing_items
    ] + [{"price": ordered_price_ids[0], "quantity": 1}] + [
        {"price": price_id} for price_id in ordered_price_ids[1:]
    ]

    return await asyncio.to_thread(
        lambda: stripe.Subscription.modify(
            subscription["id"],
            items=replacement_items,
            proration_behavior=proration_behavior,
            metadata={SUBSCRIPTION_TIER_METADATA_KEY: target_tier},
        ).to_dict()
    )


async def upgrade_subscription_items(
    subscription: dict, target_tier: str, catalog: dict
) -> dict:
    """Immediately swap every subscription item to the target tier's prices."""
    return await swap_subscription_items_immediately(
        subscription, target_tier, catalog, proration_behavior="create_prorations"
    )


async def cancel_subscription_immediately(subscription_id: str) -> dict:
    """End a subscription right now rather than at the period boundary.

    Used by the refund flow: a refunded paid period must stop granting the paid
    allotment at once, not at the end of a month the customer is no longer
    paying for. Deleting the subscription fires ``customer.subscription.deleted``,
    which is what the Neural Nexus API listens to in order to pin the account to
    the free tier, restart its usage window, and record the canceled tier so a
    resubscribe inside the same period can retain what was already paid for.
    """
    return await asyncio.to_thread(
        lambda: stripe.Subscription.delete(subscription_id).to_dict()
    )


async def schedule_downgrade_at_period_end(
    subscription: dict, target_tier: str, catalog: dict
) -> dict:
    """Schedule a paid-tier downgrade to take effect at the period boundary."""
    ordered_price_ids = catalog_prices_for_tier(catalog, target_tier)
    _, period_end = subscription_period_bounds(subscription)

    def _create_schedule() -> dict:
        schedule = stripe.SubscriptionSchedule.create(
            from_subscription=subscription["id"]
        ).to_dict()
        current_phase = schedule["phases"][0]
        current_phase_items = [
            {"price": item["price"], "quantity": item.get("quantity")}
            if item.get("quantity")
            else {"price": item["price"]}
            for item in current_phase["items"]
        ]
        next_phase_items = [{"price": ordered_price_ids[0], "quantity": 1}] + [
            {"price": price_id} for price_id in ordered_price_ids[1:]
        ]
        return stripe.SubscriptionSchedule.modify(
            schedule["id"],
            end_behavior="release",
            phases=[
                {
                    "items": current_phase_items,
                    "start_date": current_phase["start_date"],
                    "end_date": current_phase["end_date"] or period_end,
                },
                {
                    "items": next_phase_items,
                    "metadata": {SUBSCRIPTION_TIER_METADATA_KEY: target_tier},
                },
            ],
        ).to_dict()

    return await asyncio.to_thread(_create_schedule)


async def get_pending_downgrade_tier(
    subscription: dict, catalog: dict
) -> str | None:
    """The tier the subscription will move to at the period boundary, if any.

    A pending cancellation drops the account to the free tier; a scheduled
    downgrade to a paid tier is encoded as the schedule's next phase. Returns
    None when nothing is pending.
    """
    if subscription.get("cancel_at_period_end"):
        return "free"

    schedule_id = subscription.get("schedule")
    if not schedule_id:
        return None

    current_tier = subscription_tier(subscription, catalog)

    def _next_phase_tier() -> str | None:
        schedule = stripe.SubscriptionSchedule.retrieve(schedule_id).to_dict()
        if schedule.get("status") not in ("active", "not_started"):
            return None
        phases = schedule.get("phases", [])
        if len(phases) < 2:
            return None
        next_phase = phases[-1]
        metadata_tier = (next_phase.get("metadata") or {}).get(
            SUBSCRIPTION_TIER_METADATA_KEY
        )
        if metadata_tier in catalog:
            tier = metadata_tier
        else:
            phase_price_ids = {
                item.get("price") for item in next_phase.get("items", [])
            }
            tier = next(
                (
                    candidate_tier
                    for candidate_tier, tier_entry in catalog.items()
                    if tier_entry.get("base_price_id") in phase_price_ids
                ),
                None,
            )
        # Only surface it as pending when it actually differs from today's tier.
        return tier if tier and tier != current_tier else None

    return await asyncio.to_thread(_next_phase_tier)


async def set_cancel_at_period_end(subscription_id: str, cancel: bool) -> dict:
    return await asyncio.to_thread(
        lambda: stripe.Subscription.modify(
            subscription_id, cancel_at_period_end=cancel
        ).to_dict()
    )


def compare_tiers(current_tier: str, target_tier: str) -> int:
    """Negative → downgrade, zero → same, positive → upgrade."""
    return tier_rank(target_tier) - tier_rank(current_tier)


async def apply_refund_to_subscription(customer_id: str, catalog: dict) -> dict:
    """Bring the subscription in line with a refund that was just issued.

    A refund that leaves the subscription running would hand the customer a paid
    period they no longer paid for, so every refund settles the subscription too.
    What "settle" means depends on whether the refunded period was a free trial:

    * **Not trialing (paid pro or premium)** — the subscription ends IMMEDIATELY.
      The Neural Nexus API's ``customer.subscription.deleted`` webhook then pins
      the account to the free tier, resets its usage window to the free-tier
      allotment at once, and records the canceled tier so resubscribing inside
      the same period retains what was already paid for.
    * **Trialing on the tier that granted the trial (pro)** — the trial is left
      alone and the subscription is set to end at the period boundary. The
      customer keeps the free-trial allotment they were given, and the account
      becomes free tier when the period closes.
    * **Trialing on a tier ABOVE the one that granted the trial (premium)** —
      only the paid upgrade is unwound: the subscription drops to the trial tier
      immediately (so premium's allotment stops right away), the free trial
      itself is retained to the period boundary at the trial tier's allotment,
      and the account becomes free tier when the period closes. No proration is
      created, because the refund already returned the money.

    Returns a description of what happened for the response message; a customer
    with no live subscription yields ``{"action": "none"}``.
    """
    subscription = await get_current_subscription(customer_id)
    if subscription is None:
        return {"action": "none", "tier": None}

    current_tier = subscription_tier(subscription, catalog)
    if subscription.get("status") != "trialing":
        await release_pending_schedule(subscription)
        await cancel_subscription_immediately(subscription["id"])
        return {"action": "canceled_immediately", "tier": current_tier}

    trial_tier = catalog_trial_tier(catalog) or current_tier
    await release_pending_schedule(subscription)
    downgraded_to_trial_tier = compare_tiers(current_tier, trial_tier) < 0
    if downgraded_to_trial_tier:
        await swap_subscription_items_immediately(
            subscription, trial_tier, catalog, proration_behavior="none"
        )
    await set_cancel_at_period_end(subscription["id"], cancel=True)
    return {
        "action": (
            "downgraded_to_trial_tier_and_ends_at_period_end"
            if downgraded_to_trial_tier
            else "ends_at_period_end"
        ),
        "tier": trial_tier,
    }
