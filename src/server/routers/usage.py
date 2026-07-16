"""Per-meter usage versus allotment for the current billing period."""

from __future__ import annotations

import datetime

from fastapi import APIRouter, Depends

from security.identity import CustomerIdentity, resolve_customer_identity
from stripe_gateway import meter_usage as stripe_meter_usage
from stripe_gateway import subscriptions as stripe_subscriptions
from stripe_gateway.catalog import get_tier_catalog

router = APIRouter(tags=["Usage"])


def _calendar_month_bounds_epoch() -> tuple[int, int]:
    now = datetime.datetime.now(datetime.timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if month_start.month == 12:
        next_month_start = month_start.replace(year=month_start.year + 1, month=1)
    else:
        next_month_start = month_start.replace(month=month_start.month + 1)
    return int(month_start.timestamp()), int(next_month_start.timestamp())


def _iso_from_epoch(epoch_seconds: int) -> str:
    return datetime.datetime.fromtimestamp(
        epoch_seconds, tz=datetime.timezone.utc
    ).isoformat()


@router.get("/usage")
async def get_usage(
    identity: CustomerIdentity = Depends(resolve_customer_identity),
) -> dict:
    """Allotment, usage to date, remaining, and overage rate per granted meter.

    Field names match the Neural Nexus API's /verify_subscription_status so a
    client can consume either source interchangeably.
    """
    catalog = await get_tier_catalog()

    subscription = None
    if identity.customer_id:
        subscription = await stripe_subscriptions.get_current_subscription(
            identity.customer_id
        )
    tier = stripe_subscriptions.subscription_tier(subscription, catalog)

    period_start, period_end = (None, None)
    if subscription is not None:
        period_start, period_end = stripe_subscriptions.subscription_period_bounds(
            subscription
        )
    if not period_start or not period_end:
        period_start, period_end = _calendar_month_bounds_epoch()

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
        used_to_date = int(usage_by_meter_id.get(meter_entry.get("meter_id"), 0))
        monthly_allotment = meter_entry["monthly_allotment"]
        meters[event_name] = {
            "monthly_allotment": monthly_allotment,
            "used_to_date": used_to_date,
            "remaining": max(0, monthly_allotment - used_to_date),
            "overage_price_per_million": meter_entry["overage_price_per_million"],
            "overage_price_per_unit_usd": meter_entry["overage_price_per_unit_usd"],
            "unit": meter_entry["unit"],
        }

    return {
        "tier": tier,
        "status": subscription.get("status") if subscription else None,
        "trialing": bool(subscription and subscription.get("status") == "trialing"),
        "usage_period_start": _iso_from_epoch(period_start),
        "usage_period_end": _iso_from_epoch(period_end),
        "meters": meters,
    }
