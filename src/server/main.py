"""Neural Nexus customer portal server.

A backend-for-frontend for the Vercel-hosted React portal client: the browser
talks only to this server; this server talks to Stripe (subscriptions, usage
meters, invoices, payment methods, refunds) and to the Auth0 Management API
(the pay-per-use flag the Neural Nexus API gates on). Run it locally in Docker
and expose it to the internet with the Cloudflare Tunnel service in
``docker-compose.yml``.

API reference UI: Scalar at ``/reference`` (Swagger remains at ``/docs``).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scalar_fastapi import get_scalar_api_reference

from routers import account, auth, billing, invoices, subscription, usage
from security.one_time_passcode import OneTimePasscodeStore
from settings import get_portal_settings
from stripe_gateway.catalog import get_tier_catalog
from stripe_gateway.client import configure_stripe

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _warm_tier_catalog() -> None:
    """Discover the tier catalog once at startup so the first request does not
    pay the discovery cost, and surface a misprovisioned Stripe environment
    immediately in the server log instead of on the first tier change."""
    try:
        catalog = await get_tier_catalog()
    except Exception as catalog_error:  # noqa: BLE001 - startup must not crash on Stripe being down
        logger.warning(
            "Tier-catalog discovery failed at startup (%s); the catalog will be "
            "retried on the first request.",
            catalog_error,
        )
        return
    if not catalog:
        logger.warning(
            "Tier-catalog discovery found NO provisioned tiers — this Stripe "
            "environment is not provisioned (run the f-metering "
            "provision_stripe_billing.py script). Subscription checkout and tier "
            "changes will return HTTP 503 until then."
        )
        return
    logger.info("Tier catalog discovered at startup: %s", sorted(catalog.keys()))


@asynccontextmanager
async def lifespan(application: FastAPI):
    settings = get_portal_settings()
    configure_stripe()
    application.state.one_time_passcode_store = OneTimePasscodeStore(
        ttl_seconds=settings.one_time_passcode_ttl_seconds,
        max_attempts=settings.one_time_passcode_max_attempts,
    )
    await _warm_tier_catalog()
    yield


app = FastAPI(
    title="Neural Nexus Customer Portal API",
    description=(
        "Backend-for-frontend for the Neural Nexus customer portal. "
        "Verified users sign in with an email one-time passcode; anonymous "
        "visitors are identified by a hashed client ip and see their free-tier "
        "status and usage read-only."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_portal_settings().client_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

app.include_router(auth.router)
app.include_router(account.router)
app.include_router(subscription.router)
app.include_router(usage.router)
app.include_router(invoices.router)
app.include_router(billing.router)


@app.get("/healthz", tags=["System"])
async def health_check() -> dict:
    return {"ok": True, "environment": get_portal_settings().portal_env}


@app.get("/reference", include_in_schema=False)
async def scalar_api_reference():
    return get_scalar_api_reference(openapi_url=app.openapi_url, title=app.title)
