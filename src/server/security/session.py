"""Signed portal sessions (HS256 JSON Web Tokens carried as bearer tokens).

The Vercel-hosted client and the tunnel-exposed server are cross-origin, so a
bearer token in the ``Authorization`` header is used instead of cookies.
"""

from __future__ import annotations

import datetime

import jwt

from settings import PortalSettings


def mint_session_token(
    settings: PortalSettings,
    customer_id: str,
    email: str,
    nn_refresh_token: str | None = None,
) -> str:
    issued_at = datetime.datetime.now(datetime.timezone.utc)
    claims: dict = {
        "sub": customer_id,
        "email": email,
        "kind": "verified",
        "iat": issued_at,
        "exp": issued_at + datetime.timedelta(hours=settings.session_ttl_hours),
    }
    # The Neural Nexus refresh token is carried in the (client-held) session so
    # /auth/logout can revoke it later; the portal keeps no server-side session
    # store. This mirrors how the Neural Nexus dashboard stores the token set
    # client-side.
    if nn_refresh_token:
        claims["nn_refresh_token"] = nn_refresh_token
    return jwt.encode(claims, settings.session_signing_secret, algorithm="HS256")


def decode_session_token(settings: PortalSettings, token: str) -> dict | None:
    """Return the session claims, or None when invalid or expired."""
    try:
        return jwt.decode(token, settings.session_signing_secret, algorithms=["HS256"])
    except jwt.InvalidTokenError:
        return None
