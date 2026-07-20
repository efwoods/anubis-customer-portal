"""Portal API flow tests with the Stripe and Auth0 gateways mocked."""

from __future__ import annotations

import datetime

import pytest
from fastapi.testclient import TestClient

import auth0_gateway
import main
import neural_nexus_gateway
import routers.auth
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
                "monthly_allotment": 200_000,
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

    messaging = body["meters"]["messaging_tokens"]
    assert messaging["monthly_allotment"] == 5_000_000
    assert messaging["used_to_date"] == 6_000_000
    assert messaging["remaining"] == 0  # clamped, over allotment
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
