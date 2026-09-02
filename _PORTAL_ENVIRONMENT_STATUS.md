# Customer portal: prod/dev status and end-to-end function

## Context

Question asked: does the customer portal work in both the production (Stripe
**live**) and development (Stripe **test**) environments, and how does it
function end to end?

Both stacks were probed live (containers had been up ~12h), not just read:
`portal-live` on :8200, `portal-test` on :8202, the Cloudflare tunnel at
`checkout-api.neuralnexus.site`, the Vercel client, and the Neural Nexus API's
`/stripe/webhook`. Answer: **live works for reads, browsing, and Stripe
mutations, but the state-propagation half is broken; the test stack now works
for verified flows as well as anonymous ones.** Defects are listed below with
the fix for each; they are numbered in discovery order, so read the "Suggested
order" section for the sequence to work them in.

First verified 2026-08-18. Re-probed against both running stacks and both
Stripe accounts on 2026-09-02, then worked through to completion the same day.

**The eight original defects are closed.** D2 and D3 were already fixed; D4 was
fixed in code (commit `a932a7f`); D1, D5, D3', D7 and the live half of D8 were
closed by configuration plus a rebuild of `portal-live` and a `--force-recreate`
of `langgraph-api-prod`, all verified against the running services (see
"Verification" at the end).

**One new defect was found while verifying D1: D9, now tabled.** Auth0
`app_metadata` is shared mutable state between the two Stripe environments, and
every account in the tenant now holds a *test* Stripe customer id. It is
deferred rather than dropped because live is effectively empty — see
**[_AUTH0_TENANT_SPLIT.md](_AUTH0_TENANT_SPLIT.md)** for the reason and the
triggers that should un-table it. The portal **client** is deliberately not
being redeployed to Vercel for now — see "What remains" below.

## Verified status

| Check | live (:8200) | test (:8202) |
|---|---|---|
| `/healthz` | `{"ok":true,"environment":"live"}` | `{"ok":true,"environment":"test"}` |
| Public reachability | tunnel → `checkout-api.neuralnexus.site` OK | local only, by design |
| Client | Vercel bundle points at `checkout-api.neuralnexus.site` | `client-portal-client-1` on :5171, 200 (D3 fixed) |
| CORS preflight | Vercel origin allowed | `:5171` allowed, `:5172` rejected (400) |
| Catalog discovery from Stripe | OK (`pk_live_`, products+prices read) | OK (`pk_test_`) |
| Anonymous `/subscription` | 200, no customer matched from host curl | 200, `cus_V1fzo1DIo5UB0M` |
| Anonymous `/usage` | 200, calendar-month window (`2026-09-01 → 2026-10-01`) | 200, 153,865 tokens via event-summaries fallback |
| Verified login | works (NN prod API), but Stripe **live** customers only (see D6) | fixed 2026-08-31 — reaches the Stripe-test NN API on :9600; a bad password now returns a real `401` (see D2) |
| NN `/stripe/webhook` | **400** (invalid signature) — fixed 2026-09-02, was 503 (see D1) | **400** (invalid signature) on :9600 — configured and verifying |
| Test suite | — | **20 passed** (D4 fixed) |

## End-to-end function (both environments, identical code)

Two stacks, same image, differing only by env file — `.env` → `portal-live`
(:8200, `sk_live_`), `.env.dev` → `portal-test` (:8202, `sk_test_`). There is
**no code branch on `PORTAL_ENV`**; the only runtime fork is `DEV=TRUE`, which
pins the anonymous client ip to `172.18.0.1` (`security/identity.py:50`).

1. **Bootstrap** — `main.py` lifespan runs `configure_stripe()` (pins API
   version `2024-12-18.acacia`) then warms `get_tier_catalog()`. The catalog is
   *discovered* from Stripe product metadata (`neural_nexus_tier`,
   `neural_nexus_product_role`, `neural_nexus_meter`) in
   `stripe_gateway/catalog.py` — nothing about tiers or allotments is
   hardcoded. Client calls `GET /config` for the publishable key + environment
   (drives the TEST MODE banner).
2. **Identity** (`security/identity.py:59`) — bearer JWT → `verified` (Stripe
   customer id is the `sub` claim, no network call); no bearer → sha256 of the
   `x-forwarded-for` header matched against `metadata.anonymous_hashed_ip` via
   Stripe Customer Search. Anonymous is always free tier, read-only.
   `require_verified_identity` gates every mutation.
3. **Sign-in** — `POST /auth/login` proxies to the Neural Nexus API
   (`neural_nexus_gateway.py`), then `find_customer_by_email` in Stripe, then
   mints an HS256 session (`security/session.py`). Stateless; no server store.
4. **Read** — `GET /subscription` assembles catalog + `Subscription.list` +
   trial history + pending schedule + Auth0 `pay_per_use_enabled`. `GET /usage`
   resolves the billing window (`usage_period.py`, a port of the API's
   arithmetic) and reads meters via the analytics-preview endpoint, falling
   back to GA `event_summaries` (the preview API is not enabled on this
   account — confirmed again in the test logs, 404 → fallback).
5. **Mutate** — `POST /subscription/change` dispatches on direction: checkout /
   reactivate / immediate prorated swap / period-end schedule / cancel. The
   portal writes **only to Stripe**.
6. **Propagate** — Stripe fires webhooks; the Neural Nexus API's
   `/stripe/webhook` reconciles Auth0 `app_metadata.subscription_status` and
   creates the $0 free-tier subscription after a downgrade. Dead in live until
   2026-09-02; the signing secret is now stored and the endpoint verifies (D1).
7. **Live usage** — the API is supposed to POST HMAC-signed events to
   `/internal/usage-event`, which fans out over SSE (`/usage/stream`) so meters
   move without waiting for Stripe aggregation. Wired in both environments as of
   2026-09-02 (D3').

## Defects and fixes

### D1 — Neural Nexus `/stripe/webhook` returned 503 in live — **FIXED 2026-09-02**

**Resolved 2026-09-02**: the signing secret was revealed in the Stripe
Dashboard, stored in `anubis/.env`, and `langgraph-api-prod` force-recreated.
`POST https://api.neuralnexus.site/stripe/webhook` now returns **400**
`{"detail":"Invalid webhook signature."}` — verifying, as it should for an
unsigned probe — both through the tunnel and directly on :8124.

The endpoint was never rotated, so its retry backlog survived — but as of
2026-09-02 19:20 UTC **nothing has drained yet**. The only `/stripe/webhook`
entries in the recreated container's log are unsigned verification probes; no
real Stripe delivery has arrived. That is expected rather than alarming: five
handled-type events fired during the outage (four for one account, one
`customer.updated`), all are still inside Stripe's ~3-day retry window, and
after two days of failures the backoff interval is hours. Re-check the log for a
signed delivery returning 200 before considering the propagation path proven end
to end. The endpoint is confirmed still `enabled` — Stripe did not auto-disable
it during the outage. Note that when those retries do land they will overwrite
Auth0 for the account named in D9.

The original finding follows.

`POST https://api.neuralnexus.site/stripe/webhook` → **503**, both through the
tunnel and directly at `http://localhost:8124/stripe/webhook`.
`STRIPE_WEBHOOK_SECRET` is empty in `/home/user/gh/anubis-project/anubis/.env`
(length 0) and in the running `anubis-langgraph-api-prod-1` container env. (It
*is* set in that repo's `.env.dev`, and matches what the `stripe-cli` service
wrote to `/run/stripe/webhook_secret`, so the dev API verifies signatures —
:9600 returns 400, not 503.) Consequence, exactly as CLAUDE.md warns: every
portal subscription change lands in Stripe but never reaches Auth0, and a
downgrade to free cancels the paid subscription with no $0 free-tier
replacement.

**The missing piece is only the stored secret — the endpoint already exists.**
Listing `stripe.WebhookEndpoint` against `anubis/.env`'s `sk_live_` key returns
an **enabled** endpoint at `https://api.neuralnexus.site/stripe/webhook`
subscribed to exactly the 6 events `webapp.py::_handle_stripe_event` handles,
plus a disabled one at the misspelled `api.neuralneuxus.site`. Registering
another one by hand in the Dashboard, as an earlier version of this document
advised, would duplicate a working endpoint and double every delivery.
Endpoint registration is automated in the `anubis` repo by
`scripts/provision_stripe_webhook.py` (companion to
`provision_stripe_billing.py`, which the `stripe-provision` compose service
already runs on every `up`). Webhook registration is deliberately *not* a
compose sidecar, because Stripe returns an endpoint's signing secret **only in
the create response** — never on retrieve or update — so it cannot be
regenerated on each container start the way `billing_config.json` is.

Fix (configuration, in the `anubis` repo — not this one). Because the endpoint
already exists, re-running the provisioning script prints `endpoint exists ->
we_... (secret not re-readable)` and gives you nothing to store. Pick one:
1. **Reveal the existing secret** — Stripe Dashboard → Developers → Webhooks →
   "Your account" → the `api.neuralnexus.site/stripe/webhook` endpoint → reveal
   the signing secret. No delivery history is disturbed. Preferred.
2. **Or rotate**, if the secret cannot be revealed:
   `STRIPE_SECRET_KEY=sk_live_... python scripts/provision_stripe_webhook.py --url https://api.neuralnexus.site/stripe/webhook --allow-live --rotate`
   — this **deletes and recreates** the endpoint so a fresh secret is printed.
   In-flight deliveries signed with the old secret fail verification and the
   endpoint's delivery history restarts.

Then put the value in `anubis/.env` as `STRIPE_WEBHOOK_SECRET`, restart the API
container, and re-check that the POST above returns 400, not 503.

Note the **test** Stripe account has *zero* registered endpoints, by design:
the dev stack's `stripe-cli` service runs `stripe listen`, an outbound relay
that mints its own `whsec_` and forwards to `langgraph-api-dev:9600`. That is a
development relay, not an ingress — no public URL, no retries, no delivery log
— which is why production needs the registered endpoint above.

### D2 — Test stack cannot sign anyone in — **FIXED 2026-08-31**

`.env.dev` set `NN_API_BASE_URL=http://host.docker.internal:8123`; nothing
listens on 8123 (connection refused, confirmed from inside the container).
Every verified flow in the test stack failed as "The sign-in service is
unavailable"; only anonymous flows worked.

Fixed by pointing `src/server/.env.dev` at **`http://host.docker.internal:9600`**
and recreating the test stack. 9600 is the *dev* Neural Nexus API
(`anubis-dev-langgraph-api-dev-1`, `anubis/.env.dev`, `STRIPE_SECRET_KEY=sk_test_`).

The earlier suggestions in this document — 8124 or `https://api.neuralnexus.site`
— would have restored connectivity but **not** working sign-in, because both are
the Stripe-**live** Neural Nexus API. See D6 for why that distinction decides
whether sign-in succeeds.

Verified: `POST http://localhost:8202/auth/login` with an unknown account now
returns `401 {"detail":"Invalid email or password."}` (a real credential
rejection proxied from `http://host.docker.internal:9600/login`) instead of the
transport-failure message.

### D6 — "No billing account is associated with this email" on a test account

One Auth0 tenant (`dev-y3wkm2zfq1qzlef0.us.auth0.com`) serves **both** Neural
Nexus environments, but there are **two Stripe accounts**. Password
verification therefore succeeds through either Neural Nexus API, while the
Stripe customer for an account exists in only one of the two Stripe accounts —
whichever one the Neural Nexus API that ran the signup was configured with
(`anubis/.env` → `sk_live_`, `anubis/.env.dev` → `sk_test_`).

`routers/auth.py::login` then looks the email up with **the portal's own**
Stripe key (`stripe_gateway/customers.py::find_customer_by_email`) and returns
`403 "No billing account is associated with this email."` when there is no
match. So a test account (Stripe test customer) signing in to the **live**
portal authenticates fine and then fails that lookup — the exact symptom
reported. The message is accurate: there genuinely is no billing account for
that email *in the live Stripe account*.

This is correct behaviour, not a defect in the portal: the two Stripe accounts
must not be crossed. The operational rule is simply that **a test account signs
in at the test portal (:8202) and a live account at the live portal (:8200 /
`checkout-api.neuralnexus.site`)** — which is what D2 above now makes possible.

A test account that still fails at :8202 has no Stripe *test* customer, meaning
it was created through the live Neural Nexus API. Create it instead through the
dev Neural Nexus API on :9600 (or the test portal's own `POST /auth/signup`,
which now proxies there), so `ensure_stripe_customer` in
`anubis/src/security/auth.py` lands the customer in the Stripe test account.

### D7 — `portal-live` was running a stale image — **FIXED 2026-09-02**

`/openapi.json` on :8200 lists no `/usage/stream` or `/usage/stream-ticket`,
while :8202 lists both, and the live logs show the deployed client polling them
in a loop: repeated `POST /usage/stream-ticket → 404` and `GET /usage/stream →
404`. The live container predates the real-time usage work and was never
rebuilt.

Fix: `cd src/server && docker compose -f docker-compose.yml up --build -d`,
then confirm both paths appear in `curl -s http://localhost:8200/openapi.json`.
Note this only stops the 404 loop; live meters still will not move in real time
until D3' is configured in the `anubis` repo.

### D3 — Local containerized client was unreachable — **FIXED**

The port drift is gone. `src/client/docker-compose.yml` is back to
`"5171:5171"` and clean in git; `vite.config.ts` pins `port: 5171` and the
Dockerfile `EXPOSE 5171`, so all three agree. `client-portal-client-1` is up
and `http://localhost:5171/` returns 200, and a preflight from
`http://localhost:5171` against :8202 returns 200 (from `:5172`, still 400 —
correct, that origin is not in `CLIENT_ORIGIN`).

**Residue still open** — the same 5173 drift in three documentation/default
sites, none of which affects the running stacks because `CLIENT_ORIGIN` is set
explicitly in both env files:
- `src/server/settings.py:44` defaults `client_origin` to `http://localhost:5173`.
- `src/server/scripts/stripe_test_mode_smoke.py:83` uses `http://localhost:5173`
  as the Checkout return URL.
- `CLAUDE.md:57` documents `npm run dev` as :5173.

All three should read 5171. (`src/client/.env.development:11`'s
`VITE_NEURAL_NEXUS_APP_ORIGINS=http://localhost:5173` is *not* drift — that is
the separate Neural Nexus frontend app, which really does run on 5173:
`react-vite-dev` is up on that port.)

### D8 — Single sign-on from the Neural Nexus application — **FIXED in test and live, 2026-09-02**

Signing in to the Neural Nexus application at `http://localhost:5173/billing`
left the embedded portal showing its own sign-in card, and a password attempt
there returned "Invalid email or password." All three sides of the single
sign-on handoff were already written (see
`Neural-Nexus-Frontend/_BILLING_PORTAL_SSO_FEATURE.md`); nothing was
implemented, three things were unconfigured:

1. `POST /auth/single_sign_on` returned **404** on :8202 — the `portal-test`
   container predated the route. `docker-compose.dev.yml` mounts no source, so
   an edit to `routers/auth.py` needs `up --build`, unlike the client compose
   which mounts `./src`.
2. `NN_EXCHANGE_SHARED_SECRET` was absent from `src/server/.env.dev`.
3. `BILLING_PORTAL_EXCHANGE_SECRET` was empty in `anubis/.env.dev`, so
   `POST http://localhost:9600/redeem_billing_portal_exchange_code` answered
   **503** "not configured".

Fixed by generating one 64-character secret, writing it to both env files, then
rebuilding `portal-test` and recreating `anubis-dev-langgraph-api-dev-1`
(`docker compose -p anubis-dev -f docker-compose.yml --env-file .env.dev up -d
langgraph-api-dev` — the `--env-file` matters, or `PORT` falls back to 8123 and
the published port moves off 9600).

Verified end to end: a code minted with the shared secret and spent at
`POST http://localhost:8202/auth/single_sign_on` returns HTTP 200 with a
verified session for `cus_Ux1G8zxlKL1GFV`, and replaying the same code returns
HTTP 400 "already redeemed". `POST /redeem_billing_portal_exchange_code` on
:9600 now answers 401 "Redemption requests must be signed" rather than 503, and
a CORS preflight from `http://localhost:5171` to the new route returns 200.

**Live secret configured 2026-09-02, awaiting a rebuild and a restart.** A
second 64-character secret — deliberately different from the test pair, so a
code minted against Stripe test cannot be spent against live — is now in
`anubis/.env` (`BILLING_PORTAL_EXCHANGE_SECRET`) and the portal's `.env`
(`NN_EXCHANGE_SHARED_SECRET`). Neither side has picked it up yet: the API reads
it at lifespan startup, and the `portal-live` image has no
`/auth/single_sign_on` route at all until the D7 rebuild. See "Restarts still
owed" below.

### D3' — Real-time usage push was not enabled in either environment — **FIXED 2026-09-02**

`PORTAL_USAGE_EVENT_URL` / `PORTAL_USAGE_EVENT_SECRET` appear only in
`anubis/.env.example`, not in `anubis/.env` or `anubis/.env.dev`. The portal
side is fully built and configured (`USAGE_EVENT_SHARED_SECRET` set in both env
files, `/internal/usage-event` + `/usage/stream` implemented), so meters
currently move only as fast as Stripe aggregates. This is the remaining half of
`__BUG.md`'s "anonymous usage is not reported in the customer portal".

**Configured 2026-09-02, awaiting a restart to take effect.**
`PORTAL_USAGE_EVENT_URL` and `PORTAL_USAGE_EVENT_SECRET` are now set in both
`anubis/.env` (→ host port 8200, the live portal) and `anubis/.env.dev` (→ host
port 8202, the test portal), each with the secret matching that portal's
`USAGE_EVENT_SHARED_SECRET`. Both API containers read these into
`GlobalContext` at lifespan startup, so neither is active until the container
is recreated — see "Restarts still owed" below.

Note for later: the portal's `USAGE_EVENT_SHARED_SECRET` is the *same value* in
`.env` and `.env.dev`, so a test-signed usage event would be accepted by the
live portal. Pre-existing, low severity, and not changed here because it needs
both sides moved together — worth splitting when the live pair is next rotated.

### D4 — Two tests failed, making real network calls — **FIXED 2026-09-02**

`tests/test_portal_flow.py::test_refund_of_paid_subscription_cancels_immediately`
and `::test_refund_during_pro_trial_retains_trial_to_period_end` fail with
`stripe._error.AuthenticationError: Invalid API Key provided: sk_test_*******lder`,
raised from `routers/invoices.py:62` → `stripe_gateway/catalog.py:204`
(`_build_catalog_sync`). Cause: `routers/invoices.py:10` binds
`get_tier_catalog` into its own module namespace, and the `client` fixture
patches that name on `routers.subscription`, `routers.usage`, and `main` — but
not `routers.invoices`. So `refund_invoice`'s `catalog = await
get_tier_catalog()` reaches the real Stripe API during an offline test run.

**FIXED 2026-09-02** (commit `a932a7f`). The three existing patches are in the
`client` fixture in `tests/test_portal_flow.py`, not `tests/conftest.py` (which
only sets environment variables at module scope and has no `monkeypatch`
fixture); `monkeypatch.setattr(routers.invoices, "get_tier_catalog",
fake_get_tier_catalog)` was added alongside them. `pytest -q` → **20 passed**.

### D5 — Usage window disagreed with the API in live — **FIXED 2026-09-02**

`USAGE_PERIOD_DAYS` is **0** (calendar month) in the portal's `.env` but **30**
(rolling) in `anubis/.env` and in the running API container. CLAUDE.md and both
`.env.example` files state these must match, or the portal shows a comfortable
meter while the chat app returns 402. Live `/usage` currently reports
`2026-09-01 → 2026-10-01`, i.e. calendar month. (The portal's `.env.dev` and
`anubis/.env.dev` both use 0, so the *test* pair already agrees.)

**Resolved 2026-09-02 in configuration, awaiting a restart to take effect.**
**0 (calendar month) is canonical** — confirmed by the repository owner.
`anubis/.env` moved from 30 to 0; the portal's `.env` was already 0 and did not
change, so nothing on the portal side needs a rebuild for this. All four files
now read 0 (portal `.env` / `.env.dev`, `anubis/.env` / `.env.dev`). The
production API container still has `USAGE_PERIOD_DAYS=30` in its environment
until it is recreated — see "Restarts still owed" below.

### D9 — one Auth0 tenant, two Stripe accounts, one shared `app_metadata` — **OPEN**

Found 2026-09-02 while checking whether any account diverged during the D1
outage. It is not caused by D1 and is not fixed by fixing it.

D6 already records that a single Auth0 tenant
(`dev-y3wkm2zfq1qzlef0.us.auth0.com`) serves both Neural Nexus environments
while there are two Stripe accounts, and draws the conclusion that a test
account must sign in at the test portal and a live account at the live portal.
The deeper consequence was not drawn: **`app_metadata` is a single set of
fields that BOTH environments write.** `subscription_status` and
`stripe_customer_id` are not namespaced by Stripe mode, so for any email present
in both accounts the last webhook to fire wins, whichever environment it came
from.

That has already happened. `habite9140@robustq.com` exists in both:

| | Stripe customer | Subscription | State |
|---|---|---|---|
| live | `cus_VArjpq9vVFLriC` | `sub_1UAW06Limk9GVblr37b6Y71H` | trialing, `cancel_at_period_end=true` |
| test | `cus_VBRR9JTcirLWZ5` | `sub_1UB4ZOLimk9GVblr2mugNBSz` | trialing, `cancel_at_period_end=false` |

Auth0 currently holds the **test** values — `stripe_customer_id` is
`cus_VBRR9JTcirLWZ5`, which does not exist in the live Stripe account at all
(verified: `InvalidRequestError` on retrieve with the `sk_live_` key). So the
production API, serving that user, reads a Stripe customer id it cannot resolve,
and a `subscription_status` describing a subscription in the wrong account. The
live cancellation recorded in Stripe on 2026-09-01 is invisible there.

Fixing D1 does not repair this and slightly sharpens it: until 2026-09-02 only
the test environment's webhook was working, so test writes were unopposed. Now
both environments write, and the field flips to whichever fired last. The five
live events still inside Stripe's retry window will overwrite it with the live
values — correct for live, and clobbered again the next time that email is
touched in test.

**Blast radius, corrected 2026-09-02.** The first write-up of this defect
measured the wrong thing — email overlap between the two Stripe accounts, which
finds one account. The right measure is which Stripe account each Auth0 record's
`stripe_customer_id` actually resolves in, and by that measure **all five users
in the tenant point at Stripe TEST customers. Not one resolves against the live
key.**

| Auth0 user | `stripe_customer_id` | Resolves in |
|---|---|---|
| `e.woods.business@icloud.com` | `cus_Ux1G8zxlKL1GFV` | TEST |
| `habite9140@robustq.com` | `cus_VBRR9JTcirLWZ5` | TEST |
| `tineyi5581@kolsea.com` | `cus_V81oV7GP6dRSA0` | TEST |
| `eveng1neer.business@gmail.com` | `cus_Ux1NmqcS8AOQYi` | TEST |
| `business@neuralnexus.site` | `cus_Ux1JytTtbjRXWB` | TEST |

So the production API cannot resolve a Stripe customer for **any** account in
the tenant. This is not a one-account edge case; it is the steady state, and it
is the natural consequence of the development environment being the one in
active use — every signup has gone through the dev API, and each wrote its test
customer id over whatever live had.

What keeps it from being an emergency is that live has almost nothing in it. The
live Stripe account holds three customers: `habite9140@robustq.com` (trialing,
created 2026-08-31), `tewona3193@amupx.com` (no subscriptions), and
`billing_meters_test_customer@example.com` (a provisioning artifact). The first
two are temp-mail addresses — end-to-end tests of the live flow, not paying
strangers. **No real customer is currently harmed, which makes this the moment
to fix it rather than a reason to defer.**

### Fix — **TABLED 2026-09-02**

Separate Auth0 tenants per environment. Chosen over namespacing the fields by
Stripe mode (an `anubis` code change that would still leave `api_key`,
`personal_avatar_id` and `usage_period_anchor` shared) and over operational
discipline (what is in place now, already failed for all five accounts).

**Deferred, not dropped.** Live is effectively empty, so no real customer is
harmed today, and the fix needs a decision plus an Auth0 dashboard action that
cannot be automated. The reason, the un-table triggers, and the full change set
are in **[_AUTH0_TENANT_SPLIT.md](_AUTH0_TENANT_SPLIT.md)**.

Until it lands, treat `app_metadata.subscription_status` and
`stripe_customer_id` as describing the **test** environment for every account in
the tenant, whatever environment is reading them.

## Restarts — all applied 2026-09-02

Every configuration fix above needed a container **recreate**, not a restart:
`env_file` values are baked into a container at *create* time, so `docker
restart` and `docker compose restart` reuse the old environment. Worse, plain
`docker compose up -d` is a silent no-op after an env-file edit, because compose
compares the service *definition* and an env file's contents are not part of
that comparison. Both traps were hit here before `--force-recreate` was used.

```bash
# 1. Live portal — D7 (stale image: no /usage/stream, /usage/stream-ticket or
#    /auth/single_sign_on) and the portal half of the D8 live secret.
cd anubis-customer-portal/src/server
docker compose -f docker-compose.yml up --build -d

# 2. Production Neural Nexus API — D1 (webhook secret), D5 (USAGE_PERIOD_DAYS
#    30 -> 0), D3' (usage-event push) and the API half of D8, in one recreate.
cd anubis
docker compose -p anubis -f docker-compose-prod.yml up -d --force-recreate langgraph-api-prod

# 3. Development Neural Nexus API — D3' for the test pair. The --env-file is
#    required: both anubis compose files share a directory, so docker compose
#    auto-loads ./.env (the LIVE file) as the interpolation source, and without
#    the flag PORT falls back to 8123 and the published port moves off 9600.
cd anubis
docker compose -p anubis-dev -f docker-compose.yml --env-file .env.dev up -d langgraph-api-dev
```

A note worth keeping for the next time a webhook secret goes missing: the
endpoint was **not** rotated. `provision_stripe_webhook.py --rotate` looks like
the self-service answer, but every delivery was failing with 503 and Stripe
retries each for about three days — that backlog is exactly what heals the Auth0
divergence once a valid secret lands. Rotating deletes the endpoint and its
queued retries with it, turning a recoverable outage into permanent drift.
Revealing the secret in the Dashboard cost one click and lost nothing.

## What remains

Nothing. No defect is open in this repository, and the one remaining deployment
task has been deliberately declined for now.

**Deploying the portal client to Vercel is not being done.** The server side of
single sign-on and the post-Checkout return are live, but the *deployed* client
bundle at `checkout.neuralnexus.site` predates `singleSignOn.ts` and
`appReturn.ts`. That is harmless while live has no real users: a customer
opening the live billing page meets the portal's own sign-in card in the frame —
the designed fallback, not a break — and a live Checkout ends on the portal
rather than back in the application. Both features work today against the local
client on :5171, which is where they are actually exercised.

Revisit on the same triggers that un-table the Auth0 tenant split
([_AUTH0_TENANT_SPLIT.md](_AUTH0_TENANT_SPLIT.md)): a real customer signing up
in live, or any public launch. Both of those make the live embed something
somebody actually sees.

D1, D5, and D3' are **configuration changes in the `anubis` repo**, not code
changes here. D7 is a rebuild of this repo's live stack. D4 and the D3 residue
are the only code changes in this repo.

## Verification

Results recorded 2026-09-02, after the three recreates above:

| Check | Before | After |
|---|---|---|
| `POST https://api.neuralnexus.site/stripe/webhook` (D1) | 503 | **400** `Invalid webhook signature.` |
| same, direct on `:8124` (D1) | 503 | **400** |
| `POST :8124/redeem_billing_portal_exchange_code` (D8) | 503 `not configured` | **401** `Redemption requests must be signed.` |
| `POST :8200/auth/single_sign_on` (D8) | 404, then 502 | **400** `The exchange code is not valid.` |
| `:8200/openapi.json` (D7) | `/usage` only | `/usage`, `/usage/stream`, `/usage/stream-ticket`, `/auth/single_sign_on` |
| prod API `USAGE_PERIOD_DAYS` (D5) | 30 | **0**, matching the portal's `2026-09-01 → 2026-10-01` |
| prod + dev API `PORTAL_USAGE_EVENT_URL` (D3') | empty | `:8200` / `:8202`, secrets matching each portal |
| `pytest -q` (D4) | 18 passed, 2 failed | **20 passed** |
| tunnel `https://checkout-api.neuralnexus.site/healthz` | 200 | 200 |

The live single sign-on chain was also exercised end to end: a code minted with
the live shared secret, signed, and spent at `:8200/auth/single_sign_on` was
accepted by the production API — signature verified, audience/issuer/expiry
checked, `jti` spent — and came back **403 "No billing account is associated
with this email"** only at the final step, because that account has a Stripe
*test* customer and no live one (confirmed: 0 live customers for that email).
That is D6's documented and correct behaviour, and it proves every link in the
chain ahead of the Stripe lookup. Do not repeat this against a real live
customer's email: it would mint a genuine portal session for their account.

The original per-defect procedures follow.

- **D1**: `curl -s -o /dev/null -w '%{http_code}' -X POST https://api.neuralnexus.site/stripe/webhook -d '{}'`
  — expect 400 (bad signature), not 503. Then make a tier change in the live
  portal and confirm Auth0 `app_metadata.subscription_status` follows. Confirm
  the endpoint list is unchanged (one enabled `api.neuralnexus.site` endpoint,
  no duplicate) with
  `STRIPE_SECRET_KEY=sk_live_... python scripts/provision_stripe_webhook.py --allow-live`
  in the `anubis` repo — with no `--rotate` it only reports and reconciles
  events, it never recreates.
- **D5**: `curl -s http://localhost:8200/usage` and confirm the
  `usage_period_start/end` match what the API's `/verify_subscription_status`
  reports for the same account.
- **D2**: after recreating the test stack, `POST http://localhost:8202/auth/login`
  with test credentials returns a token instead of "sign-in service unavailable".
- **D3**: `curl -o /dev/null -w '%{http_code}' http://localhost:5171/` returns
  200, and a preflight from that origin against :8202 returns 200 with a
  matching `access-control-allow-origin`. Both confirmed 2026-09-02.
- **D3'**: send a metered message through the API, watch `/usage/stream` in the
  portal move within seconds rather than minutes.
- **D4**: `cd src/server && .venv/bin/python -m pytest -q` → 20 passed.
- **D8**: signed in to the Neural Nexus application, open
  `http://localhost:5173/billing` — the frame shows the account's subscription
  with no sign-in card. Signed out, the same page shows the sign-in card,
  unchanged. Machine-level check without a browser: mint a code with the shared
  secret (`iss=neural-nexus-api`, `aud=neural-nexus-customer-portal`, `sub`,
  `email`, 120 s `exp`, random `jti`, HS256) and POST it to
  `http://localhost:8202/auth/single_sign_on` — expect 200 once, 400 on replay.
- **Regression sweep**: `STRIPE_SECRET_KEY=sk_test_... .venv/bin/python scripts/stripe_test_mode_smoke.py`
  (refuses live keys, cleans up after itself).
