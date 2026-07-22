"""Auth0 Management API access for the pay-per-use flag.

The Neural Nexus API's gating layer reads ``app_metadata.pay_per_use_enabled``
from Auth0 — Stripe has no equivalent switch — so toggling pay-per-use from
the portal means writing that flag through the Auth0 Management API. When the
flag has never been set, the Neural Nexus API infers pay-per-use only for an
``active`` (not trialing) subscription; ``infer_pay_per_use_enabled`` mirrors
that so both systems answer consistently.

Note: the Neural Nexus API caches api-key → user lookups for five minutes, so
a toggle can take up to five minutes to affect request gating there.
"""

from __future__ import annotations

import asyncio
import logging
import time
import urllib.parse

import httpx
from fastapi import HTTPException

from settings import PortalSettings, get_portal_settings

logger = logging.getLogger(__name__)

_management_token_cache: tuple[float, str] | None = None
_management_token_lock = asyncio.Lock()


def auth0_is_configured(settings: PortalSettings | None = None) -> bool:
    settings = settings or get_portal_settings()
    return bool(settings.auth0_domain and settings.auth0_client_id and settings.auth0_client_secret)


async def _get_management_token() -> str:
    global _management_token_cache
    settings = get_portal_settings()
    async with _management_token_lock:
        if _management_token_cache and time.monotonic() < _management_token_cache[0]:
            return _management_token_cache[1]
        async with httpx.AsyncClient(timeout=15.0) as http_client:
            response = await http_client.post(
                f"https://{settings.auth0_domain}/oauth/token",
                json={
                    "grant_type": "client_credentials",
                    "client_id": settings.auth0_client_id,
                    "client_secret": settings.auth0_client_secret,
                    "audience": f"https://{settings.auth0_domain}/api/v2/",
                },
            )
        response.raise_for_status()
        token_document = response.json()
        expires_in_seconds = int(token_document.get("expires_in", 3600))
        management_token = token_document["access_token"]
        _management_token_cache = (
            time.monotonic() + max(60, expires_in_seconds - 120),
            management_token,
        )
        return management_token


async def _find_user_by_email(email: str) -> dict | None:
    management_token = await _get_management_token()
    settings = get_portal_settings()
    encoded_email = urllib.parse.quote(email.lower())
    async with httpx.AsyncClient(timeout=15.0) as http_client:
        response = await http_client.get(
            f"https://{settings.auth0_domain}/api/v2/users-by-email?email={encoded_email}",
            headers={"Authorization": f"Bearer {management_token}"},
        )
    response.raise_for_status()
    user_list = response.json()
    if not user_list:
        return None
    if len(user_list) > 1:
        # More than one Auth0 identity carries this email (e.g. a database and a
        # social connection). We patch the first, but the Neural Nexus API's
        # api-key lookup may resolve a different identity — surface it so a
        # "pay-per-use won't change" report can be traced to the right record.
        logger.warning(
            "Auth0 returned %d users for email %s; using user_id=%s. If the "
            "pay-per-use flag does not take effect, the api-key may resolve a "
            "different identity.",
            len(user_list),
            email,
            user_list[0].get("user_id"),
        )
    return user_list[0]


def infer_pay_per_use_enabled(subscription_status: str | None) -> bool:
    """The Neural Nexus API's inference when the flag was never set explicitly."""
    return subscription_status == "active"


async def read_pay_per_use_enabled(email: str) -> bool | None:
    """Explicit flag from Auth0 app_metadata, or None when unset/unavailable."""
    if not auth0_is_configured():
        return None
    try:
        auth0_user = await _find_user_by_email(email)
    except Exception as lookup_error:  # noqa: BLE001 - degrade to inference
        logger.warning("Auth0 user lookup failed for pay-per-use read: %s", lookup_error)
        return None
    if auth0_user is None:
        return None
    flag_value = (auth0_user.get("app_metadata") or {}).get("pay_per_use_enabled")
    if flag_value is None:
        return None
    return bool(flag_value)


async def write_pay_per_use_enabled(email: str, enabled: bool) -> bool:
    """Persist the pay-per-use flag and return the value Auth0 actually stored.

    Returning the stored value (rather than echoing the request) lets the
    caller confirm the write took effect and surfaces a silent no-op instead of
    reporting success the Neural Nexus API will not see.
    """
    if not auth0_is_configured():
        raise HTTPException(
            status_code=503,
            detail="Pay-per-use cannot be changed right now: the portal server is "
            "not configured with Auth0 Management API credentials.",
        )
    auth0_user = await _find_user_by_email(email)
    if auth0_user is None:
        raise HTTPException(
            status_code=404,
            detail="No Neural Nexus account exists for this email. Sign up first.",
        )
    management_token = await _get_management_token()
    settings = get_portal_settings()
    async with httpx.AsyncClient(timeout=15.0) as http_client:
        response = await http_client.patch(
            f"https://{settings.auth0_domain}/api/v2/users/"
            f"{urllib.parse.quote(auth0_user['user_id'])}",
            headers={"Authorization": f"Bearer {management_token}"},
            json={"app_metadata": {"pay_per_use_enabled": enabled}},
        )
    response.raise_for_status()
    stored_user = response.json()
    stored_flag = (stored_user.get("app_metadata") or {}).get("pay_per_use_enabled")
    return bool(stored_flag)
