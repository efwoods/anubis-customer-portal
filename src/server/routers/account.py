"""Portal configuration and the caller's identity."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from security.identity import CustomerIdentity, resolve_customer_identity
from settings import get_portal_settings
from stripe_gateway import customers as stripe_customers

router = APIRouter(tags=["Account"])


@router.get("/config")
async def get_portal_configuration() -> dict:
    """Public client bootstrap: Stripe publishable key, environment, signup URL."""
    settings = get_portal_settings()
    return {
        "publishable_key": settings.stripe_publishable_key,
        "environment": settings.portal_env,
        "nn_api_base_url": settings.nn_api_base_url,
    }


@router.get("/me")
async def get_current_identity(
    identity: CustomerIdentity = Depends(resolve_customer_identity),
) -> dict:
    response: dict = {
        "kind": identity.kind,
        "customer_id": identity.customer_id,
        "email": identity.email,
        "name": None,
    }
    if identity.customer_id:
        customer = await stripe_customers.get_customer(identity.customer_id)
        response["name"] = customer.get("name")
        response["email"] = identity.email or customer.get("email")
    return response
