"""Stripe customer lookup and billing-information management."""

from __future__ import annotations

import asyncio
import logging

import stripe

logger = logging.getLogger(__name__)


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


async def mirror_pay_per_use_flag_to_stripe(customer_id: str, enabled: bool) -> None:
    """Publish the pay-per-use switch into Stripe customer metadata.

    Writing the flag to Auth0 alone is not enough for it to take effect
    promptly: the Neural Nexus API caches api-key → user lookups for five
    minutes, and only its own writes evict that cache. Subscription changes feel
    instant precisely because Stripe emits a webhook the Neural Nexus API
    handles — so pay-per-use travels the same road. Setting this metadata emits
    ``customer.updated``, whose handler writes the flag into Auth0 on the Neural
    Nexus side and evicts the cache there, making the toggle effective on the
    very next request.

    Best-effort: Auth0 remains the store of record, so a Stripe failure only
    costs promptness (the flag still lands within the cache TTL) and must not
    fail the user's toggle.
    """

    def _write_metadata() -> None:
        stripe.Customer.modify(
            customer_id,
            metadata={"pay_per_use_enabled": "true" if enabled else "false"},
        )

    try:
        await asyncio.to_thread(_write_metadata)
    except Exception as mirror_error:  # noqa: BLE001 - promptness only
        logger.warning(
            "Could not mirror the pay-per-use flag into Stripe metadata for %s; "
            "the Neural Nexus API will pick it up within its cache TTL instead: %s",
            customer_id,
            mirror_error,
        )


async def get_customer(customer_id: str) -> dict:
    return await asyncio.to_thread(
        lambda: stripe.Customer.retrieve(customer_id).to_dict()
    )


_ADDRESS_KEYS = ("line1", "line2", "city", "state", "postal_code", "country")


def _default_payment_method_id(customer: dict) -> str | None:
    invoice_settings = customer.get("invoice_settings") or {}
    default_payment_method = invoice_settings.get("default_payment_method")
    if isinstance(default_payment_method, dict):
        return default_payment_method.get("id")
    return default_payment_method


def _billing_card_id(customer: dict) -> str | None:
    """The payment method whose billing_details the form should sync with:
    the default card, or the sole card on file when none is marked default."""
    default_id = _default_payment_method_id(customer)
    if default_id:
        return default_id
    card_list = stripe.Customer.list_payment_methods(
        customer["id"], type="card", limit=1
    ).to_dict()
    card_data = card_list.get("data", [])
    return card_data[0]["id"] if card_data else None


def _address_has_value(address: dict | None) -> bool:
    return bool(address and any(address.get(key) for key in _ADDRESS_KEYS))


async def get_billing_information(customer_id: str) -> dict:
    """Customer billing name/phone/address, falling back to the billing card's
    ``billing_details`` for any field the customer record leaves empty — so the
    form reflects what the payment method carries and the two never look out of
    sync on screen."""

    def _read() -> dict:
        customer = stripe.Customer.retrieve(customer_id).to_dict()
        name = customer.get("name")
        phone = customer.get("phone")
        address = customer.get("address")
        if not name or not phone or not _address_has_value(address):
            billing_card_id = _billing_card_id(customer)
            if billing_card_id:
                billing_details = (
                    stripe.PaymentMethod.retrieve(billing_card_id).to_dict().get(
                        "billing_details"
                    )
                    or {}
                )
                name = name or billing_details.get("name")
                phone = phone or billing_details.get("phone")
                if not _address_has_value(address):
                    card_address = billing_details.get("address") or {}
                    if _address_has_value(card_address):
                        address = {
                            key: card_address.get(key) for key in _ADDRESS_KEYS
                        }
        return {
            "name": name,
            "email": customer.get("email"),
            "phone": phone,
            "address": address,
        }

    return await asyncio.to_thread(_read)


async def update_billing_information(
    customer_id: str,
    name: str | None,
    phone: str | None,
    address: dict | None,
) -> dict:
    """Update the customer's billing name, phone, and address (email is the
    login identity and stays read-only), then mirror the same values onto the
    billing card's ``billing_details`` so the card and customer stay in sync."""
    update_fields: dict = {}
    if name is not None:
        update_fields["name"] = name
    if phone is not None:
        update_fields["phone"] = phone
    if address is not None:
        update_fields["address"] = {
            key: value for key, value in address.items() if key in _ADDRESS_KEYS
        }

    def _update() -> dict:
        updated_customer = stripe.Customer.modify(customer_id, **update_fields).to_dict()
        billing_card_id = _billing_card_id(updated_customer)
        if billing_card_id:
            card_billing_details: dict = {}
            if name is not None:
                card_billing_details["name"] = name
            if phone is not None:
                card_billing_details["phone"] = phone
            if "address" in update_fields:
                card_billing_details["address"] = update_fields["address"]
            if card_billing_details:
                try:
                    stripe.PaymentMethod.modify(
                        billing_card_id, billing_details=card_billing_details
                    )
                except stripe.error.StripeError:
                    # Best-effort mirror; the customer record is the source of
                    # truth and the read path falls back to it regardless.
                    pass
        return updated_customer

    return await asyncio.to_thread(_update)
