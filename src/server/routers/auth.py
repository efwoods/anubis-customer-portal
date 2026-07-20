"""Email + password authentication against the Neural Nexus API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, EmailStr

import neural_nexus_gateway
from neural_nexus_gateway import NeuralNexusAuthError
from security.identity import CustomerIdentity, require_verified_identity
from security.session import mint_session_token
from settings import get_portal_settings
from stripe_gateway import customers as stripe_customers

router = APIRouter(prefix="/auth", tags=["Authentication"])


class LoginBody(BaseModel):
    email: EmailStr
    password: str


class SignupBody(BaseModel):
    email: EmailStr
    password: str
    name: str | None = None


@router.post("/login")
async def login(body: LoginBody) -> dict:
    """Authenticate against the Neural Nexus API, then issue a portal session.

    The Neural Nexus API verifies the password (Auth0); the portal maps the
    email to its Stripe customer and mints its own bearer session, carrying the
    Neural Nexus refresh token so /auth/logout can revoke it later.
    """
    email = str(body.email)
    try:
        token_set = await neural_nexus_gateway.login(email, body.password)
    except NeuralNexusAuthError as auth_error:
        status_code = 401 if (auth_error.status_code or 401) < 500 else 502
        raise HTTPException(status_code=status_code, detail=str(auth_error)) from auth_error

    customer = await stripe_customers.find_customer_by_email(email)
    if customer is None:
        raise HTTPException(
            status_code=403,
            detail="No billing account is associated with this email.",
        )

    settings = get_portal_settings()
    token = mint_session_token(
        settings,
        customer["id"],
        email,
        nn_refresh_token=token_set.get("refresh_token"),
    )
    return {"token": token, "email": email, "customer_id": customer["id"]}


@router.post("/logout", status_code=204)
async def logout(
    identity: CustomerIdentity = Depends(require_verified_identity),
) -> Response:
    """Revoke the Neural Nexus session (best-effort) and let the client discard
    its bearer token. Always 204 so sign-out never blocks on the Neural Nexus
    API being reachable."""
    if identity.nn_refresh_token:
        await neural_nexus_gateway.logout(identity.nn_refresh_token)
    return Response(status_code=204)


@router.post("/signup")
async def signup(body: SignupBody) -> dict:
    """Create a Neural Nexus account. This does not sign the user in to the
    portal — a verified portal session requires an existing Stripe customer —
    so the client directs the user to verify their email and then sign in."""
    try:
        await neural_nexus_gateway.signup(str(body.email), body.password, body.name)
    except NeuralNexusAuthError as auth_error:
        status_code = auth_error.status_code or 502
        if status_code >= 500:
            status_code = 502
        raise HTTPException(status_code=status_code, detail=str(auth_error)) from auth_error
    return {"ok": True}
