"""Payment methods and billing information (verified users only)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from security.identity import CustomerIdentity, require_verified_identity
from stripe_gateway import customers as stripe_customers
from stripe_gateway import payment_methods as stripe_payment_methods
from stripe_gateway import subscriptions as stripe_subscriptions

router = APIRouter(tags=["Billing"])


class BillingAddressBody(BaseModel):
    line1: str | None = None
    line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None


class BillingInformationBody(BaseModel):
    name: str | None = None
    phone: str | None = None
    address: BillingAddressBody | None = None


@router.get("/payment_methods")
async def list_payment_methods(
    identity: CustomerIdentity = Depends(require_verified_identity),
) -> dict:
    payment_method_list = await stripe_payment_methods.list_payment_methods(
        identity.customer_id
    )
    return {"payment_methods": payment_method_list}


@router.post("/payment_methods/setup_intent")
async def create_payment_method_setup_intent(
    identity: CustomerIdentity = Depends(require_verified_identity),
) -> dict:
    return await stripe_payment_methods.create_setup_intent(identity.customer_id)


@router.post("/payment_methods/{payment_method_id}/default", status_code=204)
async def set_default_payment_method(
    payment_method_id: str,
    identity: CustomerIdentity = Depends(require_verified_identity),
) -> Response:
    await stripe_payment_methods.set_default_payment_method(
        identity.customer_id, payment_method_id
    )
    return Response(status_code=204)


@router.delete("/payment_methods/{payment_method_id}", status_code=204)
async def remove_payment_method(
    payment_method_id: str,
    identity: CustomerIdentity = Depends(require_verified_identity),
) -> Response:
    subscription = await stripe_subscriptions.get_current_subscription(
        identity.customer_id
    )
    has_paid_subscription = bool(
        subscription and subscription.get("status") in ("active", "trialing", "past_due")
    )
    await stripe_payment_methods.detach_payment_method(
        identity.customer_id, payment_method_id, has_paid_subscription
    )
    return Response(status_code=204)


@router.get("/billing_info")
async def get_billing_information(
    identity: CustomerIdentity = Depends(require_verified_identity),
) -> dict:
    customer = await stripe_customers.get_customer(identity.customer_id)
    return {
        "name": customer.get("name"),
        "email": customer.get("email"),
        "phone": customer.get("phone"),
        "address": customer.get("address"),
    }


@router.put("/billing_info")
async def update_billing_information(
    body: BillingInformationBody,
    identity: CustomerIdentity = Depends(require_verified_identity),
) -> dict:
    updated_customer = await stripe_customers.update_billing_information(
        identity.customer_id,
        name=body.name,
        phone=body.phone,
        address=body.address.model_dump(exclude_none=True) if body.address else None,
    )
    return {
        "name": updated_customer.get("name"),
        "email": updated_customer.get("email"),
        "phone": updated_customer.get("phone"),
        "address": updated_customer.get("address"),
    }
