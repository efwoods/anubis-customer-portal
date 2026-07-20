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

import logging

import httpx

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
