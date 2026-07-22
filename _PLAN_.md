# Deploy: Cloudflare tunnel for the portal server + wire the Vercel client to it

## Context

The Neural Nexus customer portal is ready to go live for integration testing.
It has two halves that must be connected across the public internet:

- **Client** — React/Vite app on Vercel (project `anubis-customer-portal`),
  served on the custom domain **`checkout.neuralnexus.site`** (this is the
  origin users navigate to and the browser makes API calls from).
- **Server** — FastAPI backend-for-frontend running in **local Docker**
  (`src/server/docker-compose.yml`; host port `8200` → container `8080`),
  which mutates Stripe/Auth0 and proxies email+password auth to the Neural
  Nexus API.

The browser cannot call a `localhost` server, so the portal server must be
exposed to the public internet through a **Cloudflare Tunnel**. Decisions
confirmed with the user:

- Server tunnel hostname: **`checkout-api.neuralnexus.site`** (new tunnel;
  distinct from the existing `api.neuralnexus.site` → `neuralnexus-api` tunnel,
  which fronts the separate Neural Nexus API).
- Client (`checkout.neuralnexus.site`) sets `VITE_API_BASE_URL` to that server
  tunnel hostname.
- The server's upstream Neural Nexus API stays at production
  **`https://api.neuralnexus.site`** — the earlier `localhost:8123` interim step
  is dropped. This is already the value in `src/server/.env.dev`, so **no change
  to `NN_API_BASE_URL`**.

Intended outcome: `https://checkout.neuralnexus.site` (browser) →
`https://checkout-api.neuralnexus.site` (tunnel) → local Docker portal server →
Stripe / Auth0 / `https://api.neuralnexus.site`, with CORS allowing the client
origin.

**No Python code changes are required** — CORS and the upstream URL are already
env-driven (`main.py` reads `client_origin_list`; `neural_nexus_gateway.py`
reads `nn_api_base_url`). The work is compose + env + Cloudflare + Vercel config.

## Changes

### 1. Fix the `cloudflared` token wiring in `src/server/docker-compose.yml`

Current gotcha: the `cloudflared` service has no `env_file`, so
`${CLOUDFLARE_TUNNEL_TOKEN}` in its `command:` is interpolated from the compose
**project** env (root `.env`/shell), **not** from `portal-server`'s `.env.dev`
— the token silently ends up empty. Also the compose file hardcodes
`env_file: .env.dev`, which defeats the documented test/live switch
(`docker compose --env-file .env.live up`), and `COMPOSE_ENV_FILE` (already
declared in `.env.example`) is meant to drive exactly that.

Fix both at once by using cloudflared's **native `TUNNEL_TOKEN` env var** (read
automatically when no `--token` flag is passed) and parameterizing `env_file`:

```yaml
services:
  portal-server:
    build: .
    env_file:
      - ${COMPOSE_ENV_FILE:-.env.dev}
    ports:
      - "${PORT:-8200}:8080"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')"]
      interval: 30s
      timeout: 5s
      retries: 3

  cloudflared:
    image: cloudflare/cloudflared:latest
    env_file:
      - ${COMPOSE_ENV_FILE:-.env.dev}
    command: tunnel --no-autoupdate run
    restart: unless-stopped
    depends_on:
      - portal-server
```

- `cloudflared` reaches the server over the compose network at
  `http://portal-server:8080` (the ingress target configured in Cloudflare,
  step 4) — no host port needed.
- No `extra_hosts` / `host.docker.internal` is needed: the upstream Neural
  Nexus API is reached over the public internet at `api.neuralnexus.site`.

### 2. Rename the tunnel-token env var to `TUNNEL_TOKEN`

Across `src/server/.env.example`, `src/server/.env.dev`, and
`src/server/.env.live` (live is gitignored; create/update it too), rename
`CLOUDFLARE_TUNNEL_TOKEN` → `TUNNEL_TOKEN` (the name cloudflared reads
natively). Set its value in `.env.dev`/`.env.live` to the connector token from
step 3; leave it blank in `.env.example`.

### 3. Set `CLIENT_ORIGIN` (CORS) for the production client

In `src/server/.env.dev` (the file the container reads), change:

```
CLIENT_ORIGIN=http://localhost:5171
```
to include the production client origin(s) and keep the local dev origin:
```
CLIENT_ORIGIN=https://checkout.neuralnexus.site,https://anubis-customer-portal.vercel.app,http://localhost:5171
```
(`client_origin_list` in `settings.py` splits on commas; `main.py` feeds it to
`CORSMiddleware`.) Mirror this in `.env.live` and update the comment in
`.env.example`. `NN_API_BASE_URL` stays `https://api.neuralnexus.site`.

### 4. Create the Cloudflare tunnel + public hostname (Cloudflare dashboard / CLI — user's account)

Zero Trust → Networks → Tunnels:
1. Create a new tunnel, e.g. `neuralnexus-portal` (leave the existing
   `neuralnexus-api` tunnel untouched). Copy its **connector token** → paste as
   `TUNNEL_TOKEN` in `.env.dev` (step 2).
2. Add a **public hostname**: subdomain `checkout-api`, domain
   `neuralnexus.site`, service **`http://portal-server:8080`**. This auto-creates
   the proxied `CNAME checkout-api.neuralnexus.site → <tunnel-id>.cfargotunnel.com`
   DNS record (record #22 of 200).

### 5. Vercel client config

1. In the Vercel `anubis-customer-portal` project, set env var
   **`VITE_API_BASE_URL=https://checkout-api.neuralnexus.site`** (Production;
   add to Preview if preview builds should hit it too). Vite inlines this at
   **build time**, so a redeploy is required after setting it.
2. Confirm the custom domain **`checkout.neuralnexus.site`** is attached to the
   project (add it + the Vercel DNS/verification record if not — mirrors the
   existing `www.neuralnexus.site → *.vercel-dns-017.com` CNAME, DNS-only so
   Vercel issues TLS). User indicated it already serves there.
3. Trigger a fresh production deploy so the new `VITE_API_BASE_URL` is baked in.

### 6. Stop shipping the stale committed build (cleanup)

`src/client/dist/` is committed with `http://localhost:8200` inlined into
`dist/assets/index-*.js`. Vercel builds from source (`vercel.json` →
`framework: vite`), so it ignores `dist/`, but the stale bundle is a footgun.
Add `dist/` to `src/client/.gitignore` and remove it from the repo. Update the
`src/client/.env.example` comment to show the tunnel hostname as the production
example.

## Files to modify

- `src/server/docker-compose.yml` — cloudflared `env_file` + native
  `TUNNEL_TOKEN` command; parameterize both services' `env_file` via
  `${COMPOSE_ENV_FILE:-.env.dev}`.
- `src/server/.env.example` — rename token var → `TUNNEL_TOKEN`; update
  `CLIENT_ORIGIN` comment.
- `src/server/.env.dev` — `TUNNEL_TOKEN=<token>`; `CLIENT_ORIGIN=` the three
  origins above. (`NN_API_BASE_URL` unchanged.)
- `src/server/.env.live` — same two vars for live (gitignored).
- `src/client/.env.example` — production example = tunnel hostname.
- `src/client/.gitignore` (+ remove `src/client/dist/`).
- Cloudflare dashboard (tunnel + hostname) and Vercel dashboard (env var +
  domain + redeploy) — user-driven ops steps, not repo edits.

## Considerations

- **Auth model**: login/signup are **email + password**, proxied to the Neural
  Nexus API (`neural_nexus_gateway.py` → Auth0); there is no one-time-passcode
  flow (the `CLAUDE.md` / `.env` comments mentioning OTP/SMTP are stale). A
  `/auth/login` only succeeds for an email that already has a **Stripe
  customer** (`find_customer_by_email`), so it depends on both
  `api.neuralnexus.site` being reachable and a matching Stripe customer.
- **`DEV=TRUE` in `.env.dev`**: pins the anonymous client IP to `172.18.0.1`
  (so anonymous users resolve the f-metering dev anonymous customer). Fine for
  an integration check; for a public deployment that resolves real anonymous
  users by hashed IP, run with `DEV=FALSE` via `.env.live` / a production env
  file.
- **Test vs live Stripe**: `.env.dev` carries **test** Stripe keys, so the live
  tunnel initially runs in Stripe **test** mode. Switch to `.env.live` (real
  keys, `PORTAL_ENV=live`, `DEV=FALSE`) via
  `COMPOSE_ENV_FILE=.env.live docker compose up` when going truly live.
- **Committed secrets**: `.env.dev` commits real test Stripe/Auth0/SMTP
  credentials. Out of scope here, but worth rotating + gitignoring later.

## Verification

1. **Tunnel up**: `cd src/server && docker compose up --build`. Confirm the
   `cloudflared` logs show a registered connection (no "token is empty" error)
   and `portal-server` is healthy.
2. **Public reachability**: `curl https://checkout-api.neuralnexus.site/healthz`
   returns OK; `https://checkout-api.neuralnexus.site/reference` (Scalar) loads.
3. **End-to-end from the client**: open `https://checkout.neuralnexus.site`,
   sign up and/or log in with **email + password** (an existing Stripe-customer
   email for login to succeed), and load the subscription/usage/invoices
   sections. In devtools, confirm requests go to
   `https://checkout-api.neuralnexus.site` with **no CORS errors** and no 401
   loops.
4. **Upstream auth**: the `/auth/login` and `/auth/signup` calls confirm the
   server reaches `https://api.neuralnexus.site` (Auth0) successfully.
5. **Server tests unaffected**: `cd src/server && .venv/bin/python -m pytest`.
