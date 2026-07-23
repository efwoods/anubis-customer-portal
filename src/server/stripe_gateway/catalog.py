"""Discover the Neural Nexus tier catalog from Stripe objects.

The f-metering provisioning script (``scripts/provision_stripe_billing.py``)
stamps every product with metadata:

* ``neural_nexus_tier`` — ``free`` | ``pro`` | ``premium``
* ``neural_nexus_product_role`` — ``base`` (flat monthly fee) | ``metered``
* ``neural_nexus_meter`` — the meter event name, on metered products only
* ``neural_nexus_catalog_version`` — e.g. ``v2``; also the price lookup-key suffix

Metered prices are graduated: tier 1 (``up_to`` = the monthly allotment) costs
$0 and tier 2 is the overage rate. The portal derives allotments and overage
rates from those price tiers so pricing changes in Stripe are reflected here
without a deploy. ``STRIPE_BILLING_CONFIG_JSON`` (optional) supplies explicit
price ids as hints; discovery is the fallback and the default.
"""

from __future__ import annotations

import asyncio
import json
import re
import time

import stripe
from fastapi import HTTPException

from settings import get_portal_settings

PRODUCT_TIER_METADATA_KEY = "neural_nexus_tier"
PRODUCT_ROLE_METADATA_KEY = "neural_nexus_product_role"
PRODUCT_METER_METADATA_KEY = "neural_nexus_meter"
PRODUCT_CATALOG_VERSION_METADATA_KEY = "neural_nexus_catalog_version"
PRODUCT_ROLE_BASE = "base"
PRODUCT_ROLE_METERED = "metered"

SUBSCRIPTION_TIER_ORDER = ["free", "pro", "premium"]
ADAPTER_TRAINING_METER_EVENT_NAME = "adapter_training_units"

_CATALOG_CACHE_TTL_SECONDS = 300.0
_catalog_cache: tuple[float, dict] | None = None
_catalog_cache_lock = asyncio.Lock()

_TRIAL_DAYS_PATTERN = re.compile(r"(\d+)-day free trial")


def tier_rank(tier: str) -> int:
    try:
        return SUBSCRIPTION_TIER_ORDER.index(tier)
    except ValueError:
        return 0


def _load_billing_config_hints() -> dict:
    """Parse STRIPE_BILLING_CONFIG_JSON into {tier: {base_price, metered_prices}}."""
    raw_config = get_portal_settings().stripe_billing_config_json
    if not raw_config.strip():
        return {}
    try:
        document = json.loads(raw_config)
    except json.JSONDecodeError:
        return {}
    return document.get("tiers", {}) or {}


def _select_price_for_product(product: dict, price_list: list[dict], hinted_price_id: str | None) -> dict | None:
    """Pick the active price for one product.

    Preference order: the explicitly hinted price id, then the price whose
    lookup key ends with the product's catalog version, then the newest.
    """
    if not price_list:
        return None
    if hinted_price_id:
        for price in price_list:
            if price["id"] == hinted_price_id:
                return price
    catalog_version = (product.get("metadata") or {}).get(
        PRODUCT_CATALOG_VERSION_METADATA_KEY
    )
    if catalog_version:
        for price in price_list:
            lookup_key = price.get("lookup_key") or ""
            if lookup_key.endswith(f"_{catalog_version}"):
                return price
    return max(price_list, key=lambda price: price.get("created", 0))


def _build_catalog_sync() -> dict:
    """Synchronously assemble the tier catalog from Stripe products and prices.

    Returns ``{tier: {tier, display_name, monthly_base_fee_usd, base_price_id,
    trial_period_days, meters: {event_name: {...}}}}``.
    """
    hints = _load_billing_config_hints()

    neural_nexus_products = []
    for product_object in stripe.Product.list(active=True, limit=100).auto_paging_iter():
        product_dictionary = product_object.to_dict()
        if (product_dictionary.get("metadata") or {}).get(PRODUCT_TIER_METADATA_KEY):
            neural_nexus_products.append(product_dictionary)

    catalog: dict[str, dict] = {}
    for product in neural_nexus_products:
        product_metadata = product.get("metadata") or {}
        tier = product_metadata.get(PRODUCT_TIER_METADATA_KEY)
        role = product_metadata.get(PRODUCT_ROLE_METADATA_KEY)
        if tier not in SUBSCRIPTION_TIER_ORDER or role not in (
            PRODUCT_ROLE_BASE,
            PRODUCT_ROLE_METERED,
        ):
            continue

        tier_entry = catalog.setdefault(
            tier,
            {
                "tier": tier,
                "display_name": None,
                "monthly_base_fee_usd": 0.0,
                "base_price_id": None,
                "trial_period_days": 0,
                "meters": {},
            },
        )

        tier_hints = hints.get(tier, {}) or {}
        price_list = [
            price_object.to_dict()
            for price_object in stripe.Price.list(
                product=product["id"], active=True, limit=100, expand=["data.tiers"]
            ).auto_paging_iter()
        ]

        if role == PRODUCT_ROLE_BASE:
            selected_price = _select_price_for_product(
                product, price_list, tier_hints.get("base_price")
            )
            if selected_price is None:
                continue
            tier_entry["display_name"] = product.get("name")
            tier_entry["base_price_id"] = selected_price["id"]
            tier_entry["monthly_base_fee_usd"] = (
                selected_price.get("unit_amount") or 0
            ) / 100.0
            trial_match = _TRIAL_DAYS_PATTERN.search(product.get("description") or "")
            if trial_match:
                tier_entry["trial_period_days"] = int(trial_match.group(1))
            continue

        meter_event_name = product_metadata.get(PRODUCT_METER_METADATA_KEY)
        if not meter_event_name:
            continue
        hinted_metered_price = (tier_hints.get("metered_prices") or {}).get(
            meter_event_name
        )
        selected_price = _select_price_for_product(
            product, price_list, hinted_metered_price
        )
        if selected_price is None:
            continue

        graduated_tiers = selected_price.get("tiers") or []
        monthly_allotment = 0
        overage_cents_per_unit = 0.0
        if graduated_tiers:
            monthly_allotment = int(graduated_tiers[0].get("up_to") or 0)
        if len(graduated_tiers) > 1:
            overage_cents_per_unit = float(
                graduated_tiers[1].get("unit_amount_decimal")
                or graduated_tiers[1].get("unit_amount")
                or 0
            )

        billed_per_unit = meter_event_name == ADAPTER_TRAINING_METER_EVENT_NAME
        recurring = selected_price.get("recurring") or {}
        tier_entry["meters"][meter_event_name] = {
            "meter_event_name": meter_event_name,
            "meter_id": recurring.get("meter"),
            "price_id": selected_price["id"],
            "monthly_allotment": monthly_allotment,
            "overage_price_per_million": (
                None if billed_per_unit else round(overage_cents_per_unit * 10_000.0, 6)
            ),
            "overage_price_per_unit_usd": (
                round(overage_cents_per_unit / 100.0, 6) if billed_per_unit else None
            ),
            "unit": "units" if billed_per_unit else "tokens",
            "display_name": product.get("name"),
        }

    return catalog


async def get_tier_catalog(force_refresh: bool = False) -> dict:
    """Return the tier catalog, cached for a few minutes."""
    global _catalog_cache
    async with _catalog_cache_lock:
        if (
            not force_refresh
            and _catalog_cache is not None
            and time.monotonic() - _catalog_cache[0] < _CATALOG_CACHE_TTL_SECONDS
        ):
            return _catalog_cache[1]
        catalog = await asyncio.to_thread(_build_catalog_sync)
        _catalog_cache = (time.monotonic(), catalog)
        return catalog


def catalog_trial_tier(catalog: dict) -> str | None:
    """The tier whose free trial a signup grants, or ``None`` when none offers one.

    Exactly one tier carries a trial in the provisioned catalog (pro), but the
    catalog is discovered rather than hardcoded, so this picks the highest-ranked
    tier advertising trial days instead of assuming the name. The refund flow
    needs it to answer "which allotment is the free trial", and the client needs
    it to say whose trial a customer is on.
    """
    trial_tiers = [
        tier
        for tier in SUBSCRIPTION_TIER_ORDER
        if (catalog.get(tier) or {}).get("trial_period_days", 0) > 0
    ]
    if not trial_tiers:
        return None
    return max(trial_tiers, key=tier_rank)


def catalog_prices_for_tier(catalog: dict, tier: str) -> list[str]:
    """Ordered price ids for one tier: the flat base first, then metered prices."""
    tier_entry = catalog.get(tier)
    if not tier_entry or not tier_entry.get("base_price_id"):
        raise HTTPException(
            status_code=503,
            detail=f"The Stripe catalog has no provisioned prices for tier '{tier}'. "
            "This Stripe environment has not been provisioned — run the f-metering "
            "provision_stripe_billing.py script against this Stripe account first.",
        )
    ordered_price_ids = [tier_entry["base_price_id"]]
    for meter_entry in tier_entry["meters"].values():
        ordered_price_ids.append(meter_entry["price_id"])
    return ordered_price_ids


def public_tier_catalog(catalog: dict) -> list[dict]:
    """The catalog shaped for the client's tier switcher (no price ids)."""
    public_entries = []
    for tier in SUBSCRIPTION_TIER_ORDER:
        tier_entry = catalog.get(tier)
        if not tier_entry:
            continue
        public_entries.append(
            {
                "tier": tier,
                "display_name": tier_entry.get("display_name") or f"Neural Nexus {tier.title()} Tier",
                "monthly_base_fee_usd": tier_entry.get("monthly_base_fee_usd", 0.0),
                "trial_period_days": tier_entry.get("trial_period_days", 0),
                "meters": [
                    {
                        "meter_event_name": meter_entry["meter_event_name"],
                        "monthly_allotment": meter_entry["monthly_allotment"],
                        "overage_price_per_million": meter_entry["overage_price_per_million"],
                        "overage_price_per_unit_usd": meter_entry["overage_price_per_unit_usd"],
                        "unit": meter_entry["unit"],
                    }
                    for meter_entry in tier_entry["meters"].values()
                ],
            }
        )
    return public_entries
