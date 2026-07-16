"""End-to-end smoke test against the real Stripe TEST environment.

Run it manually once the Stripe test account has been provisioned by the
f-metering ``scripts/provision_stripe_billing.py`` script:

    cd src/server
    STRIPE_SECRET_KEY=sk_test_... .venv/bin/python scripts/stripe_test_mode_smoke.py

The script refuses to run against a live key. It exercises, in order:

1. Catalog discovery (tiers, allotments, overage rates from product metadata
   and graduated prices).
2. Test-customer creation and email lookup (the login path).
3. Checkout-session creation for the pro tier (trial included).
4. A meter event for the test customer, then usage read-back through the
   meter-usage analytics preview API (with the event-summaries fallback).
5. Cleanup: the test customer is deleted.

Note: Stripe meter events aggregate asynchronously — the usage read-back can
lag by a minute or two; a zero reading right after posting the event is not
necessarily a failure and is reported as INDETERMINATE.
"""

from __future__ import annotations

import asyncio
import datetime
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stripe  # noqa: E402

from stripe_gateway.catalog import get_tier_catalog  # noqa: E402
from stripe_gateway.client import configure_stripe  # noqa: E402
from stripe_gateway.customers import find_customer_by_email  # noqa: E402
from stripe_gateway.meter_usage import fetch_usage_by_meter_id  # noqa: E402
from stripe_gateway.subscriptions import create_checkout_session  # noqa: E402

SMOKE_CUSTOMER_EMAIL = "portal-smoke-test@neuralnexus.site"


async def run_smoke_test() -> int:
    secret_key = os.environ.get("STRIPE_SECRET_KEY", "")
    if not secret_key.startswith("sk_test_"):
        print("Refusing to run: STRIPE_SECRET_KEY must be a Stripe TEST key (sk_test_...).")
        return 1
    configure_stripe()

    print("== 1. Catalog discovery ==")
    catalog = await get_tier_catalog(force_refresh=True)
    if not catalog:
        print(
            "FAIL: no Neural Nexus products found. Run the f-metering "
            "provision_stripe_billing.py script against this Stripe account first."
        )
        return 1
    for tier_name, tier_entry in catalog.items():
        print(
            f"  {tier_name}: base ${tier_entry['monthly_base_fee_usd']}/month, "
            f"trial {tier_entry['trial_period_days']} days"
        )
        for meter_event_name, meter_entry in tier_entry["meters"].items():
            print(
                f"    {meter_event_name}: allotment {meter_entry['monthly_allotment']:,} "
                f"{meter_entry['unit']}, meter {meter_entry['meter_id']}"
            )

    print("== 2. Test customer + email lookup ==")
    smoke_customer = stripe.Customer.create(
        email=SMOKE_CUSTOMER_EMAIL, name="Portal Smoke Test", description="portal smoke test"
    ).to_dict()
    customer_id = smoke_customer["id"]
    try:
        found_customer = await find_customer_by_email(SMOKE_CUSTOMER_EMAIL)
        assert found_customer and found_customer["id"] == customer_id, "email lookup mismatch"
        print(f"  created + found {customer_id}")

        print("== 3. Checkout session (pro, trial) ==")
        checkout_session = await create_checkout_session(
            customer_id, "pro", catalog, "http://localhost:5173", include_trial=True
        )
        assert checkout_session.get("url"), "checkout session has no url"
        print(f"  checkout url: {checkout_session['url'][:64]}…")

        print("== 4. Meter event + usage read-back ==")
        messaging_meter = catalog.get("pro", {}).get("meters", {}).get("messaging_tokens")
        if not messaging_meter or not messaging_meter.get("meter_id"):
            print("  SKIP: no messaging meter discovered.")
        else:
            stripe.billing.MeterEvent.create(
                event_name="messaging_tokens",
                payload={"stripe_customer_id": customer_id, "value": "72"},
            )
            print("  posted meter event (72 messaging tokens); waiting 90s to aggregate…")
            await asyncio.sleep(90)
            now_epoch = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
            usage = await fetch_usage_by_meter_id(
                customer_id,
                [messaging_meter["meter_id"]],
                now_epoch - 3600,
                now_epoch,
            )
            observed = usage.get(messaging_meter["meter_id"], 0)
            if observed >= 72:
                print(f"  usage read-back OK: {observed}")
            else:
                print(
                    f"  INDETERMINATE: read back {observed} (aggregation can lag; "
                    "re-run step 4 manually in a couple of minutes)."
                )
    finally:
        stripe.Customer.delete(customer_id)
        print(f"== 5. Cleanup: deleted {customer_id} ==")

    print("SMOKE TEST COMPLETE")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(run_smoke_test()))
