"""Read per-customer meter usage from Stripe.

Primary source: the meter-usage analytics preview endpoint
(``GET /v1/billing/analytics/meter_usage``, ``Stripe-Version:
2025-07-30.preview``) — one call returns every requested meter. The Stripe
Python SDK does not wrap preview endpoints, so the call goes through httpx
with an explicit version header.

Fallback: the GA meter event-summaries endpoint per meter
(``GET /v1/billing/meters/{meter_id}/event_summaries``) when the preview API
is unavailable to the account.

All timestamps sent to either endpoint are aligned down to minute boundaries
(both APIs reject unaligned timestamps).
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx
import stripe

from settings import get_portal_settings

logger = logging.getLogger(__name__)

METER_USAGE_ANALYTICS_PREVIEW_VERSION = "2025-07-30.preview"
_STRIPE_API_BASE_URL = "https://api.stripe.com"

# When the account is not enrolled in the analytics preview, the endpoint 404s;
# remember that for a while so every usage read does not retry a dead endpoint.
_PREVIEW_UNAVAILABLE_RETRY_SECONDS = 3600.0
_preview_unavailable_until_monotonic: float = 0.0


def _align_to_minute(epoch_seconds: int) -> int:
    return epoch_seconds - (epoch_seconds % 60)


async def _fetch_usage_from_analytics_preview(
    customer_id: str,
    meter_ids: list[str],
    start_time: int,
    end_time: int,
) -> dict[str, int]:
    query_parameters: list[tuple[str, str]] = [
        ("customer", customer_id),
        ("start_time", str(_align_to_minute(start_time))),
        ("end_time", str(_align_to_minute(end_time))),
    ]
    for index, meter_id in enumerate(meter_ids):
        query_parameters.append((f"meters[{index}][meter_id]", meter_id))

    settings = get_portal_settings()
    async with httpx.AsyncClient(timeout=20.0) as http_client:
        response = await http_client.get(
            f"{_STRIPE_API_BASE_URL}/v1/billing/analytics/meter_usage",
            params=query_parameters,
            auth=(settings.stripe_secret_key, ""),
            headers={"Stripe-Version": METER_USAGE_ANALYTICS_PREVIEW_VERSION},
        )
    response.raise_for_status()
    usage_by_meter_id: dict[str, int] = {meter_id: 0 for meter_id in meter_ids}
    for usage_row in response.json().get("data", []):
        row_meter_id = usage_row.get("meter_id")
        if row_meter_id in usage_by_meter_id:
            usage_by_meter_id[row_meter_id] += int(usage_row.get("bucket_value") or 0)
    return usage_by_meter_id


async def _fetch_usage_from_event_summaries(
    customer_id: str,
    meter_ids: list[str],
    start_time: int,
    end_time: int,
) -> dict[str, int]:
    def _sum_meter(meter_id: str) -> int:
        total_value = 0
        summaries = stripe.billing.Meter.list_event_summaries(
            meter_id,
            customer=customer_id,
            start_time=_align_to_minute(start_time),
            end_time=_align_to_minute(end_time),
            limit=100,
        )
        for summary_object in summaries.auto_paging_iter():
            summary_dictionary = summary_object.to_dict()
            total_value += int(summary_dictionary.get("aggregated_value") or 0)
        return total_value

    usage_by_meter_id: dict[str, int] = {}
    for meter_id in meter_ids:
        usage_by_meter_id[meter_id] = await asyncio.to_thread(_sum_meter, meter_id)
    return usage_by_meter_id


async def fetch_usage_by_meter_id(
    customer_id: str,
    meter_ids: list[str],
    start_time: int,
    end_time: int,
) -> dict[str, int]:
    """Return ``{meter_id: total usage}`` for the period. Fails open to zeros."""
    global _preview_unavailable_until_monotonic
    valid_meter_ids = [meter_id for meter_id in meter_ids if meter_id]
    if not valid_meter_ids:
        return {}
    if time.monotonic() >= _preview_unavailable_until_monotonic:
        try:
            return await _fetch_usage_from_analytics_preview(
                customer_id, valid_meter_ids, start_time, end_time
            )
        except Exception as analytics_error:  # noqa: BLE001 - fall back, then fail open
            if (
                isinstance(analytics_error, httpx.HTTPStatusError)
                and analytics_error.response.status_code == 404
            ):
                _preview_unavailable_until_monotonic = (
                    time.monotonic() + _PREVIEW_UNAVAILABLE_RETRY_SECONDS
                )
            logger.warning(
                "Meter-usage analytics preview call failed (%s); falling back to "
                "event summaries.",
                analytics_error,
            )
    try:
        return await _fetch_usage_from_event_summaries(
            customer_id, valid_meter_ids, start_time, end_time
        )
    except Exception as summaries_error:  # noqa: BLE001 - fail open
        logger.error("Meter event-summaries fallback failed: %s", summaries_error)
        return {meter_id: 0 for meter_id in valid_meter_ids}
