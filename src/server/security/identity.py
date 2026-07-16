"""Resolve the customer identity for a request.

Two identity kinds exist:

* ``verified`` — a bearer session token minted after email one-time-passcode
  verification; carries the Stripe customer id and email.
* ``anonymous`` — no (valid) bearer token; the client ip is hashed with the
  exact same sha256 scheme the Neural Nexus API uses
  (``hashlib.sha256(x_forwarded_for.encode()).hexdigest()``) and matched
  against a Stripe customer carrying ``metadata.anonymous_hashed_ip``.
  Anonymous users are always free tier and read-only.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request

from security.session import decode_session_token
from settings import PortalSettings, get_portal_settings
from stripe_gateway import customers as stripe_customers

# Matches the f-metering development-mode fallback so a local portal against
# the same Stripe test account resolves the same anonymous customer.
_DEVELOPMENT_MODE_CLIENT_IP = "172.18.0.1"


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass
class CustomerIdentity:
    kind: str  # "verified" | "anonymous"
    customer_id: str | None
    email: str | None = None
    hashed_ip: str | None = None

    @property
    def is_verified(self) -> bool:
        return self.kind == "verified"


def _client_ip_for_request(request: Request, settings: PortalSettings) -> str:
    if settings.dev_mode_enabled:
        return _DEVELOPMENT_MODE_CLIENT_IP
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for
    return request.client.host if request.client else _DEVELOPMENT_MODE_CLIENT_IP


async def resolve_customer_identity(
    request: Request,
    settings: PortalSettings = Depends(get_portal_settings),
) -> CustomerIdentity:
    authorization_header = request.headers.get("authorization", "")
    if authorization_header.lower().startswith("bearer "):
        session_claims = decode_session_token(
            settings, authorization_header.split(" ", 1)[1].strip()
        )
        if session_claims is not None:
            return CustomerIdentity(
                kind="verified",
                customer_id=session_claims["sub"],
                email=session_claims.get("email"),
            )
        raise HTTPException(status_code=401, detail="Session is invalid or expired. Sign in again.")

    hashed_ip = _hash_key(_client_ip_for_request(request, settings))
    anonymous_customer_id = await stripe_customers.find_customer_id_by_anonymous_hashed_ip(
        hashed_ip
    )
    return CustomerIdentity(kind="anonymous", customer_id=anonymous_customer_id, hashed_ip=hashed_ip)


async def require_verified_identity(
    identity: CustomerIdentity = Depends(resolve_customer_identity),
) -> CustomerIdentity:
    if not identity.is_verified:
        raise HTTPException(
            status_code=401,
            detail="This action requires a verified account. Sign in with your email, "
            "or create an account first.",
        )
    return identity


async def require_customer_identity(
    identity: CustomerIdentity = Depends(resolve_customer_identity),
) -> CustomerIdentity:
    """Any identity that maps to a Stripe customer (verified or anonymous)."""
    if identity.customer_id is None:
        raise HTTPException(
            status_code=404,
            detail="No billing record found for this visitor. Create an account to subscribe.",
        )
    return identity
