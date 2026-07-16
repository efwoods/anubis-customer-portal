# Neural Nexus Customer Portal — Specification

A full-page customer portal for Neural Nexus that replicates the Stripe-hosted
billing portal and adds every feature the hosted portal cannot provide:
token-usage visibility against allotments, tier switching with metered prices,
a pay-per-use toggle, and self-service refunds — for **both verified and
anonymous users**, in **test and live** Stripe environments.

- Client (React + Vite + TypeScript): deployed to Vercel at
  `https://checkout.neuralnexus.site` — source in [src/client](src/client).
- Server (Python FastAPI + uvicorn, Scalar API reference at `/reference`):
  runs locally in Docker, exposed to the internet through a Cloudflare Tunnel
  (e.g. `https://checkout-api.neuralnexus.site`) — source in
  [src/server](src/server).

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

The Neural Nexus API has no CORS, so the browser never calls it — this is a
backend-for-frontend. The portal mutates subscriptions **directly in Stripe**;
the existing Neural Nexus webhook propagates those changes into Auth0, so the
two systems never disagree and the Neural Nexus API needed **zero changes**.

## Identity model

| Kind | How identified | What they can do |
|---|---|---|
| **Verified** | Email one-time passcode (6-digit, 10-minute expiry, 5 attempts). The email is matched to a Stripe customer; a signed session token (24 h JWT bearer) is issued. | Everything: view/subscribe/switch/cancel/reactivate, pay-per-use toggle, payment methods, billing information, invoices, refunds. |
| **Anonymous** | sha256 hash of the client ip (`x-forwarded-for`) matched against a Stripe customer carrying `metadata.anonymous_hashed_ip` — the exact scheme the Neural Nexus API uses for anonymous billing. | Read-only: free-tier subscription status and usage bars, plus a signup call-to-action pointing at the Neural Nexus API `/signup`. Anonymous users are always free tier and can never subscribe from the portal. |

Stripe has no API to send its hosted-portal one-time-passcode emails, so the
portal anchors identity in Stripe (customer lookup) and sends its own code by
SMTP; with `DEV=TRUE` the code is logged by the server instead of emailed.

## Feature checklist

Standard hosted-portal features (all implemented):
- ☑ View current subscription, price, and status (`active`/`trialing`/`past_due`…)
- ☑ See when the free trial ends ("Free trial ends <date>")
- ☑ Cancel subscription (at period end) and undo ("Don't cancel subscription")
- ☑ View/add payment method (Stripe Elements SetupIntent), set default, remove
- ☑ View customer name and email
- ☑ Update billing information (name, address, phone; email is the login identity)
- ☑ Invoice history (date, amount, status, hosted view + PDF links)

Previously-missing features (all implemented):
- ☑ Usage vs allotment per meter — messaging-inference tokens, document-upload
  tokens, adapter-training units, adapter-inference tokens — with **visual
  progress bars**, remaining budget, and the overage rate; overage shown as a
  distinct red bar segment
- ☑ Free-trial awareness: trial status, trial end date, and trial usage framing
  (the trial is free usage of the full **pro-tier allotment** of messaging and
  document tokens plus a free pro-tier monthly subscription)
- ☑ Switch tiers (free/pro/premium): upgrades apply immediately with proration;
  downgrades apply at the period boundary so the current period's unused
  allotment continues until then (Stripe subscription schedule); downgrade to
  free ends the paid subscription at the boundary and the Neural Nexus webhook
  drops the account to the $0 free-tier subscription
- ☑ Subscribe (Stripe Checkout) when no live subscription exists — free tier
  always collects a card (the pay-per-use vehicle); pro includes the 30-day
  trial when unused (cardless trial cancels at trial end without a card)
- ☑ Pay-per-use enable/disable button — writes `app_metadata.pay_per_use_enabled`
  through the Auth0 Management API (what the Neural Nexus API gates on);
  enabling requires a payment method on file (402 otherwise); disabled means
  requests stop with HTTP 402 at the allotment
- ☑ Self-service **refund** per paid invoice (full refund of the invoice's
  payment intent)
- ☑ Email one-time-passcode login
- ☑ Anonymous (hashed-ip) status/usage view with signup call-to-action
- ☑ Test and live environments (env-file switch, test-mode banner in the client)

## Portal server API

Scalar reference UI at `/reference`; OpenAPI/Swagger at `/docs`.

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /auth/request_otp {email}` | none | Send sign-in code (always 204 — no account enumeration) |
| `POST /auth/verify_otp {email, code}` | none | Exchange code for a bearer session token |
| `POST /auth/logout` | none | Stateless; client discards its token |
| `GET /config` | none | Publishable key, `test`/`live` environment, Neural Nexus API base URL |
| `GET /me` | any | Identity kind, customer id, name, email |
| `GET /subscription` | any | Tier, status, trial end, cancellation state, period bounds, pay-per-use flag, tier catalog |
| `GET /usage` | any | Per-meter `{monthly_allotment, used_to_date, remaining, overage_price_per_million, overage_price_per_unit_usd, unit}` + period bounds (field names match the Neural Nexus API's `/verify_subscription_status`) |
| `POST /subscription/checkout {tier}` | verified | Stripe Checkout session when no live subscription exists |
| `POST /subscription/change {tier}` | verified | Dispatches: `start_checkout` / `no_change_required` / `reactivate` / `change_tier` (upgrade immediate, downgrade at period end) |
| `POST /subscription/cancel` | verified | `cancel_at_period_end = true` |
| `POST /subscription/reactivate` | verified | Undo pending cancellation / scheduled downgrade |
| `POST /pay_per_use {enabled}` | verified | Toggle overage billing; 402 when enabling without a card |
| `GET /invoices` | verified | Invoice history with `refundable`/`refunded` flags |
| `POST /invoices/{invoice_id}/refund` | verified | Full refund of a paid invoice |
| `GET /payment_methods` | verified | Card list with default flag |
| `POST /payment_methods/setup_intent` | verified | `client_secret` for the Elements add-card form |
| `POST /payment_methods/{id}/default` | verified | Set default card |
| `DELETE /payment_methods/{id}` | verified | Remove card (refused for the default card of an active paid subscription) |
| `GET /billing_info` / `PUT /billing_info` | verified | View / update name, address, phone |
| `GET /healthz` | none | Liveness + environment |

## Catalog, meters, and usage data

Nothing about pricing is hardcoded. The portal discovers the catalog from the
Stripe objects the f-metering `scripts/provision_stripe_billing.py` script
creates (cached ~5 minutes):

- Products are matched by metadata `neural_nexus_tier` (+
  `neural_nexus_product_role` = `base` | `metered`, `neural_nexus_meter`).
- For each metered graduated price: `tiers[0].up_to` **is** the monthly
  allotment (included at $0) and `tiers[1].unit_amount_decimal` is the overage
  rate; `price.recurring.meter` supplies the Billing Meter id.
- The optional `STRIPE_BILLING_CONFIG_JSON` blob (the provisioning script's
  output) is honored as explicit price-id hints when present.

Usage is read from Stripe (meter events are keyed by `stripe_customer_id` and
aggregated by `sum`): primary source is the **meter-usage analytics preview
API** (`GET /v1/billing/analytics/meter_usage`, `Stripe-Version:
2025-07-30.preview`), with the GA meter **event-summaries** API as fallback.
Period bounds come from the subscription's current billing period (calendar
month for customers without one). Because every unit is reported to the meters
(the allotment is just graduated tier 1 at $0), meter usage equals total usage.

Current provisioned catalog (from f-metering `src/anubis/utils/billing/tiers.py`;
the portal re-derives it from Stripe at runtime):

| Tier | Base | Trial | Messaging | Document upload | Adapter inference | Adapter training |
|---|---|---|---|---|---|---|
| free | $0 | — | 200,000 @ $2.00/M | — | — | — |
| pro | $20/mo | 30 days | 5,000,000 @ $1.50/M | 10,000,000 @ $3.00/M | — | — |
| premium | $50/mo | — | 20,000,000 @ $1.25/M | 40,000,000 @ $2.50/M | 10,000,000 @ $4.00/M | 5 units @ $5.00/unit |

## Test and live environments

The server reads one env file per environment (see
[src/server/.env.example](src/server/.env.example)):

- `.env` — Stripe **test** keys, `PORTAL_ENV=test` → the client shows a
  TEST MODE banner.
- `.env.live` — Stripe **live** keys, `PORTAL_ENV=live`.

Switch with `docker compose --env-file .env.live up`. The same
provisioning script must have been run against each Stripe environment.

## Deployment

- **Server**: `src/server/docker-compose.yml` runs `portal-server` (uvicorn on
  8080) plus `cloudflared` (`tunnel run --token $CLOUDFLARE_TUNNEL_TOKEN`)
  routing the public hostname to the local container.
- **Client**: Vercel project rooted at `src/client` (`vercel.json` provides the
  SPA rewrite); set `VITE_API_BASE_URL` to the tunnel hostname. A
  `src/client/docker-compose.yml` runs the Vite dev server for local work.

## Testing

- `src/server/tests/test_portal_flow.py` (pytest, Stripe/Auth0 mocked): the
  full one-time-passcode flow, wrong-code rejection, account-enumeration
  safety, anonymous hashed-ip resolution, `/subscription` and `/usage`
  response shapes (including over-allotment clamping and trial framing), and
  verified-only endpoint gating.
- `src/server/scripts/stripe_test_mode_smoke.py` (manual, requires
  `sk_test_...`): catalog discovery against the provisioned account, customer
  creation + email lookup, pro checkout-session creation, a 72-token meter
  event with usage read-back through the analytics preview API, cleanup.
- Full metering scenarios (allotment exhaustion, 402 with pay-per-use off,
  overage billing per tier, usage reset/rollover across tier changes, trial
  end with/without a card) are exercised against the Neural Nexus API itself —
  see `_METERING_FEATURE_TESTING.md` in the f-metering repository; this portal
  displays the state those flows produce.
