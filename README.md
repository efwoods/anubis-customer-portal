# anubis-customer-portal

Customer portal for Neural Nexus: a React client (Vercel) plus a Python
FastAPI backend-for-frontend (local Docker + Cloudflare Tunnel) that adds
usage-vs-allotment bars, tier switching, a pay-per-use toggle, and refunds on
top of the standard Stripe billing-portal features. Verified users sign in with
their Neural Nexus email and password; anonymous visitors are identified by a
hashed client ip. Full specification: [_FEATURE.md](_FEATURE.md).

## The two stacks

The Stripe live environment and the Stripe test environment are two separate,
simultaneously running stacks — one compose file and one env file each, both env
files gitignored:

| Stack | Compose file | Env file | Project | Host port | Stripe | Reached by |
|---|---|---|---|---|---|---|
| live | `docker-compose.yml` | `.env` | `portal-live` | 8200 | `sk_live_` | Cloudflare tunnel → Vercel client |
| test | `docker-compose.dev.yml` | `.env.dev` | `portal-test` | 8202 | `sk_test_` | `http://localhost:5171` only |

Only the live stack is publicly reachable: the host's `cloudflared` systemd
service routes `checkout-api.neuralnexus.site` to host port 8200, and the Vercel
client is built against that hostname. The client renders a TEST MODE banner
whenever the server it talks to reports `PORTAL_ENV=test`.

Both compose files name their published port and env file **literally**. They
share a directory, so `docker compose` auto-loads `./.env` — the live file — as
the interpolation source for both; literal values are what stop the test stack
from being steered by live values.

## Prerequisites

1. **Stripe billing objects provisioned** — run the Neural Nexus API
   repository's `scripts/provision_stripe_billing.py` against the target Stripe
   environment (test with a `sk_test_` key, live with `--allow-live`). The
   portal discovers tiers, allotments, and overage rates from the resulting
   product/price metadata. The script is idempotent; re-running it changes
   nothing that already exists.
2. **Auth0 machine-to-machine application** authorized for the Management API
   (scopes: `read:users`, `update:users`) — used only to read/write
   `app_metadata.pay_per_use_enabled`.
3. **A public hostname for the live server**, either the host's existing
   Cloudflare tunnel (an ingress rule to `http://localhost:8200`) or a
   `TUNNEL_TOKEN` for the optional bundled `cloudflared` compose service.

## Run the server

```bash
cd src/server
cp .env.example .env.dev                       # test:  PORTAL_ENV=test, sk_test_…
docker compose -f docker-compose.dev.yml up --build -d    # → :8202

cp .env.example .env                           # live:  PORTAL_ENV=live, sk_live_…
docker compose -f docker-compose.yml up --build -d        # → :8200
```

- Health check: `http://localhost:8202/healthz` — reports which environment it is
- Scalar API reference: `http://localhost:8202/reference` (Swagger at `/docs`)

Local development without Docker runs against the **test** environment: the
settings loader names `.env.dev` as its dotenv file precisely so a bare host run
cannot bill real customers.

```bash
cd src/server
uv sync
.venv/bin/uvicorn main:app --reload --port 8202
```

## Run the client locally

```bash
cd src/client
npm install
npm run dev                   # http://localhost:5173, reads .env.development
# or: docker compose up --build   # http://localhost:5171, same env file
```

`.env.development` points at the test server on `:8202`. Never point local
development at `:8200` — that is the live stack and bills real customers.

## Deploy the client to Vercel

Deploys are triggered by a push to `main`. The Vercel project's **root
directory** is `src/client` (framework preset: Vite; `vercel.json` supplies the
SPA rewrite). `src/client/.env.production` is committed on purpose and holds
`VITE_API_BASE_URL=https://checkout-api.neuralnexus.site`, which Vite inlines
during the production build — so no Vercel dashboard environment variable is
required. A change to that file needs a fresh deploy, not a promote of an older
build.

Switching the live server between environments needs **no client redeploy**: the
banner and the Stripe publishable key both come from `GET /config` at runtime.

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
  dashboard and a signup call-to-action. `DEV=TRUE` pins that ip to the Neural
  Nexus API's development value and must stay `FALSE` in the live environment,
  or every anonymous visitor collapses onto one Stripe customer.
- `USAGE_PERIOD_DAYS` must match the Neural Nexus API environment the portal
  reports on — 30 in production, 0 (calendar month) in development — or the
  portal's usage bars disagree with the 402 a user hits in the chat app.
- The Neural Nexus API caches api-key → user lookups for five minutes, so a
  pay-per-use toggle can take up to five minutes to affect request gating there.
- The Neural Nexus API needs no code changes: its Stripe webhook keeps Auth0
  subscription state in sync with everything this portal does in Stripe. It does
  need a correctly registered webhook endpoint and `STRIPE_WEBHOOK_SECRET` in
  each Stripe environment — without them, a downgrade to free cancels the paid
  subscription and no replacement free-tier subscription is ever created.
- The Stripe meter-usage analytics preview API is not enabled on the current
  Stripe account, so the portal's GA event-summaries fallback is the effective
  usage source. The server handles this automatically (the preview endpoint's
  404 is remembered for an hour); no configuration is needed.
