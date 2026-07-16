"""Stripe SDK configuration.

The portal pins a stable Stripe API version ("acacia") so object shapes the
code relies on (``invoice.payment_intent``, ``subscription.current_period_end``)
are guaranteed regardless of the SDK's default pin. The meter-usage analytics
call sends its own preview ``Stripe-Version`` header explicitly (see
``meter_usage.py``) and is unaffected by this pin.
"""

from __future__ import annotations

import stripe

from settings import get_portal_settings

PINNED_STRIPE_API_VERSION = "2024-12-18.acacia"


def configure_stripe() -> None:
    settings = get_portal_settings()
    stripe.api_key = settings.stripe_secret_key
    stripe.api_version = PINNED_STRIPE_API_VERSION
