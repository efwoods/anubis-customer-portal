"""Payment-method listing, addition (SetupIntent), default selection, removal."""

from __future__ import annotations

import asyncio

import stripe
from fastapi import HTTPException


def _summarize_payment_method(payment_method: dict, default_payment_method_id: str | None) -> dict:
    card = payment_method.get("card") or {}
    return {
        "payment_method_id": payment_method.get("id"),
        "brand": card.get("brand"),
        "last4": card.get("last4"),
        "exp_month": card.get("exp_month"),
        "exp_year": card.get("exp_year"),
        "is_default": payment_method.get("id") == default_payment_method_id,
    }


def _default_payment_method_id(customer: dict) -> str | None:
    invoice_settings = customer.get("invoice_settings") or {}
    default_payment_method = invoice_settings.get("default_payment_method")
    if isinstance(default_payment_method, dict):
        return default_payment_method.get("id")
    return default_payment_method


async def list_payment_methods(customer_id: str) -> list[dict]:
    def _list() -> list[dict]:
        customer = stripe.Customer.retrieve(customer_id).to_dict()
        default_id = _default_payment_method_id(customer)
        payment_method_list = stripe.Customer.list_payment_methods(
            customer_id, type="card", limit=20
        ).to_dict()
        return [
            _summarize_payment_method(payment_method, default_id)
            for payment_method in payment_method_list.get("data", [])
        ]

    return await asyncio.to_thread(_list)


async def has_payment_method_on_file(customer_id: str) -> bool:
    def _any() -> bool:
        payment_method_list = stripe.Customer.list_payment_methods(
            customer_id, type="card", limit=1
        ).to_dict()
        return bool(payment_method_list.get("data"))

    return await asyncio.to_thread(_any)


async def create_setup_intent(customer_id: str) -> dict:
    setup_intent = await asyncio.to_thread(
        lambda: stripe.SetupIntent.create(
            customer=customer_id,
            usage="off_session",
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
        ).to_dict()
    )
    return {"client_secret": setup_intent["client_secret"]}


async def set_default_payment_method(customer_id: str, payment_method_id: str) -> None:
    def _set_default() -> None:
        payment_method = stripe.PaymentMethod.retrieve(payment_method_id).to_dict()
        if payment_method.get("customer") != customer_id:
            raise HTTPException(status_code=404, detail="Payment method not found.")
        stripe.Customer.modify(
            customer_id,
            invoice_settings={"default_payment_method": payment_method_id},
        )

    await asyncio.to_thread(_set_default)


async def detach_payment_method(
    customer_id: str, payment_method_id: str, has_paid_subscription: bool
) -> None:
    def _detach() -> None:
        payment_method = stripe.PaymentMethod.retrieve(payment_method_id).to_dict()
        if payment_method.get("customer") != customer_id:
            raise HTTPException(status_code=404, detail="Payment method not found.")
        customer = stripe.Customer.retrieve(customer_id).to_dict()
        invoice_settings = customer.get("invoice_settings") or {}
        if (
            has_paid_subscription
            and invoice_settings.get("default_payment_method") == payment_method_id
        ):
            raise HTTPException(
                status_code=409,
                detail="This card is the default for an active paid subscription. "
                "Add another card and make it the default first.",
            )
        stripe.PaymentMethod.detach(payment_method_id)

    await asyncio.to_thread(_detach)
