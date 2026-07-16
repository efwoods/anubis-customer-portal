# anubis-customer-portal

Customer portal for Neural Nexus: a React client (Vercel) plus a Python
FastAPI backend-for-frontend (local Docker + Cloudflare Tunnel) that adds
usage-vs-allotment bars, tier switching, a pay-per-use toggle, refunds, and
email one-time-passcode login on top of the standard Stripe billing-portal
features. Full specification: [_FEATURE.md](_FEATURE.md).

## Prerequisites

1. **Stripe billing objects provisioned** — run the f-metering repository's
   `scripts/provision_stripe_billing.py` against the target Stripe environment
   (test and/or live). The portal discovers tiers/allotments/overage rates from
   those products and prices.
2. **Auth0 machine-to-machine application** authorized for the Management API
   (scopes: `read:users`, `update:users`) — used only to read/write
   `app_metadata.pay_per_use_enabled`.
3. **Cloudflare Tunnel token** for the hostname the client will call
   (e.g. `checkout-api.neuralnexus.site` → `portal-server:8080`).
4. **SMTP credentials** for the one-time-passcode email (skippable in
   development: `DEV=TRUE` logs the code instead).

## Run the server (test environment)

```bash
cd src/server
cp .env.example .env          # fill in values; PORTAL_ENV=test, sk_test_... keys
docker compose up --build
```

- Health check: `http://localhost:8080/healthz`
- Scalar API reference: `http://localhost:8080/reference`

Local development without Docker:

```bash
cd src/server
uv sync
.venv/bin/uvicorn main:app --reload --port 8080
```

## Run the server (live environment)

```bash
cd src/server
cp .env.example .env.live     # PORTAL_ENV=live, sk_live_... keys,
                              # and set COMPOSE_ENV_FILE=.env.live
docker compose --env-file .env.live up --build
```

`.env.live` is gitignored. The client shows a TEST MODE banner whenever the
server reports `PORTAL_ENV=test`.

## Run the client locally

```bash
cd src/client
cp .env.example .env          # VITE_API_BASE_URL=http://localhost:8080
npm install
npm run dev                   # http://localhost:5173
# or: docker compose up --build
```

## Deploy the client to Vercel

1. Create a Vercel project with the **root directory** set to `src/client`
   (framework preset: Vite; `vercel.json` supplies the SPA rewrite).
2. Set the environment variable `VITE_API_BASE_URL` to the tunnel hostname
   (e.g. `https://checkout-api.neuralnexus.site`).
3. Point the `checkout.neuralnexus.site` domain at the project.
4. Add the deployed origin to the server's `CLIENT_ORIGIN` (comma-separated
   allowlist) and restart the server.

## Testing

```bash
cd src/server
.venv/bin/python -m pytest            # unit tests (Stripe/Auth0 mocked)

# Manual smoke test against the real Stripe TEST account (refuses live keys):
STRIPE_SECRET_KEY=sk_test_... .venv/bin/python scripts/stripe_test_mode_smoke.py
```

## Notes

- Anonymous visitors are identified by the sha256 hash of their client ip and
  matched to the Stripe customer the Neural Nexus API creates for anonymous
  metering (`metadata.anonymous_hashed_ip`); they get a read-only free-tier
  dashboard and a signup call-to-action.
- The Neural Nexus API caches api-key → user lookups for five minutes, so a
  pay-per-use toggle can take up to five minutes to affect request gating there.
- The Neural Nexus API repository needs no changes: its Stripe webhook keeps
  Auth0 subscription state in sync with everything this portal does in Stripe.
