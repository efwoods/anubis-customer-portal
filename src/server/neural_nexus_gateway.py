"""Neural Nexus API access for email + password authentication.

The portal authenticates verified users against the Neural Nexus API's Auth0-
backed endpoints instead of running its own credential store:

* ``/login`` (email + password) returns the Auth0 token set; the portal keeps
  only the ``refresh_token`` (in its own session) so it can later revoke the
  session through ``/logout``.
* ``/logout`` revokes the refresh token at Auth0. It is called best-effort — a
  failure here must never block the user's sign-out.
* ``/signup`` creates the Neural Nexus account. It does not sign the user in to
  the portal (the portal session requires an existing Stripe customer).

All calls target ``settings.nn_api_base_url``. The portal stores no Neural Nexus
API key: login and signup need none, and logout is authenticated by the refresh
token the portal already holds.
"""

from __future__ import annotations

import json
import logging
import time

import httpx

import billing_portal_exchange_signature
from settings import get_portal_settings

logger = logging.getLogger(__name__)

_REQUEST_TIMEOUT_SECONDS = 20.0


class NeuralNexusAuthError(Exception):
    """A Neural Nexus authentication call failed (bad credentials, duplicate
    account, or the API being unreachable). Carries an HTTP status when the
    Neural Nexus API returned one so the router can map it to a response."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        super().__init__(message)
        self.status_code = status_code


def _base_url() -> str:
    return get_portal_settings().nn_api_base_url.rstrip("/")


async def login(email: str, password: str) -> dict:
    """Authenticate against the Neural Nexus API and return the token set.

    Raises ``NeuralNexusAuthError`` on invalid credentials or an unreachable
    Neural Nexus API.
    """
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as http_client:
            response = await http_client.post(
                f"{_base_url()}/login",
                json={"email": email, "password": password},
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as transport_error:
        logger.warning("Neural Nexus /login request failed: %s", transport_error)
        raise NeuralNexusAuthError(
            "The sign-in service is unavailable. Try again in a moment."
        ) from transport_error
    if response.status_code >= 400:
        raise NeuralNexusAuthError(
            "Invalid email or password.", status_code=response.status_code
        )
    return response.json()


async def logout(refresh_token: str) -> None:
    """Revoke the refresh token at Auth0 via the Neural Nexus API. Best-effort:
    any failure is logged and swallowed so sign-out is never blocked."""
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as http_client:
            response = await http_client.post(
                f"{_base_url()}/logout",
                json={"refresh_token": refresh_token},
                headers={"Accept": "application/json"},
            )
        if response.status_code >= 400:
            logger.warning(
                "Neural Nexus /logout returned HTTP %s; the local session is "
                "cleared regardless.",
                response.status_code,
            )
    except httpx.HTTPError as transport_error:
        logger.warning("Neural Nexus /logout request failed: %s", transport_error)


async def signup(email: str, password: str, name: str | None = None) -> dict:
    """Create a Neural Nexus account. Raises ``NeuralNexusAuthError`` (with the
    Neural Nexus status, e.g. 409 for a duplicate account) on failure."""
    payload: dict[str, str] = {"email": email, "password": password}
    if name:
        payload["name"] = name
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as http_client:
            response = await http_client.post(
                f"{_base_url()}/signup",
                json=payload,
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as transport_error:
        logger.warning("Neural Nexus /signup request failed: %s", transport_error)
        raise NeuralNexusAuthError(
            "The sign-up service is unavailable. Try again in a moment."
        ) from transport_error
    if response.status_code >= 400:
        detail = "Could not create the account."
        try:
            body = response.json()
            if isinstance(body, dict) and isinstance(body.get("detail"), str):
                detail = body["detail"]
        except ValueError:
            pass
        raise NeuralNexusAuthError(detail, status_code=response.status_code)
    return response.json()


async def redeem_billing_portal_exchange_code(
    shared_secret: str, exchange_code: str
) -> dict:
    """Spend a billing portal exchange code and return the account it names.

    The code was minted by the Neural Nexus API for a user who is already signed
    in to the Neural Nexus application, and handed to this portal through the
    embedding page's frame. Spending it is how this portal learns which account
    it is being asked to serve; the response carries ``user_id`` and ``email``
    and no Neural Nexus credential of any kind, so the portal mints its own
    session from the email exactly as its password sign-in already does.

    The call is machine-to-machine and authenticated by an HMAC-SHA256 over
    ``'<timestamp>.<body>'`` keyed by the secret shared with the Neural Nexus
    API. The signature covers the exact bytes sent, so the body is serialized
    once here and handed to httpx as bytes rather than as ``json=``, which would
    be free to re-serialize it differently.

    Raises ``NeuralNexusAuthError`` when the code is expired, forged, already
    spent, when single sign-on is unconfigured on either side, or when the
    Neural Nexus API is unreachable.
    """
    body = json.dumps({"exchange_code": exchange_code}).encode("utf-8")
    timestamp = str(int(time.time()))
    signature = billing_portal_exchange_signature.build_exchange_redemption_signature(
        shared_secret, timestamp, body
    )
    try:
        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT_SECONDS) as http_client:
            response = await http_client.post(
                f"{_base_url()}/redeem_billing_portal_exchange_code",
                content=body,
                headers={
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    billing_portal_exchange_signature.TIMESTAMP_HEADER_NAME: timestamp,
                    billing_portal_exchange_signature.SIGNATURE_HEADER_NAME: signature,
                },
            )
    except httpx.HTTPError as transport_error:
        logger.warning(
            "Neural Nexus /redeem_billing_portal_exchange_code request failed: %s",
            transport_error,
        )
        raise NeuralNexusAuthError(
            "The sign-in service is unavailable. Try again in a moment."
        ) from transport_error
    if response.status_code >= 400:
        detail = "This sign-in link is no longer valid."
        try:
            body_document = response.json()
            if isinstance(body_document, dict) and isinstance(
                body_document.get("detail"), str
            ):
                detail = body_document["detail"]
        except ValueError:
            pass
        raise NeuralNexusAuthError(detail, status_code=response.status_code)
    return response.json()
