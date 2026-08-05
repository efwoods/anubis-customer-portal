"""Shared signing construction for usage events pushed by the Neural Nexus API.

This must stay byte-for-byte identical to
``src/anubis/utils/billing/usage_notification.py`` in the Neural Nexus API repo,
which produces the signatures this server verifies. The two cannot import each
other — separate repositories, separate containers — so the construction is
written out on both sides and the header names are defined once here.

The signed material is ``<timestamp>.<raw body bytes>``, the same shape Stripe
uses for its own webhook signatures. Binding the timestamp into the signature is
what lets the receiver reject a replayed body by age; signing the raw bytes
rather than a re-serialized document is what stops a signature surviving a
modified payload that happens to parse to the same object.
"""

from __future__ import annotations

import hashlib
import hmac

TIMESTAMP_HEADER_NAME = "X-Neural-Nexus-Usage-Timestamp"
SIGNATURE_HEADER_NAME = "X-Neural-Nexus-Usage-Signature"


def build_usage_event_signature(
    shared_secret: str, timestamp: str, body: bytes
) -> str:
    """Return the hex HMAC-SHA256 over ``timestamp.body``."""
    signed_payload = timestamp.encode("utf-8") + b"." + body
    return hmac.new(
        shared_secret.encode("utf-8"), signed_payload, hashlib.sha256
    ).hexdigest()
