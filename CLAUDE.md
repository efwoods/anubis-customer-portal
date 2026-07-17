# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Customer portal for Neural Nexus: a React client (deployed to Vercel) plus a
Python FastAPI backend-for-frontend (run locally in Docker, exposed via
Cloudflare Tunnel) that replicates the Stripe-hosted billing portal and adds
what it cannot provide — token-usage-vs-allotment bars, tier switching with
metered prices, a pay-per-use toggle, self-service refunds, and email
one-time-passcode login — for both verified and anonymous users, in Stripe
test and live environments. Full spec: [_FEATURE.md](_FEATURE.md).

This portal is a satellite of the main Neural Nexus API (Anubis / f-metering
repo, developed separately): it mutates subscriptions **directly in Stripe**
and the existing Neural Nexus webhook (`/stripe/webhook`, unchanged) propagates
those changes into Auth0, so the two systems never disagree. The Neural Nexus
API needs zero changes to support this portal.

## Commands

```bash
# Server — local dev without Docker
cd src/server
uv sync
.venv/bin/uvicorn main:app --reload --port 8080
# Health check: http://localhost:8080/healthz
# Scalar API reference: http://localhost:8080/reference (Swagger at /docs)

# Server — Docker (test environment, reads .env)
cd src/server && cp .env.example .env   # fill in values; PORTAL_ENV=test, sk_test_...
docker compose up --build

# Server — Docker (live environment, reads .env.live, gitignored)
docker compose --env-file .env.live up --build

# Server tests (Stripe/Auth0 mocked)
cd src/server
.venv/bin/python -m pytest
.venv/bin/python -m pytest tests/test_portal_flow.py::test_subscription_status_shape  # single test

# Manual smoke test against the real Stripe TEST account (refuses live keys)
STRIPE_SECRET_KEY=sk_test_... .venv/bin/python scripts/stripe_test_mode_smoke.py

# Client — local dev
cd src/client
cp .env.example .env   # VITE_API_BASE_URL=http://localhost:8080
npm install
npm run dev            # http://localhost:5173
npm run build           # tsc -b && vite build
```

There is no lint/format tooling configured in this repo (no ruff/mypy/Makefile
— that tooling lives in the separate Neural Nexus API repo).

## Architecture

```
Browser (Vercel client)
   │  HTTPS + CORS, bearer session token
   ▼
Portal server (FastAPI, local Docker, Cloudflare Tunnel)
   ├──► Stripe API        subscriptions, checkout, meter usage, invoices,
   │                      refunds, payment methods, billing information
   └──► Auth0 Management  app_metadata.pay_per_use_enabled (read + write)

Neural Nexus API (separate repo, unchanged)
   └──► /stripe/webhook keeps Auth0 app_metadata.subscription_status in sync
        with every subscription change the portal makes in Stripe.
```

The Neural Nexus API has no CORS, so the browser never calls it directly —
this portal server is the backend-for-frontend. The portal never writes
subscription status itself; it only mutates Stripe and lets the existing
webhook propagate state into Auth0.

### Identity model (`src/server/security/identity.py`)

Two identity kinds, resolved per-request by `resolve_customer_identity` (a
FastAPI dependency used by nearly every route):

- **verified** — a bearer session token (HS256 JWT, `security/session.py`)
  minted after email one-time-passcode verification (`routers/auth.py` +
  `security/one_time_passcode.py`). Carries the Stripe customer id and email.
  Routes requiring this use `require_verified_identity`.
- **anonymous** — no valid bearer token. The client ip (`x-forwarded-for`) is
  sha256-hashed with the *exact same scheme the Neural Nexus API uses* and
  matched against a Stripe customer carrying `metadata.anonymous_hashed_ip`
  (`stripe_gateway/customers.py::find_customer_id_by_anonymous_hashed_ip`).
  Anonymous users are always free tier, read-only. In `DEV=TRUE` the client ip
  is pinned to `172.18.0.1` to match the Neural Nexus API's own dev fallback,
  so a local portal against the same Stripe test account resolves the same
  anonymous customer.

One-time passcodes are process-local (in-memory dict on `app.state`, sha256
hashed, TTL + bounded attempts) — no external store, since the portal server
is a single container; a restart just invalidates outstanding codes.

### Catalog discovery (`src/server/stripe_gateway/catalog.py`)

Nothing about pricing/tiers is hardcoded. The catalog (`get_tier_catalog`,
cached 5 minutes) is built by scanning Stripe products/prices for metadata
stamped by the separate f-metering repo's `scripts/provision_stripe_billing.py`:
`neural_nexus_tier` (free/pro/premium), `neural_nexus_product_role`
(`base` flat fee vs `metered`), `neural_nexus_meter` (meter event name). For
metered graduated prices, `tiers[0].up_to` **is** the monthly allotment
(included at $0) and `tiers[1].unit_amount_decimal` is the overage rate.
`STRIPE_BILLING_CONFIG_JSON` is an optional explicit-price-id hint (the
provisioning script's own output); discovery is the default/fallback path.
Changing this logic changes how every tier/price/allotment in the system is
derived — treat it as the single source of truth over any hardcoded tier list.

### Subscription mutation semantics (`src/server/routers/subscription.py`,
`src/server/stripe_gateway/subscriptions.py`)

`POST /subscription/change` dispatches based on direction:
- No live subscription → Stripe Checkout session (`start_checkout`).
- Same tier + pending cancellation/schedule → release it (`reactivate`).
- Upgrade → immediate item swap with `proration_behavior="create_prorations"`.
- Downgrade to a paid tier → a Stripe `SubscriptionSchedule` phase takes effect
  at the period boundary (current allotment continues until then) —
  `schedule_downgrade_at_period_end`.
- Downgrade to free / cancel → `cancel_at_period_end=true`; the *Neural Nexus
  webhook* (not this portal) creates the $0 free-tier subscription afterward.

Any pending schedule/cancellation must be released (`release_pending_schedule`)
before a new tier change can apply — this ordering matters and is handled at
the top of `change_subscription_tier`.

The free tier always collects a payment method at checkout (`payment_method_collection="always"`)
because it is the pay-per-use billing vehicle; a pro trial can start cardless
(`if_required`) but cancels at trial end if no card was ever added.

### Usage/meter reads (`src/server/stripe_gateway/meter_usage.py`)

Primary source is the Stripe **meter-usage analytics preview** endpoint
(`GET /v1/billing/analytics/meter_usage`, `Stripe-Version: 2025-07-30.preview`)
called via raw `httpx` (the Stripe Python SDK does not wrap preview
endpoints). Falls back to the GA `event_summaries` endpoint per-meter if the
account isn't enrolled in the preview (404 memoized for an hour to avoid
repeated dead calls). Both endpoints require timestamps aligned to minute
boundaries (`_align_to_minute`). `GET /usage` response field names
deliberately match the Neural Nexus API's `/verify_subscription_status` so a
client can consume either source interchangeably. Note: the analytics preview
API is not enabled on the current Stripe account (verified 2026-07-16), so the
event-summaries fallback is the effective usage source in practice.

### Stripe API version pin (`src/server/stripe_gateway/client.py`)

`stripe.api_version` is pinned to `"2024-12-18.acacia"` globally so object
shapes the code relies on (`invoice.payment_intent`,
`subscription.current_period_end`) stay stable regardless of the account's
default API version. The meter-usage analytics preview call is the one
exception — it sends its own `Stripe-Version: 2025-07-30.preview` header
explicitly per-request.

### Pay-per-use flag (`src/server/auth0_gateway.py`)

Stripe has no on/off switch for overage billing, so
`app_metadata.pay_per_use_enabled` lives in Auth0 and is read/written through
the Auth0 Management API (client-credentials token, cached until near
expiry). When the flag was never explicitly set, both this portal
(`infer_pay_per_use_enabled`) and the Neural Nexus API infer it from
subscription status (`active` → enabled, `trialing`/other → disabled) so the
two systems agree without a stored value. Enabling requires a payment method
on file (402 otherwise); the Neural Nexus API caches api-key→user lookups for
five minutes, so a toggle can take up to five minutes to take effect there.

### Routers → gateway module mapping

`main.py` wires six routers, each thin and delegating to a `stripe_gateway/*`
or `auth0_gateway`/`email_delivery` module that owns the actual Stripe/Auth0
calls:

| Router | Gateway modules |
|---|---|
| `routers/auth.py` | `security/one_time_passcode.py`, `security/session.py`, `email_delivery.py`, `stripe_gateway/customers.py` |
| `routers/account.py` | `stripe_gateway/customers.py` |
| `routers/subscription.py` | `stripe_gateway/subscriptions.py`, `stripe_gateway/customers.py`, `stripe_gateway/payment_methods.py`, `stripe_gateway/catalog.py`, `auth0_gateway.py` |
| `routers/usage.py` | `stripe_gateway/meter_usage.py`, `stripe_gateway/subscriptions.py`, `stripe_gateway/catalog.py` |
| `routers/invoices.py` | `stripe_gateway/invoices.py` |
| `routers/billing.py` | `stripe_gateway/customers.py`, `stripe_gateway/payment_methods.py`, `stripe_gateway/subscriptions.py` |

All blocking Stripe SDK calls are wrapped in `asyncio.to_thread` inside the
gateway modules — the Stripe Python SDK is synchronous.

### Client (`src/client/`)

Plain React + Vite + TypeScript, no state-management or routing library.
`src/api.ts` is the only fetch wrapper (`apiRequest`): attaches the bearer
token from `localStorage`, clears it on a 401, throws `ApiError` with the
FastAPI `detail` message. `App.tsx` holds top-level identity/config state and
composes one component per portal section (`components/*Section.tsx`); each
section fetches its own data keyed off `refreshCounter`, bumped by
`onChanged` callbacks after a mutation so the whole dashboard re-syncs.
Stripe Elements (`@stripe/react-stripe-js`) is used only for the add-card
SetupIntent form in `PaymentMethodsSection`.

### Environment files

Two parallel env files switch Stripe environments — `src/server/.env`
(test keys, `PORTAL_ENV=test`) and `src/server/.env.live` (live keys,
gitignored), selected via `docker compose --env-file .env.live up`. Every
variable is declared in `src/server/.env.example` (no values) and as a typed
field in `src/server/settings.py` (`PortalSettings`, a `pydantic-settings`
`BaseSettings`) — add new variables in both places. The client has its own
`src/client/.env.example` (`VITE_API_BASE_URL`).

### Testing

`src/server/tests/test_portal_flow.py` mocks the Stripe/Auth0 gateway
functions directly (via `monkeypatch.setattr` on the imported module, not
HTTP-level mocking) and drives the FastAPI `TestClient` through the full
one-time-passcode flow, anonymous hashed-ip resolution, `/subscription` and
`/usage` response shapes, and verified-only endpoint gating.
`tests/conftest.py` sets required env vars via `os.environ.setdefault`
*before* `main` is imported by any test module.
