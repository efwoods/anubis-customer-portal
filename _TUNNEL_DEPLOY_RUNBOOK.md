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
portal-server  (local Docker, host-published :8200 -> container :8080)
        ├──► Stripe
        ├──► Auth0 Management API
        └──► https://api.neuralnexus.site        (login / logout / signup)
```

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

## 2. Bring the server up

```bash
cd src/server
docker compose up --build -d          # portal-server only; no tunnel container
docker compose ps                     # expect: Up (healthy)
curl -s -o /dev/null -w '%{http_code}\n' http://localhost:8200/healthz
```

The compose `cloudflared` service is **not** started by this command — it is
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

**3b. Client domain (only remaining manual step)**
`checkout.neuralnexus.site` does not resolve yet. Until it is configured, the
portal is reachable at the project's `*.vercel.app` URL, which `CLIENT_ORIGIN`
already allows. To add it:
- Vercel → **anubis-customer-portal → Settings → Domains → Add**
  `checkout.neuralnexus.site`.
- Create the `CNAME` Vercel asks for in Cloudflare DNS, target `*.vercel-dns.com`,
  **DNS-only / not proxied** (so Vercel issues TLS; mirrors the existing `www`
  record). Do not use `cloudflared tunnel route dns` for this one — it is a
  Vercel-hosted origin, not a tunnel origin.

**3c. Deploy**
Push to `main`. A rebuild is what picks up `.env.production`, so any change to
that file needs a new deploy (not just a promote/rollback of an old build).

---

## 4. Verify end-to-end

**4a. Tunnel reachable**
```bash
curl -s -o /dev/null -w '%{http_code}\n' https://checkout-api.neuralnexus.site/healthz
```
Expect `200`. (`https://checkout-api.neuralnexus.site/reference` should load the
Scalar API docs in a browser.) Confirm `api.neuralnexus.site` still answers too,
since the restart in 1c affects both.

**4b. Client → server**
- Open the deployed client with DevTools → **Network** open.
- **Sign up** and/or **log in** with email + password.
  - Auth is proxied to `api.neuralnexus.site` (Auth0). **Login only succeeds for
    an email that already has a Stripe customer.**
- Confirm:
  - Requests go to **`https://checkout-api.neuralnexus.site/...`**.
  - **No CORS errors** in the Console. (`CLIENT_ORIGIN` already allows
    `checkout.neuralnexus.site` + the `.vercel.app` URL + `localhost:5171`.)
  - Subscription / usage / invoices sections load.

---

## Reminders

- `.env.dev` runs **Stripe test mode** with `DEV=TRUE` (anonymous IP pinned to
  the dev value). Good for this integration check — not for real customers.
  Note this is now reachable from the public internet, so anyone who finds the
  hostname hits the test-mode portal until you switch to `.env.live`.
- **Going live:** create `src/server/.env.live` (gitignored) with the same
  `CLIENT_ORIGIN` plus **live** Stripe keys and `DEV=FALSE`, then:
  ```bash
  COMPOSE_ENV_FILE=.env.live docker compose up --build -d
  ```
  The tunnel needs no change — it routes to host port `:8200` either way, so
  whichever env file the container was started with is what the public
  hostname serves.
- The Neural Nexus API stays at production `https://api.neuralnexus.site`
  (`NN_API_BASE_URL`) in both environments.
- The portal server must be listening on host `:8200` before the tunnel is
  useful; if the container is down, the hostname returns a Cloudflare 502.
