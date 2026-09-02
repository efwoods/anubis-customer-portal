"""The redemption signature must match the Neural Nexus API's construction.

The API rejects a redemption whose signature it cannot reproduce, so this
construction living in two repositories is the whole risk. The expected values
below are computed independently of the module under test, from the same
definition the API repo's ``build_redemption_signature`` uses: an HMAC-SHA256
over ``<timestamp>.<raw body bytes>``.
"""

from __future__ import annotations

import hashlib
import hmac

import billing_portal_exchange_signature


def test_signature_is_the_hmac_over_timestamp_dot_body():
    shared_secret = "shared-secret"
    timestamp = "1700000000"
    body = b'{"exchange_code": "abc"}'

    expected = hmac.new(
        shared_secret.encode("utf-8"),
        timestamp.encode("utf-8") + b"." + body,
        hashlib.sha256,
    ).hexdigest()

    assert (
        billing_portal_exchange_signature.build_exchange_redemption_signature(
            shared_secret, timestamp, body
        )
        == expected
    )


def test_header_names_match_the_neural_nexus_api():
    """Header names the API reads verbatim; a rename on one side alone rejects
    every redemption as unsigned."""
    assert (
        billing_portal_exchange_signature.TIMESTAMP_HEADER_NAME
        == "X-Neural-Nexus-Portal-Timestamp"
    )
    assert (
        billing_portal_exchange_signature.SIGNATURE_HEADER_NAME
        == "X-Neural-Nexus-Portal-Signature"
    )
