# Portal deploy runbook — Cloudflare tunnel + Vercel client

Connect the local Docker portal server to the public internet and point the
Vercel client at it.

**Target topology**

```
Browser at https://checkout.neuralnexus.site   (Vercel: anubis-customer-portal)
        │  HTTPS + CORS, bearer session token
        ▼
https://checkout-api.neuralnexus.site           (Cloudflare tunnel: neuralnexus-portal)
        ▼
portal-server:8080  (local Docker, host-published on :8200)
        ├──► Stripe
        ├──► Auth0 Management API
        └──► https://api.neuralnexus.site        (login / logout / signup)
```

The repo code/config changes are already committed. The steps below are the
**ops steps** that require the Cloudflare and Vercel accounts.

---

## 1. Create the Cloudflare tunnel

**1a. Open the Tunnels page**
- Go to **dash.cloudflare.com** and log in.
- Left sidebar → **Zero Trust** (may open on a `one.dash.cloudflare.com` URL).
- Zero Trust sidebar → **Networks → Tunnels** (older menus: **Access → Tunnels**).

**1b. Create the tunnel**
- Click **Create a tunnel**.
- Connector type **Cloudflared** → **Next**.
- Name it `neuralnexus-portal` → **Save tunnel**.
- ⚠️ Do **not** touch the existing `neuralnexus-api` tunnel.

**1c. Copy the connector token**
- The "Install and run a connector" screen shows a command containing the token:
  ```
  cloudflared service install eyJhIjoiXXXX...very-long-string...
  ```
- Copy **only** the long `eyJ...` string after `install` (not the whole command).
- You do NOT run this command — the `cloudflared` Docker container uses the token.
- To retrieve it later: tunnel **⋯ → Configure**, or **Refresh token**.

**1d. Add the public hostname**
- On the tunnel's **Public Hostname** tab → **Add a public hostname**:
  - **Subdomain:** `checkout-api`
  - **Domain:** `neuralnexus.site`
  - **Path:** blank
  - **Type:** `HTTP`
  - **URL:** `portal-server:8080`
    - ⚠️ Use `portal-server:8080` (compose service name + container port),
      NOT `localhost:8200`. cloudflared runs inside the compose network.
- **Save hostname.** This auto-creates the proxied DNS record
  `checkout-api.neuralnexus.site → <tunnel-id>.cfargotunnel.com` (record #22
  of 200 — no manual DNS entry needed).

**1e. Paste the token into the env file**
- In `src/server/.env.dev`:
  ```
  TUNNEL_TOKEN=eyJhIjoiXXXX...the-long-string-you-copied...
  ```

---

## 2. Bring the server up

```bash
cd src/server
docker compose up --build
```

Watch the logs:
- ✅ `cloudflared` → `Registered tunnel connection … location=<city>` (~4 connections).
- ❌ `provided Tunnel token is not valid` / `token is empty` → token not pasted
  correctly into `.env.dev`; fix and re-run.
- `portal-server` reports healthy (compose healthcheck hits `/healthz`).

Add `-d` to detach once it's working.

---

## 3. Vercel (anubis-customer-portal project)

**3a. Set the API URL env var**
- vercel.com → **anubis-customer-portal** → **Settings → Environment Variables**.
- Add:
  - **Key:** `VITE_API_BASE_URL`
  - **Value:** `https://checkout-api.neuralnexus.site`
  - **Environments:** **Production** (also **Preview** if desired).
- Save.

**3b. Confirm the client domain**
- **Settings → Domains** → confirm **`checkout.neuralnexus.site`** is **Valid / Active**.
- If missing: **Add** `checkout.neuralnexus.site`, then follow Vercel's DNS
  instruction — a `CNAME` to a `*.vercel-dns.com` target, **DNS-only / not
  proxied** in Cloudflare (so Vercel issues TLS; mirrors the existing `www` record).

**3c. Redeploy (required)**
- Vite inlines `VITE_API_BASE_URL` at **build time**, so the env var alone does
  nothing until a rebuild.
- **Deployments** tab → newest **Production** deploy → **⋯ → Redeploy** →
  uncheck "Use existing Build Cache" → confirm.

---

## 4. Verify end-to-end

**4a. Tunnel reachable**
```bash
curl https://checkout-api.neuralnexus.site/healthz
```
Expect `200`/OK. (`https://checkout-api.neuralnexus.site/reference` should load
the Scalar API docs in a browser.)

**4b. Client → server**
- Open **https://checkout.neuralnexus.site** with DevTools → **Network** open.
- **Sign up** and/or **log in** with email + password.
  - Auth is proxied to `api.neuralnexus.site` (Auth0). **Login only succeeds for
    an email that already has a Stripe customer.**
- Confirm:
  - Requests go to **`https://checkout-api.neuralnexus.site/...`**.
  - **No CORS errors** in the Console. (`CLIENT_ORIGIN` already allows
    `checkout.neuralnexus.site` + the `.vercel.app` URL + localhost.)
  - Subscription / usage / invoices sections load.

---

## Reminders

- `.env.dev` runs **Stripe test mode** with `DEV=TRUE` (anonymous IP pinned to
  the dev value). Good for this integration check — not for real customers.
- **Going live:** create `src/server/.env.live` (gitignored) with the **same**
  `TUNNEL_TOKEN` and `CLIENT_ORIGIN`, plus **live** Stripe keys and `DEV=FALSE`,
  then run:
  ```bash
  COMPOSE_ENV_FILE=.env.live docker compose up --build
  ```
- The Neural Nexus API stays at production `https://api.neuralnexus.site`
  (`NN_API_BASE_URL`) in both environments.
