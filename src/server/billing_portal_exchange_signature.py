"""Shared signing construction for billing portal exchange code redemption.

This must stay byte-for-byte identical to
``src/security/billing_portal_single_sign_on.py`` in the Neural Nexus API repo,
which verifies the signatures this server produces. The two cannot import each
other — separate repositories, separate containers — so the construction is
written out on both sides and the header names are defined once here.

The direction is the opposite of ``usage_event_signature``: there the Neural
Nexus API signs and this server verifies, here this server signs and the Neural
Nexus API verifies. The construction is the same one in both directions and the
same one Stripe uses for its webhook signatures — an HMAC-SHA256 over
``<timestamp>.<raw body bytes>`` — so the timestamp cannot be rewritten to
replay a captured redemption, and a signature cannot survive a modified body.

Signing the redemption call is what stops an exchange code from being enough on
its own: a code observed in transit is worthless to anyone who cannot also prove
possession of the shared secret, so it cannot be turned into a customer's email
address.
"""

from __future__ import annotations

import hashlib
import hmac

TIMESTAMP_HEADER_NAME = "X-Neural-Nexus-Portal-Timestamp"
SIGNATURE_HEADER_NAME = "X-Neural-Nexus-Portal-Signature"


def build_exchange_redemption_signature(
    shared_secret: str, timestamp: str, body: bytes
) -> str:
    """Return the hex HMAC-SHA256 over ``timestamp.body``."""
    signed_payload = timestamp.encode("utf-8") + b"." + body
    return hmac.new(
        shared_secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
