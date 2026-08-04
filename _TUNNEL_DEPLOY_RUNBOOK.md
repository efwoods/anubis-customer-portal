# Portal deploy runbook — Cloudflare tunnel + Vercel client

Connect the local Docker portal server to the public internet and point the
Vercel client at it.

**Target topology**

```
Browser at https://checkout.neuralnexus.site   (Vercel: anubis-customer-portal)
        │  HTTPS + CORS, bearer session token
        ▼
https://checkout-api.neuralnexus.site           (Cloudflare tunnel: neuralnexus-api)
        ▼  host cloudflared systemd service, ingress rule -> http://localhost:8200
portal-server  (LIVE stack: project portal-live, .env, :8200 -> container :8080)
        ├──► Stripe (live keys)
        ├──► Auth0 Management API
        └──► https://api.neuralnexus.site        (login / logout / signup)

portal-server-dev  (TEST stack: project portal-test, .env.dev, :8202)
        └── not tunnelled; reachable only from this host
```

**Only the live stack is public.** The tunnel's ingress rule names host port
8200, so the test stack on 8202 is unreachable from the internet by
construction — there is no second hostname to forget to lock down.

**One tunnel serves both hostnames.** Rather than a second tunnel plus a
`cloudflared` sidecar container, the portal reuses the existing
`neuralnexus-api` tunnel (`980ecf10-3835-4226-a164-dc22d13b2dc9`) that already
runs as a host systemd service. Its config file carries one ingress rule per
hostname. This is why there is no `TUNNEL_TOKEN` in `.env.dev` and why the
compose `cloudflared` service sits behind the `bundled-tunnel` profile
(unused on this host).

---

## 1. Cloudflare tunnel ingress — DONE

Applied on this host; documented here for rebuilds and for anyone reproducing
the setup on a new machine.

**1a. Ingress rule** — `~/.cloudflared/config.yml` (mirrored in the Anubis repo
at `anubis/cloudflare/config.yml`):

```yaml
tunnel: 980ecf10-3835-4226-a164-dc22d13b2dc9
credentials-file: /home/user/.cloudflared/980ecf10-3835-4226-a164-dc22d13b2dc9.json

ingress:
  # Neural Nexus API (Anubis LangGraph API, prod container).
  - hostname: api.neuralnexus.site
    service: http://localhost:8124
  # Customer portal backend-for-frontend (anubis-customer-portal server
  # container, published on the host as :8200 -> container :8080).
  - hostname: checkout-api.neuralnexus.site
    service: http://localhost:8200
  - service: http_status:404
```

Note the ingress targets `http://localhost:8200` (the **host-published** port),
because cloudflared runs on the host — not `portal-server:8080`, which would
only be correct for a cloudflared container inside the compose network.

Validate before restarting anything:

```bash
cloudflared tunnel --config ~/.cloudflared/config.yml ingress validate
cloudflared tunnel --config ~/.cloudflared/config.yml ingress rule https://checkout-api.neuralnexus.site/healthz
```

**1b. DNS record** — created with (idempotent; safe to re-run):

```bash
cloudflared tunnel route dns neuralnexus-api checkout-api.neuralnexus.site
```

This adds the proxied `CNAME checkout-api.neuralnexus.site → <tunnel-id>.cfargotunnel.com`.

**1c. Reload the connector** — required for a config change to take effect;
briefly interrupts `api.neuralnexus.site` (a few seconds) since both hostnames
share the connector:

```bash
sudo systemctl restart cloudflared
systemctl status cloudflared --no-pager
journalctl -u cloudflared -n 30 --no-pager
```

Healthy logs show `Registered tunnel connection` (~4 connections).

---

## 2. Bring the servers up

Each stack names its own compose file; neither takes `--env-file`, because each
compose file names its env file literally.

```bash
cd src/server
docker compose -f docker-compose.dev.yml up --build -d   # portal-test  :8202  (.env.dev, sk_test_)
docker compose -f docker-compose.yml     up --build -d   # portal-live  :8200  (.env,     sk_live_)

docker compose -f docker-compose.yml ps                  # expect: Up (healthy)
curl -s http://localhost:8200/healthz                    # {"ok":true,"environment":"live"}
curl -s http://localhost:8202/healthz                    # {"ok":true,"environment":"test"}
```

Watch the live stack's startup log once: `Tier catalog discovered at startup:
['free', 'premium', 'pro']` confirms the Stripe environment is provisioned. A
`NO provisioned tiers` warning instead means checkout and tier changes will
return HTTP 503 until the Neural Nexus API repo's
`scripts/provision_stripe_billing.py` has been run against that account's key.

If a stack was previously started under the old shared project name `server`,
bring it down under that name first or port 8200 stays bound:

```bash
docker compose -p server -f docker-compose.yml -f docker-compose.dev.yml down
```

The compose `cloudflared` service is **not** started by these commands — it is
guarded by the `bundled-tunnel` profile and is only for hosts with no existing
tunnel (`docker compose --profile bundled-tunnel up --build`, which needs
`TUNNEL_TOKEN` set and a tunnel hostname pointing at `portal-server:8080`).

---

## 3. Vercel (anubis-customer-portal project)

Deploys are triggered by **push to `main`** on GitHub.

**3a. API URL — committed, no dashboard step**
`src/client/.env.production` holds `VITE_API_BASE_URL=https://checkout-api.neuralnexus.site`.
Vite loads `.env.production` during `vite build` (the production-mode build
Vercel runs), so the push-triggered deploy inlines the tunnel hostname with no
Vercel environment variable required. The file is committed on purpose — the
value is a public URL — via a `!src/client/.env.production` negation in
`.gitignore`.

If a `VITE_API_BASE_URL` project environment variable is ever added in the
Vercel dashboard, it takes precedence over this file.

**3b. Client domain — Cloudflare redirect (same pattern as `ui`)**
`checkout.neuralnexus.site` 302-redirects to the `anubis-customer-portal.vercel.app`
production alias — identical mechanism to `ui.neuralnexus.site` (which redirects
to its Streamlit app). The branded URL is only the entry point; after the bounce
the address bar shows the `.vercel.app` URL. The domain is **not** added to the
Vercel project. All steps are in the Cloudflare dashboard (`neuralnexus.site`
zone); there is no Cloudflare API token on the host and `cloudflared` cannot
create these, so this is manual.

- **DNS → Records → Add record:** `A` `checkout` → `192.0.2.1` (dummy, same as
  the `ui` record), **Proxied (orange cloud)**. Redirect Rules only run on
  proxied traffic. This is separate from the `checkout-api` tunnel record.
- **Rules → Redirect Rules → Create rule** (Single Redirect, `checkout → Vercel portal`):
  - When `Hostname` `equals` `checkout.neuralnexus.site`.
  - URL redirect, **Dynamic**:
    - Expression: `concat("https://anubis-customer-portal.vercel.app", http.request.uri.path)`
    - Status code **302 (Temporary)** — a 301 gets hard-cached by browsers and
      would fight a later switch to a true proxy.
    - Preserve query string: **On**.
  - (Static alternative, matching `ui` exactly: redirect to
    `https://anubis-customer-portal.vercel.app/` with no path preservation.)
  - Deploy.

After the redirect the effective origin is `anubis-customer-portal.vercel.app`,
which `CLIENT_ORIGIN` already allows, so no code change is needed.

**3c. Deploy**
Push to `main`. A rebuild is what picks up `.env.production`, so any change to
that file needs a new deploy (not just a promote/rollback of an old build).

---

## 4. Verify end-to-end

**4a. Tunnel reachable, serving the live environment**
```bash
curl -s https://checkout-api.neuralnexus.site/healthz   # {"ok":true,"environment":"live"}
```
The `environment` field is the check that matters — a `200` alone does not tell
you which Stripe account is behind it. (`https://checkout-api.neuralnexus.site/reference`
should load the Scalar API docs in a browser.) Confirm `api.neuralnexus.site`
still answers too, since the restart in 1c affects both.

**4b. CORS from the deployed origin**
```bash
curl -si -X OPTIONS https://checkout-api.neuralnexus.site/subscription \
  -H 'Origin: https://anubis-customer-portal.vercel.app' \
  -H 'Access-Control-Request-Method: GET' | grep -i access-control-allow-origin
```

**4c. Client → server**
- Open the deployed client with DevTools → **Network** open.
- **Sign up** and/or **log in** with email + password.
  - Auth is proxied to `api.neuralnexus.site` (Auth0). **Login only succeeds for
    an email that already has a Stripe customer.**
- Confirm:
  - **No TEST MODE banner** — the live server reports `PORTAL_ENV=live`.
  - Requests go to **`https://checkout-api.neuralnexus.site/...`**.
  - No CORS errors in the Console.
  - Subscription / usage / invoices sections load.

---

## Reminders

- **The live stack (`.env`, project `portal-live`, `:8200`) is the one the
  tunnel serves.** The test stack (`.env.dev`, project `portal-test`, `:8202`)
  is deliberately not tunnelled — the ingress rule names 8200 only.
- The tunnel needs no change when the stack behind it is rebuilt: it routes to
  host port `:8200` either way, so whichever compose file bound that port is
  what the public hostname serves.
- Switching the server between environments needs **no Vercel redeploy**. The
  banner and the Stripe publishable key both come from `GET /config` at runtime;
  only `VITE_API_BASE_URL` is build-time, and it does not change.
- The Neural Nexus API stays at production `https://api.neuralnexus.site`
  (`NN_API_BASE_URL`) in both environments.
- `USAGE_PERIOD_DAYS` must match that API's own setting (30 in production), or
  the portal's usage bars disagree with the 402 users hit in the chat app.
- The Neural Nexus API needs a Stripe webhook endpoint registered at
  `https://api.neuralnexus.site/stripe/webhook` **per Stripe environment**, with
  its signing secret in that API's `STRIPE_WEBHOOK_SECRET`. Without it the
  endpoint returns 503, and a portal-driven downgrade to free cancels the paid
  subscription without ever creating the replacement free-tier one.
- The portal server must be listening on host `:8200` before the tunnel is
  useful; if the container is down, the hostname returns a Cloudflare 502.
