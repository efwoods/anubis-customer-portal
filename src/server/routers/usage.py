"""Per-meter usage versus allotment for the current billing period.

The window this endpoint reports over is deliberately the SAME window the
Neural Nexus API's allotment gating counts against, reproduced from the same
inputs (``usage_period_anchor`` in Auth0 app_metadata, ``USAGE_PERIOD_DAYS``,
and the Stripe billing period). Reporting a different window is what previously
let this portal show a comfortable-looking meter while the chat app was
refusing messages with HTTP 402 — the two were measuring different spans of
time. See ``usage_period.py`` for the arithmetic.
"""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends

import auth0_gateway
import usage_observations
from security.identity import CustomerIdentity, resolve_customer_identity
from settings import get_portal_settings
from stripe_gateway import meter_usage as stripe_meter_usage
from stripe_gateway import subscriptions as stripe_subscriptions
from stripe_gateway.catalog import get_tier_catalog
from usage_period import resolve_usage_period_bounds

router = APIRouter(tags=["Usage"])


def _iso_from_epoch(epoch_seconds: int) -> str:
    return datetime.datetime.fromtimestamp(
        epoch_seconds, tz=datetime.timezone.utc
    ).isoformat()


async def _resolve_pay_per_use_enabled(
    identity: CustomerIdentity, subscription_status: str | None
) -> bool:
    if not identity.is_verified or not identity.email:
        return False
    explicit_flag = await auth0_gateway.read_pay_per_use_enabled(identity.email)
    if explicit_flag is not None:
        return explicit_flag
    return auth0_gateway.infer_pay_per_use_enabled(subscription_status)


@router.get("/usage")
async def get_usage(
    identity: CustomerIdentity = Depends(resolve_customer_identity),
) -> dict:
    """Allotment, usage to date, remaining, and overage rate per granted meter.

    Field names match the Neural Nexus API's /verify_subscription_status so a
    client can consume either source interchangeably. Each meter also reports
    ``over_allotment`` — how far past the included allotment usage has run —
    because with pay-per-use enabled a customer keeps working past the
    allotment and needs to see the billable overage rather than a bar pinned at
    "0 remaining".
    """
    catalog = await get_tier_catalog()

    subscription = None
    if identity.customer_id:
        subscription = await stripe_subscriptions.get_current_subscription(
            identity.customer_id
        )
    tier = stripe_subscriptions.subscription_tier(subscription, catalog)

    stripe_period_start, stripe_period_end = (None, None)
    if subscription is not None:
        (
            stripe_period_start,
            stripe_period_end,
        ) = stripe_subscriptions.subscription_period_bounds(subscription)

    usage_period_anchor = None
    if identity.is_verified and identity.email:
        usage_period_anchor = await auth0_gateway.read_usage_period_anchor(
            identity.email
        )
    period_start, period_end = resolve_usage_period_bounds(
        usage_period_days=get_portal_settings().usage_period_days,
        usage_period_anchor=usage_period_anchor,
        stripe_period_start=stripe_period_start,
        stripe_period_end=stripe_period_end,
    )

    tier_meters: dict = (catalog.get(tier) or {}).get("meters", {})
    meter_id_by_event_name = {
        event_name: meter_entry.get("meter_id")
        for event_name, meter_entry in tier_meters.items()
    }

    usage_by_meter_id: dict[str, int] = {}
    if identity.customer_id and meter_id_by_event_name:
        now_epoch = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
        usage_by_meter_id = await stripe_meter_usage.fetch_usage_by_meter_id(
            identity.customer_id,
            [meter_id for meter_id in meter_id_by_event_name.values() if meter_id],
            period_start,
            min(period_end, now_epoch),
        )

    meters: dict[str, dict] = {}
    for event_name, meter_entry in tier_meters.items():
        stripe_used_to_date = int(usage_by_meter_id.get(meter_entry.get("meter_id"), 0))
        # Stripe governs what the customer is billed, but its meter aggregation
        # lags the request that produced the usage. The Neural Nexus API pushes
        # the reconciled figure to /internal/usage-event the moment a turn is
        # metered, so take whichever is larger: the pushed value carries the
        # display until Stripe catches up and overtakes it, and the two converge
        # on the same number. This is the same reconciliation the API applies in
        # reconcile_period_usage, so the portal, /verify_subscription_status, and
        # the 402 gate all quote one figure.
        observed_used_to_date = usage_observations.observed_usage(
            identity.customer_id, event_name, period_start
        )
        used_to_date = (
            stripe_used_to_date
            if observed_used_to_date is None
            else max(stripe_used_to_date, observed_used_to_date)
        )
        monthly_allotment = meter_entry["monthly_allotment"]
        meters[event_name] = {
            "monthly_allotment": monthly_allotment,
            "used_to_date": used_to_date,
            "remaining": max(0, monthly_allotment - used_to_date),
            "over_allotment": max(0, used_to_date - monthly_allotment),
            "overage_price_per_million": meter_entry["overage_price_per_million"],
            "overage_price_per_unit_usd": meter_entry["overage_price_per_unit_usd"],
            "unit": meter_entry["unit"],
        }

    subscription_status = subscription.get("status") if subscription else None
    return {
        "tier": tier,
        "status": subscription_status,
        "trialing": subscription_status == "trialing",
        "pay_per_use_enabled": await _resolve_pay_per_use_enabled(
            identity, subscription_status
        ),
        "usage_period_start": _iso_from_epoch(period_start),
        "usage_period_end": _iso_from_epoch(period_end),
        "meters": meters,
    }
