# Auth0 tenant split — TABLED

**Status: tabled 2026-09-02. Not scheduled. Safe to leave until a trigger below fires.**

Tracked as D9 in [_PORTAL_ENVIRONMENT_STATUS.md](_PORTAL_ENVIRONMENT_STATUS.md).

## The problem, in three sentences

One Auth0 tenant (`dev-y3wkm2zfq1qzlef0.us.auth0.com`) serves both Neural Nexus
environments, but there are two Stripe accounts. `app_metadata.subscription_status`
and `stripe_customer_id` are single fields that **both** environments write, so for
any email touched in both, the last webhook to fire wins. Because development is the
environment in active use, every Auth0 record now holds a **test** Stripe customer id:

| Auth0 user | `stripe_customer_id` | Resolves in |
|---|---|---|
| `e.woods.business@icloud.com` | `cus_Ux1G8zxlKL1GFV` | TEST |
| `habite9140@robustq.com` | `cus_VBRR9JTcirLWZ5` | TEST |
| `tineyi5581@kolsea.com` | `cus_V81oV7GP6dRSA0` | TEST |
| `eveng1neer.business@gmail.com` | `cus_Ux1NmqcS8AOQYi` | TEST |
| `business@neuralnexus.site` | `cus_Ux1JytTtbjRXWB` | TEST |

The production API therefore cannot resolve a Stripe customer for **any** account in
the tenant.

## Why it is safe to table

**Live is effectively empty.** The live Stripe account holds three customers:
`habite9140@robustq.com` (trialing), `tewona3193@amupx.com` (no subscriptions), and
`billing_meters_test_customer@example.com` (a provisioning artifact). The first two are
temp-mail addresses — end-to-end tests of the live flow, not paying strangers.

**No real customer is harmed today.** Nothing is silently overcharging anyone, nothing
is losing data, and the development environment — the one actually in use — is
internally consistent and correct.

## Un-table immediately when any of these is true

- [ ] **A real customer signs up in live.** The first non-temp-mail live account makes
      this a live billing defect rather than a latent one.
- [ ] **Before any public launch.** This must be closed before the product is put in
      front of an audience.
- [ ] **Anything starts depending on `app_metadata.subscription_status` in live** —
      tier gating, allotment enforcement, or the customer portal serving live users.
- [ ] **A second person needs a working live account**, including for a demo.

## Call to action

Two things are needed, and only the first is blocking:

1. **Decide which environment gets the new tenant.** Live-stays-put is the safer
   default: production keeps whatever post-login Actions, email templates and
   connections the current tenant has. That could not be verified from here — the
   Management API app is scoped to user operations only, so `read:actions`,
   `read:connections` and `read:clients` all return 403. **Audit that in the dashboard
   before choosing**, because it is the only argument against moving live instead.
2. **Create the tenant in the Auth0 dashboard.** Tenant creation is an account-level
   action and is not exposed by the Management API, so it cannot be automated from
   here. It needs a `Username-Password-Authentication` database connection and a
   Machine-to-Machine application authorised for the Management API with at least
   `read:users`, `update:users` and `create:users`.

Everything after that is configuration and takes minutes — hand it back and it can be
finished in one pass.

## The work, once unblocked

No code changes, in any repository. Five keys, two repositories, four env files; the
frontend needs nothing, having no Auth0 configuration at all.

| File | Keys |
|---|---|
| `anubis/.env` | `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, `AUTH0_AUDIENCE`, `AUTH0_CONNECTION` |
| `anubis/.env.dev` | same five |
| `anubis-customer-portal/src/server/.env` | `AUTH0_DOMAIN`, `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET` |
| `anubis-customer-portal/src/server/.env.dev` | same three |

`AUTH0_AUDIENCE` is the tenant's Management API (`https://<domain>/api/v2/`), so it
moves with the domain. Then `--force-recreate` the API container and `up --build -d`
the portal server — a restart will not pick up an env-file change. Finally, re-register
the accounts needed in the moved environment: there are five, all owner-controlled test
addresses, so this is signup rather than migration.

## Meanwhile

Treat `app_metadata.subscription_status` and `stripe_customer_id` as describing the
**test** environment for every account, whatever environment is reading them.
