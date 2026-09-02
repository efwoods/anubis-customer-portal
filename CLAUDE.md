# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project is

Customer portal for Neural Nexus: a React client (deployed to Vercel) plus a
Python FastAPI backend-for-frontend (run locally in Docker, exposed via
Cloudflare Tunnel) that replicates the Stripe-hosted billing portal and adds
what it cannot provide — token-usage-vs-allotment bars, tier switching with
metered prices, a pay-per-use toggle, and self-service refunds — for both
verified and anonymous users, in Stripe test and live environments. Full spec:
[_FEATURE.md](_FEATURE.md).

This portal is a satellite of the main Neural Nexus API (Anubis / f-metering
repo, developed separately): it mutates subscriptions **directly in Stripe**
and the existing Neural Nexus webhook (`/stripe/webhook`, unchanged) propagates
those changes into Auth0, so the two systems never disagree. The Neural Nexus
API needs zero *code* changes to support this portal — but that webhook is load
bearing, and it is configuration, not code. Each Stripe environment needs an
endpoint registered at `https://api.neuralnexus.site/stripe/webhook` and its
signing secret in the API's `STRIPE_WEBHOOK_SECRET` (the endpoint returns 503
without one). Where it is missing, a downgrade to free cancels the paid
subscription and the replacement $0 free-tier subscription is never created.

## Commands

```bash
# Server — Docker, TEST environment (reads .env.dev, project portal-test, :8202)
cd src/server && cp .env.example .env.dev   # PORTAL_ENV=test, sk_test_...
docker compose -f docker-compose.dev.yml up --build -d

# Server — Docker, LIVE environment (reads .env, project portal-live, :8200)
cd src/server && cp .env.example .env       # PORTAL_ENV=live, sk_live_...
docker compose -f docker-compose.yml up --build -d
# Health check: http://localhost:8200/healthz  — reports which environment it is
# Scalar API reference: http://localhost:8202/reference (Swagger at /docs)

# Server — local dev without Docker. Runs against the TEST environment: the
# settings loader names .env.dev as its dotenv file so a bare host run cannot
# bill real customers.
cd src/server
uv sync
.venv/bin/uvicorn main:app --reload --port 8202

# Server tests (Stripe/Auth0 mocked)
cd src/server
.venv/bin/python -m pytest
.venv/bin/python -m pytest tests/test_portal_flow.py::test_subscription_status_shape  # single test

# Manual smoke test against the real Stripe TEST account (refuses live keys)
STRIPE_SECRET_KEY=sk_test_... .venv/bin/python scripts/stripe_test_mode_smoke.py

# Client — local dev (reads .env.development → the test server on :8202)
cd src/client
npm install
npm run dev            # http://localhost:5171
npm run build          # tsc -b && vite build
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
  minted after email + password authentication proxied to the Neural Nexus API
  (`routers/auth.py` + `neural_nexus_gateway.py`). Carries the Stripe customer
  id, email, and the Neural Nexus refresh token used for sign-out. Routes
  requiring this use `require_verified_identity`.
- **anonymous** — no valid bearer token. The client ip (`x-forwarded-for`) is
  sha256-hashed with the *exact same scheme the Neural Nexus API uses* and
  matched against a Stripe customer carrying `metadata.anonymous_hashed_ip`
  (`stripe_gateway/customers.py::find_customer_id_by_anonymous_hashed_ip`).
  Anonymous users are always free tier, read-only. In `DEV=TRUE` the client ip
  is pinned to `172.18.0.1` to match the Neural Nexus API's own dev fallback,
  so a local portal against the same Stripe test account resolves the same
  anonymous customer.

Sessions are stateless: the portal stores nothing server-side, so a restart
leaves outstanding session tokens valid until they expire
(`SESSION_TTL_HOURS`). Each environment signs with its own
`SESSION_SIGNING_SECRET`, so a token minted by the test stack cannot validate
against live.

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
or `auth0_gateway`/`neural_nexus_gateway` module that owns the actual
Stripe/Auth0/Neural Nexus calls:

| Router | Gateway modules |
|---|---|
| `routers/auth.py` | `neural_nexus_gateway.py`, `security/session.py`, `stripe_gateway/customers.py` |
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

### Environment files and the two stacks

The Stripe live and test environments are two simultaneously running stacks,
one compose file and one env file each (both env files gitignored):

| Stack | Compose file | Env file | Project | Host port | Stripe | Reached by |
|---|---|---|---|---|---|---|
| live | `docker-compose.yml` | `.env` | `portal-live` | 8200 | `sk_live_` | Cloudflare tunnel → Vercel client |
| test | `docker-compose.dev.yml` | `.env.dev` | `portal-test` | 8202 | `sk_test_` | `http://localhost:5171` only |

This mirrors the Neural Nexus API repo's convention, where `.env` is live
production and `.env.dev` is the test environment. Only the live stack is
publicly exposed — the host `cloudflared` systemd service routes
`checkout-api.neuralnexus.site` to host port 8200.

Both compose files name their published port and env file **literally** and set
an explicit top-level `name:`. They share a directory, so `docker compose`
auto-loads `./.env` — the live file — as the interpolation source for *both*;
literal values are what keep the test stack from being steered by live values,
and distinct project names stop each `up` from treating the other's container
as an orphan. `.dockerignore` excludes every env file, so no credential is baked
into an image; values reach the container through the compose `env_file:`
directive only.

Every variable is declared in `src/server/.env.example` (no values) and as a
typed field in `src/server/settings.py` (`PortalSettings`, a
`pydantic-settings` `BaseSettings`) — add new variables in both places. That
settings class names `.env.dev` as its dotenv file so running the server
directly on the host defaults to the Stripe test environment.

Two variables must agree with the Neural Nexus API environment being reported
on: `USAGE_PERIOD_DAYS` (30 in production, 0 in development) and `DEV`
(`FALSE` in live, or every anonymous visitor collapses onto one Stripe
customer). The client has its own `src/client/.env.development` (test server)
and `src/client/.env.production` (the tunnel hostname, committed on purpose).

### Testing

`src/server/tests/test_portal_flow.py` mocks the Stripe/Auth0 gateway
functions directly (via `monkeypatch.setattr` on the imported module, not
HTTP-level mocking) and drives the FastAPI `TestClient` through the full
email + password login flow, anonymous hashed-ip resolution, `/subscription`
and `/usage` response shapes, and verified-only endpoint gating.
`tests/conftest.py` sets required env vars via `os.environ.setdefault`
*before* `main` is imported by any test module.
