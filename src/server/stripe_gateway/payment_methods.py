"""Payment-method listing, addition (SetupIntent), default selection, removal.

Also home to ``reconcile_payment_methods``, which repairs the two ways Stripe's
defaults produce a wrong-looking wallet in this product:

* Subscription-mode Checkout saves a card with ``allow_redisplay="limited"``,
  and cards attached through a SetupIntent are ``"unspecified"``. Checkout only
  PREFILLS cards marked ``"always"``, so a customer with a card on file was
  shown an empty card form on their next tier change.
* Because that form was empty, the customer retyped the same card and Stripe
  attached a SECOND PaymentMethod for it — Stripe does not deduplicate cards on
  its own — which then showed up twice in the portal's payment-method list.

Reconciling promotes every saved card to ``allow_redisplay="always"`` (the
customer demonstrably consented by leaving it on file for recurring billing)
and detaches fingerprint duplicates, so both symptoms clear and stay cleared.
"""

from __future__ import annotations

import asyncio
import logging

import stripe
from fastapi import HTTPException

logger = logging.getLogger(__name__)


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


def _keep_preference(payment_method: dict, default_payment_method_id: str | None) -> tuple:
    """Sort key choosing which of several identical cards to keep.

    Lowest sorts first and is kept. The customer's default card wins outright —
    detaching it would silently move an active subscription onto a different
    payment method. Otherwise the OLDEST card is kept, because it is the one any
    existing subscription or invoice already references; the newer copies are
    the accidental retypes.
    """
    is_default = payment_method.get("id") == default_payment_method_id
    return (0 if is_default else 1, payment_method.get("created") or 0)


def _repoint_subscriptions_off_payment_method(
    customer_id: str, detached_payment_method_id: str, kept_payment_method_id: str
) -> None:
    """Move any subscription explicitly billing the detached card onto the kept one.

    A subscription can pin its own ``default_payment_method`` independently of
    the customer's. Detaching that card would drop the subscription back to the
    customer default — usually the same card, but not guaranteed — so the
    pointer is rewritten first and the duplicate is removed only afterwards.
    """
    subscription_list = stripe.Subscription.list(
        customer=customer_id, status="all", limit=100
    ).to_dict()
    for subscription in subscription_list.get("data", []):
        subscription_payment_method = subscription.get("default_payment_method")
        if isinstance(subscription_payment_method, dict):
            subscription_payment_method = subscription_payment_method.get("id")
        if subscription_payment_method != detached_payment_method_id:
            continue
        stripe.Subscription.modify(
            subscription["id"], default_payment_method=kept_payment_method_id
        )


async def reconcile_payment_methods(customer_id: str) -> dict:
    """Make every saved card reusable in Checkout and remove duplicate cards.

    Idempotent and safe to call on any portal event that can create a card
    (finishing Checkout, saving one through the SetupIntent form) or that is
    about to show saved cards (starting a new Checkout). Returns counts of what
    changed so the caller can report or log the repair.

    Best-effort per card: one card that refuses to update or detach is logged
    and skipped rather than failing the whole reconcile, because this runs
    alongside flows (a completed checkout) that have already succeeded.
    """

    def _reconcile() -> dict:
        customer = stripe.Customer.retrieve(customer_id).to_dict()
        default_payment_method_id = _default_payment_method_id(customer)
        payment_method_list = stripe.Customer.list_payment_methods(
            customer_id, type="card", limit=100
        ).to_dict()
        payment_methods = payment_method_list.get("data", [])

        promoted_count = 0
        for payment_method in payment_methods:
            if payment_method.get("allow_redisplay") == "always":
                continue
            try:
                stripe.PaymentMethod.modify(payment_method["id"], allow_redisplay="always")
                promoted_count += 1
            except Exception as promote_error:  # noqa: BLE001 - best-effort repair
                logger.warning(
                    "Could not mark payment method %s reusable: %s",
                    payment_method.get("id"),
                    promote_error,
                )

        # Group by the card fingerprint — Stripe's stable identifier for "the
        # same card", independent of which PaymentMethod object wraps it.
        payment_methods_by_fingerprint: dict[str, list[dict]] = {}
        for payment_method in payment_methods:
            fingerprint = (payment_method.get("card") or {}).get("fingerprint")
            if not fingerprint:
                continue
            payment_methods_by_fingerprint.setdefault(fingerprint, []).append(
                payment_method
            )

        detached_count = 0
        for duplicate_group in payment_methods_by_fingerprint.values():
            if len(duplicate_group) < 2:
                continue
            ordered_group = sorted(
                duplicate_group,
                key=lambda candidate: _keep_preference(
                    candidate, default_payment_method_id
                ),
            )
            kept_payment_method_id = ordered_group[0]["id"]
            for duplicate in ordered_group[1:]:
                try:
                    _repoint_subscriptions_off_payment_method(
                        customer_id, duplicate["id"], kept_payment_method_id
                    )
                    stripe.PaymentMethod.detach(duplicate["id"])
                    detached_count += 1
                except Exception as detach_error:  # noqa: BLE001 - best-effort repair
                    logger.warning(
                        "Could not detach duplicate payment method %s: %s",
                        duplicate.get("id"),
                        detach_error,
                    )
            if default_payment_method_id is None:
                # The customer had no default at all; the surviving copy becomes
                # it so a later detach cannot leave the account card-less.
                try:
                    stripe.Customer.modify(
                        customer_id,
                        invoice_settings={
                            "default_payment_method": kept_payment_method_id
                        },
                    )
                    default_payment_method_id = kept_payment_method_id
                except Exception as default_error:  # noqa: BLE001 - best-effort
                    logger.warning(
                        "Could not set a default payment method for %s: %s",
                        customer_id,
                        default_error,
                    )

        return {
            "marked_reusable": promoted_count,
            "duplicates_removed": detached_count,
        }

    return await asyncio.to_thread(_reconcile)


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
