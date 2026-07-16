"""Signed portal sessions (HS256 JSON Web Tokens carried as bearer tokens).

The Vercel-hosted client and the tunnel-exposed server are cross-origin, so a
bearer token in the ``Authorization`` header is used instead of cookies.
"""

from __future__ import annotations

import datetime

import jwt

from settings import PortalSettings


def mint_session_token(settings: PortalSettings, customer_id: str, email: str) -> str:
    issued_at = datetime.datetime.now(datetime.timezone.utc)
    return jwt.encode(
        {
            "sub": customer_id,
            "email": email,
            "kind": "verified",
            "iat": issued_at,
            "exp": issued_at + datetime.timedelta(hours=settings.session_ttl_hours),
        },
        settings.session_signing_secret,
        algorithm="HS256",
    )


def decode_session_token(settings: PortalSettings, token: str) -> dict | None:
    """Return the session claims, or None when invalid or expired."""
    try:
        return jwt.decode(token, settings.session_signing_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
