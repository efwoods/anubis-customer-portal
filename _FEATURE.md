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

Neural Nexus API (separate repo)
   ├──► /stripe/webhook keeps Auth0 app_metadata.subscription_status in sync
   │    with every subscription change the portal makes in Stripe.
   ├──► /login, /signup                     password auth, proxied by the portal
   ├──► /create_billing_portal_exchange_code  single sign-on, minted for the app
   ├──◄ /redeem_billing_portal_exchange_code  single sign-on, spent by the portal
   └──► POST /internal/usage-event          real-time usage push into the portal
```

The Neural Nexus API has no CORS, so the browser never calls it — this is a
backend-for-frontend. The portal mutates subscriptions **directly in Stripe**;
the existing Neural Nexus webhook propagates those changes into Auth0, so the
two systems never disagree.

The billing half needed **zero changes** to that API. Two later features did
add endpoints to it: the real-time usage push and single sign-on from the
Neural Nexus application. Both are off unless a shared secret is configured on
each side, and both fail closed — usage falls back to the Stripe read, and the
embedded portal falls back to its own sign-in card.

## Identity model

| Kind | How identified | What they can do |
|---|---|---|
| **Verified** | Email + password, proxied to the Neural Nexus API's `/login`. The email is then matched to a Stripe customer and a signed session token (24 h JWT bearer) is issued. A customer already signed in to the Neural Nexus application gets the same session without a second sign-in, through the single sign-on exchange below. | Everything: view/subscribe/switch/cancel/reactivate, pay-per-use toggle, payment methods, billing information, invoices, refunds. |
| **Anonymous** | sha256 hash of the client ip (`x-forwarded-for`) matched against a Stripe customer carrying `metadata.anonymous_hashed_ip` — the exact scheme the Neural Nexus API uses for anonymous billing. | Read-only: free-tier subscription status and usage bars, plus a signup call-to-action pointing at the Neural Nexus API `/signup`. Anonymous users are always free tier and can never subscribe from the portal. |

Password verification is delegated to the Neural Nexus API rather than
reimplemented: one Auth0 tenant is the account authority for both systems, and
the portal only decides which **Stripe customer** an authenticated email maps
to. That mapping is per-Stripe-account, which is why a test account signs in at
the test portal and a live account at the live portal — the two Stripe accounts
must not be crossed.

**Single sign-on.** When the Neural Nexus application embeds this portal on its
billing page, it hands the frame a short-lived, single-use *billing portal
exchange code* by `postMessage`, pinned to the portal's exact origin. The portal
server spends that code at the API's `/redeem_billing_portal_exchange_code`
(HMAC-signed, machine-to-machine) and mints the same session a password sign-in
would. The application's own refresh token never crosses into the portal's
origin, so a session created this way has nothing for `/auth/logout` to revoke.
A shared cookie is not an option — inside the frame it would be a third-party
cookie, blocked by default in current browsers.

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
- ☑ Email + password login and signup, proxied to the Neural Nexus API
- ☑ Anonymous (hashed-ip) status/usage view with signup call-to-action
- ☑ Test and live environments (env-file switch, test-mode banner in the client)

Added after the sections above were written:
- ☑ **Real-time usage push** — the Neural Nexus API POSTs each metered turn to
  `/internal/usage-event`, which fans out over SSE (`/usage/stream`) so the bars
  move in seconds instead of waiting for Stripe's aggregation. Off unless
  `USAGE_EVENT_SHARED_SECRET` matches the API's `PORTAL_USAGE_EVENT_SECRET`;
  usage then falls back to the Stripe read alone, which is correct, just slower
- ☑ **Return to the application after Checkout** — a `return_to` supplied by the
  embedding page rides through Stripe on the success and cancel URLs, so a
  customer who started on the Neural Nexus billing page lands back there once
  the portal has reconciled the card. Origin-checked against `APP_RETURN_ORIGIN`
  on the server and again in the client before it is followed
- ☑ **Single sign-on from the Neural Nexus application** — see the identity
  model above. Off unless `NN_EXCHANGE_SHARED_SECRET` matches the API's
  `BILLING_PORTAL_EXCHANGE_SECRET`; the frame then shows this portal's own
  sign-in card, which is the designed fallback

## Portal server API

Scalar reference UI at `/reference`; OpenAPI/Swagger at `/docs`.

| Endpoint | Auth | Purpose |
|---|---|---|
| `POST /auth/login {email, password}` | none | Verify with the Neural Nexus API, return a bearer session token |
| `POST /auth/signup {email, password, name?}` | none | Create a Neural Nexus account (which creates the Stripe customer) |
| `POST /auth/single_sign_on {exchange_code}` | none | Spend a billing portal exchange code for the same session `/auth/login` returns |
| `POST /auth/logout` | verified | Revoke the Neural Nexus refresh token when the session carries one; stateless otherwise |
| `GET /config` | none | Publishable key, `test`/`live` environment, Neural Nexus API base URL |
| `GET /me` | any | Identity kind, customer id, name, email |
| `GET /subscription` | any | Tier, status, trial end, cancellation state, period bounds, pay-per-use flag, tier catalog |
| `GET /usage` | any | Per-meter `{monthly_allotment, used_to_date, remaining, overage_price_per_million, overage_price_per_unit_usd, unit}` + period bounds (field names match the Neural Nexus API's `/verify_subscription_status`) |
| `POST /subscription/checkout {tier}` | verified | Stripe Checkout session when no live subscription exists |
| `POST /subscription/change {tier, return_to?}` | verified | Dispatches: `start_checkout` / `no_change_required` / `reactivate` / `change_tier` (upgrade immediate, downgrade at period end). `return_to` is the Neural Nexus page to send the customer back to after Checkout, honoured only when its origin is in `APP_RETURN_ORIGIN` |
| `POST /subscription/cancel` | verified | `cancel_at_period_end = true` |
| `POST /subscription/reactivate` | verified | Undo pending cancellation / scheduled downgrade |
| `POST /pay_per_use {enabled}` | verified | Toggle overage billing; 402 when enabling without a card |
| `GET /invoices` | verified | Invoice history with `refundable`/`refunded` flags |
| `POST /invoices/{invoice_id}/refund` | verified | Full refund of a paid invoice |
| `GET /payment_methods` | verified | Card list with default flag |
| `POST /payment_methods/setup_intent` | verified | `client_secret` for the Elements add-card form |
| `POST /payment_methods/{id}/default` | verified | Set default card |
| `POST /payment_methods/reconcile` | verified | Collapse the duplicate card Checkout creates and make it reusable; called on the post-Checkout landing |
| `DELETE /payment_methods/{id}` | verified | Remove card (refused for the default card of an active paid subscription) |
| `GET /billing_info` / `PUT /billing_info` | verified | View / update name, address, phone |
| `POST /usage/stream-ticket` | any | Short-lived ticket authorising one `/usage/stream` connection (EventSource cannot send an Authorization header) |
| `GET /usage/stream` | ticket | Server-sent events pushing usage as it is metered, so bars move without waiting for Stripe aggregation |
| `POST /internal/usage-event` | HMAC | Machine-to-machine push from the Neural Nexus API after each metered turn. Hidden from the schema; refuses everything when `USAGE_EVENT_SHARED_SECRET` is unset |
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
| free | $0 | — | 2,000,000 @ $2.00/M | — | — | — |
| pro | $20/mo | 30 days | 5,000,000 @ $1.50/M | 10,000,000 @ $3.00/M | — | — |
| premium | $50/mo | — | 20,000,000 @ $1.25/M | 40,000,000 @ $2.50/M | 10,000,000 @ $4.00/M | 5 units @ $5.00/unit |

## Test and live environments

The two environments are two **simultaneously running stacks**, one compose
file and one env file each (both env files gitignored; every variable is
declared without values in
[src/server/.env.example](src/server/.env.example) and typed in
`settings.py`):

| Stack | Compose file | Env file | Project | Host port | Stripe | Reached by |
|---|---|---|---|---|---|---|
| live | `docker-compose.yml` | `.env` | `portal-live` | 8200 | `sk_live_` | Cloudflare tunnel → Vercel client |
| test | `docker-compose.dev.yml` | `.env.dev` | `portal-test` | 8202 | `sk_test_` | `http://localhost:5171` only |

This mirrors the Neural Nexus API repo, where `.env` is live and `.env.dev` is
test. `PORTAL_ENV=test` is what raises the client's TEST MODE banner. Both
compose files name their port and env file **literally** and set an explicit
`name:`, because they share a directory and `docker compose` auto-loads `./.env`
— the live file — as the interpolation source for both.

The provisioning script must have been run against each Stripe account, and two
variables must agree with the Neural Nexus API environment being reported on:
`USAGE_PERIOD_DAYS` and `DEV` (`FALSE` in live, or every anonymous visitor
collapses onto one Stripe customer).

## Deployment

- **Server**: `src/server/docker-compose.yml` runs `portal-server` (uvicorn on
  8080, published on host 8200). The public hostname
  `checkout-api.neuralnexus.site` is routed to that host port by a
  `cloudflared` **systemd service on the host**; the compose file also carries
  an optional bundled `cloudflared` under the `bundled-tunnel` profile, which
  is not what production uses. The server compose mounts no source, so any code
  change needs `up --build`.
- **Client**: Vercel project rooted at `src/client` (`vercel.json` provides the
  SPA rewrite); set `VITE_API_BASE_URL` to the tunnel hostname. A
  `src/client/docker-compose.yml` runs the Vite dev server for local work.

## Testing

- `src/server/tests/test_portal_flow.py` (pytest, Stripe/Auth0/Neural Nexus
  mocked by `monkeypatch.setattr` on the imported gateway modules, not at the
  HTTP layer): the full email + password sign-in flow, single sign-on by
  exchange code, anonymous hashed-ip resolution, `/subscription` and `/usage`
  response shapes (including over-allotment clamping and trial framing),
  refund settlement, and verified-only endpoint gating.
  `src/server/tests/test_billing_portal_exchange_signature.py` covers the HMAC
  construction shared with the Neural Nexus API byte for byte.
  `tests/conftest.py` sets the required env vars *before* `main` is imported.
- `src/server/scripts/stripe_test_mode_smoke.py` (manual, requires
  `sk_test_...`): catalog discovery against the provisioned account, customer
  creation + email lookup, pro checkout-session creation, a 72-token meter
  event with usage read-back through the analytics preview API, cleanup.
- Full metering scenarios (allotment exhaustion, 402 with pay-per-use off,
  overage billing per tier, usage reset/rollover across tier changes, trial
  end with/without a card) are exercised against the Neural Nexus API itself —
  see `_METERING_FEATURE_TESTING.md` in the f-metering repository; this portal
  displays the state those flows produce.
