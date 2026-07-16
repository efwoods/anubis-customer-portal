"""Stripe customer lookup and billing-information management."""

from __future__ import annotations

import asyncio

import stripe


async def find_customer_by_email(email: str) -> dict | None:
    """Return the newest Stripe customer with this exact email, or None.

    ``Customer.list(email=...)`` is an exact-match filter with no search-index
    lag (unlike Customer Search), which matters for login right after signup.
    """

    def _list_customers() -> dict | None:
        customer_list = stripe.Customer.list(email=email, limit=10).to_dict()
        found_customers = [
            customer
            for customer in customer_list.get("data", [])
            if not customer.get("deleted")
        ]
        return found_customers[0] if found_customers else None

    return await asyncio.to_thread(_list_customers)


async def find_customer_id_by_anonymous_hashed_ip(hashed_ip: str) -> str | None:
    """Return the anonymous free-tier customer keyed to one hashed client ip.

    Mirrors the Neural Nexus API's anonymous-billing lookup: Stripe Customer
    Search on ``metadata['anonymous_hashed_ip']``. Fails open to ``None``.
    """

    def _search() -> str | None:
        try:
            search_result = stripe.Customer.search(
                query=f"metadata['anonymous_hashed_ip']:'{hashed_ip}'", limit=1
            ).to_dict()
            found_customers = search_result.get("data", [])
            return found_customers[0]["id"] if found_customers else None
        except stripe.error.StripeError:
            return None

    return await asyncio.to_thread(_search)


async def get_customer(customer_id: str) -> dict:
    return await asyncio.to_thread(
        lambda: stripe.Customer.retrieve(customer_id).to_dict()
    )


async def update_billing_information(
    customer_id: str,
    name: str | None,
    phone: str | None,
    address: dict | None,
) -> dict:
    """Update the customer's billing name, phone, and address (email is the
    login identity and stays read-only)."""
    update_fields: dict = {}
    if name is not None:
        update_fields["name"] = name
    if phone is not None:
        update_fields["phone"] = phone
    if address is not None:
        allowed_address_keys = {"line1", "line2", "city", "state", "postal_code", "country"}
        update_fields["address"] = {
            key: value for key, value in address.items() if key in allowed_address_keys
        }
    return await asyncio.to_thread(
        lambda: stripe.Customer.modify(customer_id, **update_fields).to_dict()
    )
