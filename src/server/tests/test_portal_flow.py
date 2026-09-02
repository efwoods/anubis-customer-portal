"""Portal API flow tests with the Stripe and Auth0 gateways mocked."""

from __future__ import annotations

import datetime

import pytest
from fastapi.testclient import TestClient

import auth0_gateway
import main
import neural_nexus_gateway
import routers.auth
import routers.invoices
import routers.subscription
import routers.usage
from stripe_gateway import customers as stripe_customers
from stripe_gateway import meter_usage as stripe_meter_usage
from stripe_gateway import subscriptions as stripe_subscriptions

SAMPLE_CATALOG = {
    "free": {
        "tier": "free",
        "display_name": "Neural Nexus Free Tier",
        "monthly_base_fee_usd": 0.0,
        "base_price_id": "price_base_free",
        "trial_period_days": 0,
        "meters": {
            "messaging_tokens": {
                "meter_event_name": "messaging_tokens",
                "meter_id": "mtr_messaging",
                "price_id": "price_free_messaging",
                # Matches the free-tier allotment in the Neural Nexus repo's
                # tiers.py; it was raised from 200,000 and this fixture had not
                # followed.
                "monthly_allotment": 2_000_000,
                "overage_price_per_million": 2.0,
                "overage_price_per_unit_usd": None,
                "unit": "tokens",
                "display_name": "Free — Messaging Tokens",
            }
        },
    },
    "pro": {
        "tier": "pro",
        "display_name": "Neural Nexus Pro Tier",
        "monthly_base_fee_usd": 20.0,
        "base_price_id": "price_base_pro",
        "trial_period_days": 30,
        "meters": {
            "messaging_tokens": {
                "meter_event_name": "messaging_tokens",
                "meter_id": "mtr_messaging",
                "price_id": "price_pro_messaging",
                "monthly_allotment": 5_000_000,
                "overage_price_per_million": 1.5,
                "overage_price_per_unit_usd": None,
                "unit": "tokens",
                "display_name": "Pro — Messaging Tokens",
            },
            "document_upload_tokens": {
                "meter_event_name": "document_upload_tokens",
                "meter_id": "mtr_documents",
                "price_id": "price_pro_documents",
                "monthly_allotment": 10_000_000,
                "overage_price_per_million": 3.0,
                "overage_price_per_unit_usd": None,
                "unit": "tokens",
                "display_name": "Pro — Document Upload Tokens",
            },
        },
    },
}

_NOW_EPOCH = int(datetime.datetime.now(datetime.timezone.utc).timestamp())

SAMPLE_PRO_TRIAL_SUBSCRIPTION = {
    "id": "sub_test_pro",
    "status": "trialing",
    "customer": "cus_test",
    "metadata": {"neural_nexus_tier": "pro"},
    "trial_end": _NOW_EPOCH + 20 * 86_400,
    "cancel_at_period_end": False,
    "cancel_at": None,
    "schedule": None,
    "current_period_start": _NOW_EPOCH - 10 * 86_400,
    "current_period_end": _NOW_EPOCH + 20 * 86_400,
    "items": {"data": [{"id": "si_base", "price": {"id": "price_base_pro"}}]},
}


@pytest.fixture()
def client(monkeypatch):
    async def fake_get_tier_catalog(force_refresh: bool = False) -> dict:
        return SAMPLE_CATALOG

    monkeypatch.setattr(routers.subscription, "get_tier_catalog", fake_get_tier_catalog)
    monkeypatch.setattr(routers.usage, "get_tier_catalog", fake_get_tier_catalog)
    # Every module that binds get_tier_catalog into its own namespace needs its
    # own patch — `from stripe_gateway.catalog import get_tier_catalog` copies
    # the reference, so patching the catalog module would not reach any of them.
    # Missing routers.invoices sent the refund tests to the real Stripe API.
    monkeypatch.setattr(routers.invoices, "get_tier_catalog", fake_get_tier_catalog)
    # The lifespan warms the catalog at startup; keep tests off the network.
    monkeypatch.setattr(main, "get_tier_catalog", fake_get_tier_catalog)

    async def fake_read_pay_per_use_enabled(email: str) -> bool | None:
        return None

    monkeypatch.setattr(
        auth0_gateway, "read_pay_per_use_enabled", fake_read_pay_per_use_enabled
    )

    with TestClient(main.app) as test_client:
        yield test_client


def _sign_in(client: TestClient, monkeypatch) -> str:
    """Authenticate with email + password (Neural Nexus mocked) and return the token."""

    async def fake_find_customer_by_email(email: str) -> dict | None:
        return {"id": "cus_test", "email": email}

    monkeypatch.setattr(
        stripe_customers, "find_customer_by_email", fake_find_customer_by_email
    )

    async def fake_login(email: str, password: str) -> dict:
        return {"refresh_token": "rt_test", "access_token": "at_test"}

    monkeypatch.setattr(neural_nexus_gateway, "login", fake_login)

    login_response = client.post(
        "/auth/login",
        json={"email": "customer@example.com", "password": "correct horse"},
    )
    assert login_response.status_code == 200
    body = login_response.json()
    assert body["customer_id"] == "cus_test"
    return body["token"]


def test_password_login_and_me(client, monkeypatch):
    token = _sign_in(client, monkeypatch)

    async def fake_get_customer(customer_id: str) -> dict:
        return {"id": customer_id, "name": "Test User", "email": "customer@example.com"}

    monkeypatch.setattr(stripe_customers, "get_customer", fake_get_customer)

    me_response = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert me_response.status_code == 200
    assert me_response.json() == {
        "kind": "verified",
        "customer_id": "cus_test",
        "email": "customer@example.com",
        "name": "Test User",
    }


def test_single_sign_on_issues_the_same_session_as_login(client, monkeypatch):
    """A code handed over by the Neural Nexus application signs the customer in.

    The session it yields must be the one /auth/login yields — same shape, same
    bearer token, accepted by /me the same way — because everything downstream of
    sign-in was written against that session and knows nothing about how it was
    obtained.
    """

    async def fake_find_customer_by_email(email: str) -> dict | None:
        return {"id": "cus_test", "email": email}

    monkeypatch.setattr(
        stripe_customers, "find_customer_by_email", fake_find_customer_by_email
    )

    async def fake_redeem(shared_secret: str, exchange_code: str) -> dict:
        assert shared_secret == "test-exchange-secret"
        assert exchange_code == "exchange-code-from-the-application"
        return {"user_id": "auth0|test", "email": "customer@example.com"}

    monkeypatch.setattr(
        neural_nexus_gateway, "redeem_billing_portal_exchange_code", fake_redeem
    )

    response = client.post(
        "/auth/single_sign_on",
        json={"exchange_code": "exchange-code-from-the-application"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == "customer@example.com"
    assert body["customer_id"] == "cus_test"

    async def fake_get_customer(customer_id: str) -> dict:
        return {"id": customer_id, "name": "Test User", "email": "customer@example.com"}

    monkeypatch.setattr(stripe_customers, "get_customer", fake_get_customer)

    me_response = client.get(
        "/me", headers={"Authorization": f"Bearer {body['token']}"}
    )
    assert me_response.status_code == 200
    assert me_response.json()["kind"] == "verified"


def test_single_sign_on_session_holds_no_neural_nexus_credential(client, monkeypatch):
    """The Neural Nexus refresh token never crosses into this origin, so a
    session created this way has nothing for /auth/logout to revoke."""
    import jwt as pyjwt

    from settings import get_portal_settings

    async def fake_find_customer_by_email(email: str) -> dict | None:
        return {"id": "cus_test", "email": email}

    monkeypatch.setattr(
        stripe_customers, "find_customer_by_email", fake_find_customer_by_email
    )

    async def fake_redeem(shared_secret: str, exchange_code: str) -> dict:
        return {"user_id": "auth0|test", "email": "customer@example.com"}

    monkeypatch.setattr(
        neural_nexus_gateway, "redeem_billing_portal_exchange_code", fake_redeem
    )

    response = client.post(
        "/auth/single_sign_on", json={"exchange_code": "any-code"}
    )
    assert response.status_code == 200
    claims = pyjwt.decode(
        response.json()["token"],
        get_portal_settings().session_signing_secret,
        algorithms=["HS256"],
    )
    assert "nn_refresh_token" not in claims


def test_single_sign_on_with_a_refused_code_is_rejected(client, monkeypatch):
    """An expired, forged, or already-spent code yields no session."""

    async def fake_redeem(shared_secret: str, exchange_code: str) -> dict:
        raise neural_nexus_gateway.NeuralNexusAuthError(
            "This sign-in link is no longer valid.", status_code=400
        )

    monkeypatch.setattr(
        neural_nexus_gateway, "redeem_billing_portal_exchange_code", fake_redeem
    )

    response = client.post(
        "/auth/single_sign_on", json={"exchange_code": "expired-code"}
    )
    assert response.status_code == 400


def test_single_sign_on_refuses_when_the_shared_secret_is_unset(client, monkeypatch):
    """Unconfigured is a supported state: refuse, and let the embedding page
    fall back to this portal's own sign-in card."""
    from settings import get_portal_settings

    monkeypatch.setattr(get_portal_settings(), "nn_exchange_shared_secret", "")

    response = client.post(
        "/auth/single_sign_on", json={"exchange_code": "any-code"}
    )
    assert response.status_code == 503


def test_wrong_password_rejected(client, monkeypatch):
    async def fake_login(email: str, password: str) -> dict:
        raise neural_nexus_gateway.NeuralNexusAuthError(
            "Invalid email or password.", status_code=401
        )

    monkeypatch.setattr(neural_nexus_gateway, "login", fake_login)

    response = client.post(
        "/auth/login",
        json={"email": "customer@example.com", "password": "wrong"},
    )
    assert response.status_code == 401


def test_login_without_billing_account_rejected(client, monkeypatch):
    async def fake_login(email: str, password: str) -> dict:
        return {"refresh_token": "rt_test"}

    monkeypatch.setattr(neural_nexus_gateway, "login", fake_login)

    async def fake_find_customer_by_email(email: str) -> dict | None:
        return None

    monkeypatch.setattr(
        stripe_customers, "find_customer_by_email", fake_find_customer_by_email
    )

    response = client.post(
        "/auth/login",
        json={"email": "nobody@example.com", "password": "correct horse"},
    )
    assert response.status_code == 403


def test_logout_revokes_neural_nexus_session(client, monkeypatch):
    token = _sign_in(client, monkeypatch)

    captured: dict[str, str] = {}

    async def fake_logout(refresh_token: str) -> None:
        captured["refresh_token"] = refresh_token

    monkeypatch.setattr(neural_nexus_gateway, "logout", fake_logout)

    logout_response = client.post(
        "/auth/logout", headers={"Authorization": f"Bearer {token}"}
    )
    assert logout_response.status_code == 204
    assert captured["refresh_token"] == "rt_test"


def test_logout_requires_verified_identity(client, monkeypatch):
    async def fake_find_anonymous(hashed_ip: str) -> str | None:
        return None

    monkeypatch.setattr(
        stripe_customers, "find_customer_id_by_anonymous_hashed_ip", fake_find_anonymous
    )

    response = client.post("/auth/logout")
    assert response.status_code == 401


def test_signup_proxies_to_neural_nexus(client, monkeypatch):
    captured: dict[str, str | None] = {}

    async def fake_signup(email: str, password: str, name: str | None = None) -> dict:
        captured["email"] = email
        captured["name"] = name
        return {"ok": True}

    monkeypatch.setattr(neural_nexus_gateway, "signup", fake_signup)

    response = client.post(
        "/auth/signup",
        json={"email": "new@example.com", "password": "correct horse", "name": "Ada"},
    )
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert captured["email"] == "new@example.com"
    assert captured["name"] == "Ada"


def test_anonymous_me_resolves_hashed_ip_customer(client, monkeypatch):
    async def fake_find_anonymous(hashed_ip: str) -> str | None:
        return "cus_anonymous"

    monkeypatch.setattr(
        stripe_customers, "find_customer_id_by_anonymous_hashed_ip", fake_find_anonymous
    )

    async def fake_get_customer(customer_id: str) -> dict:
        return {"id": customer_id, "name": None, "email": None}

    monkeypatch.setattr(stripe_customers, "get_customer", fake_get_customer)

    me_response = client.get("/me")
    assert me_response.status_code == 200
    body = me_response.json()
    assert body["kind"] == "anonymous"
    assert body["customer_id"] == "cus_anonymous"


def test_subscription_status_shape(client, monkeypatch):
    token = _sign_in(client, monkeypatch)

    async def fake_get_current_subscription(customer_id: str) -> dict | None:
        return SAMPLE_PRO_TRIAL_SUBSCRIPTION

    monkeypatch.setattr(
        stripe_subscriptions, "get_current_subscription", fake_get_current_subscription
    )

    async def fake_has_used_trial(customer_id: str) -> bool:
        return False

    monkeypatch.setattr(stripe_subscriptions, "has_used_trial", fake_has_used_trial)

    subscription_response = client.get(
        "/subscription", headers={"Authorization": f"Bearer {token}"}
    )
    assert subscription_response.status_code == 200
    body = subscription_response.json()
    assert body["tier"] == "pro"
    assert body["status"] == "trialing"
    assert body["trial_end"] is not None
    assert body["monthly_base_fee_usd"] == 20.0
    assert body["cancel_at_period_end"] is False
    # Trialing does not infer pay-per-use (matches the Neural Nexus API).
    assert body["pay_per_use_enabled"] is False
    # Trial visibility: the customer is on the pro trial, has not used it up,
    # and the countdown reflects the ~20 days left in the sample subscription.
    assert body["trial_tier"] == "pro"
    assert body["trialing"] is True
    assert body["trial_already_used"] is False
    assert body["trial_days_remaining"] == 20
    catalog_tiers = {entry["tier"] for entry in body["tier_catalog"]}
    assert catalog_tiers == {"free", "pro"}


def test_usage_report_shape(client, monkeypatch):
    token = _sign_in(client, monkeypatch)

    async def fake_get_current_subscription(customer_id: str) -> dict | None:
        return SAMPLE_PRO_TRIAL_SUBSCRIPTION

    monkeypatch.setattr(
        stripe_subscriptions, "get_current_subscription", fake_get_current_subscription
    )

    async def fake_fetch_usage(
        customer_id: str, meter_ids: list[str], start_time: int, end_time: int
    ) -> dict[str, int]:
        return {"mtr_messaging": 6_000_000, "mtr_documents": 42}

    monkeypatch.setattr(
        stripe_meter_usage, "fetch_usage_by_meter_id", fake_fetch_usage
    )

    usage_response = client.get("/usage", headers={"Authorization": f"Bearer {token}"})
    assert usage_response.status_code == 200
    body = usage_response.json()
    assert body["tier"] == "pro"
    assert body["trialing"] is True
    # /usage carries the pay-per-use flag so the client renders the meters and
    # the toggle from one consistent response.
    assert body["pay_per_use_enabled"] is False

    messaging = body["meters"]["messaging_tokens"]
    assert messaging["monthly_allotment"] == 5_000_000
    assert messaging["used_to_date"] == 6_000_000
    assert messaging["remaining"] == 0  # clamped, over allotment
    assert messaging["over_allotment"] == 1_000_000  # surfaced for pay-per-use
    assert messaging["overage_price_per_million"] == 1.5

    documents = body["meters"]["document_upload_tokens"]
    assert documents["used_to_date"] == 42
    assert documents["remaining"] == 10_000_000 - 42


def test_unprovisioned_catalog_returns_503_on_tier_change(client, monkeypatch):
    """An unprovisioned Stripe environment (empty catalog) must yield an
    actionable 503 on tier mutations, not an unhandled 500."""
    token = _sign_in(client, monkeypatch)

    async def fake_empty_tier_catalog(force_refresh: bool = False) -> dict:
        return {}

    monkeypatch.setattr(
        routers.subscription, "get_tier_catalog", fake_empty_tier_catalog
    )

    async def fake_get_current_subscription(customer_id: str) -> dict | None:
        return SAMPLE_PRO_TRIAL_SUBSCRIPTION

    monkeypatch.setattr(
        stripe_subscriptions, "get_current_subscription", fake_get_current_subscription
    )

    change_response = client.post(
        "/subscription/change",
        json={"tier": "premium"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert change_response.status_code == 503
    assert "provision" in change_response.json()["detail"].lower()


def test_verified_only_endpoints_reject_anonymous(client, monkeypatch):
    async def fake_find_anonymous(hashed_ip: str) -> str | None:
        return "cus_anonymous"

    monkeypatch.setattr(
        stripe_customers, "find_customer_id_by_anonymous_hashed_ip", fake_find_anonymous
    )

    for method, path in [
        ("GET", "/invoices"),
        ("GET", "/payment_methods"),
        ("GET", "/billing_info"),
        ("POST", "/subscription/cancel"),
    ]:
        response = client.request(method, path)
        assert response.status_code == 401, path

    pay_per_use_response = client.post("/pay_per_use", json={"enabled": True})
    assert pay_per_use_response.status_code == 401


def _mock_refund_success(monkeypatch) -> None:
    from stripe_gateway import invoices as stripe_invoices

    async def fake_refund_invoice(customer_id: str, invoice_id: str) -> dict:
        return {
            "refund_id": "re_test",
            "status": "succeeded",
            "amount": 2000,
            "currency": "usd",
            "invoice_id": invoice_id,
        }

    monkeypatch.setattr(stripe_invoices, "refund_invoice", fake_refund_invoice)


def test_refund_of_paid_subscription_cancels_immediately(client, monkeypatch):
    """A paid (non-trial) refund ends the subscription at once, dropping to free."""
    token = _sign_in(client, monkeypatch)
    _mock_refund_success(monkeypatch)

    paid_subscription = {
        **SAMPLE_PRO_TRIAL_SUBSCRIPTION,
        "status": "active",
        "metadata": {"neural_nexus_tier": "pro"},
    }

    async def fake_get_current_subscription(customer_id: str) -> dict | None:
        return paid_subscription

    monkeypatch.setattr(
        stripe_subscriptions, "get_current_subscription", fake_get_current_subscription
    )

    canceled: dict[str, str] = {}

    async def fake_release_pending_schedule(subscription: dict) -> None:
        return None

    async def fake_cancel_immediately(subscription_id: str) -> dict:
        canceled["subscription_id"] = subscription_id
        return {"id": subscription_id, "status": "canceled"}

    monkeypatch.setattr(
        stripe_subscriptions, "release_pending_schedule", fake_release_pending_schedule
    )
    monkeypatch.setattr(
        stripe_subscriptions, "cancel_subscription_immediately", fake_cancel_immediately
    )

    response = client.post(
        "/invoices/in_test/refund", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["refund_id"] == "re_test"
    assert body["subscription_action"] == "canceled_immediately"
    assert canceled["subscription_id"] == "sub_test_pro"


def test_refund_during_pro_trial_retains_trial_to_period_end(client, monkeypatch):
    """A refund while trialing on the trial tier keeps the trial to the boundary."""
    token = _sign_in(client, monkeypatch)
    _mock_refund_success(monkeypatch)

    async def fake_get_current_subscription(customer_id: str) -> dict | None:
        return SAMPLE_PRO_TRIAL_SUBSCRIPTION  # status "trialing", tier pro

    monkeypatch.setattr(
        stripe_subscriptions, "get_current_subscription", fake_get_current_subscription
    )

    scheduled: dict[str, bool] = {}

    async def fake_release_pending_schedule(subscription: dict) -> None:
        return None

    async def fake_set_cancel_at_period_end(subscription_id: str, cancel: bool) -> dict:
        scheduled["cancel"] = cancel
        return {"id": subscription_id, "cancel_at_period_end": cancel}

    def _fail_immediate(*args, **kwargs):  # pragma: no cover - must not be called
        raise AssertionError("a trial refund must not cancel immediately")

    monkeypatch.setattr(
        stripe_subscriptions, "release_pending_schedule", fake_release_pending_schedule
    )
    monkeypatch.setattr(
        stripe_subscriptions, "set_cancel_at_period_end", fake_set_cancel_at_period_end
    )
    monkeypatch.setattr(
        stripe_subscriptions, "cancel_subscription_immediately", _fail_immediate
    )

    response = client.post(
        "/invoices/in_test/refund", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["subscription_action"] == "ends_at_period_end"
    assert scheduled["cancel"] is True


def test_anonymous_and_account_usage_are_separate_ledgers(client, monkeypatch):
    """One visitor, one source address, two completely separate usage ledgers.

    Anonymous usage and account usage are separate allotments reported
    separately. The guarantee is that the two identities never read the same
    Stripe customer: the anonymous ledger belongs to the customer carrying
    ``metadata.anonymous_hashed_ip``, and the account ledger belongs to the
    customer carrying the Auth0 linkage. This test drives both reads from the
    same client so a future refactor cannot collapse them onto one record.
    """
    metered_customer_ids: list[str] = []

    async def fake_fetch_usage(
        customer_id: str, meter_ids: list[str], start_time: int, end_time: int
    ) -> dict[str, int]:
        metered_customer_ids.append(customer_id)
        return {"mtr_messaging": 25_000, "mtr_documents": 0}

    monkeypatch.setattr(
        stripe_meter_usage, "fetch_usage_by_meter_id", fake_fetch_usage
    )

    # ── Anonymous half: resolved by hashed ip, no subscription, free tier ──
    async def fake_find_anonymous(hashed_ip: str) -> str | None:
        return "cus_anonymous"

    monkeypatch.setattr(
        stripe_customers, "find_customer_id_by_anonymous_hashed_ip", fake_find_anonymous
    )

    async def fake_no_subscription(customer_id: str) -> dict | None:
        return None

    monkeypatch.setattr(
        stripe_subscriptions, "get_current_subscription", fake_no_subscription
    )

    anonymous_usage = client.get("/usage")
    assert anonymous_usage.status_code == 200
    anonymous_body = anonymous_usage.json()
    # An anonymous visitor is a free-tier user: the same catalog allotment a
    # verified free-tier user gets, on its own ledger.
    assert anonymous_body["tier"] == "free"
    assert anonymous_body["pay_per_use_enabled"] is False
    assert (
        anonymous_body["meters"]["messaging_tokens"]["monthly_allotment"]
        == SAMPLE_CATALOG["free"]["meters"]["messaging_tokens"]["monthly_allotment"]
    )
    assert anonymous_body["meters"]["messaging_tokens"]["used_to_date"] == 25_000
    # Free tier carries no document-upload meter, so none is reported.
    assert "document_upload_tokens" not in anonymous_body["meters"]

    # ── Account half: same client, now signed in ──────────────────────────
    token = _sign_in(client, monkeypatch)

    async def fake_get_current_subscription(customer_id: str) -> dict | None:
        return SAMPLE_PRO_TRIAL_SUBSCRIPTION

    monkeypatch.setattr(
        stripe_subscriptions, "get_current_subscription", fake_get_current_subscription
    )

    account_usage = client.get("/usage", headers={"Authorization": f"Bearer {token}"})
    assert account_usage.status_code == 200
    account_body = account_usage.json()
    assert account_body["tier"] == "pro"
    assert (
        account_body["meters"]["messaging_tokens"]["monthly_allotment"]
        == SAMPLE_CATALOG["pro"]["meters"]["messaging_tokens"]["monthly_allotment"]
    )

    # The two reads hit two different Stripe customers — never the same record,
    # which is what keeps the allotments and the reported numbers separate.
    assert metered_customer_ids == ["cus_anonymous", "cus_test"]
    assert len(set(metered_customer_ids)) == 2
