"""Portal server settings loaded from environment variables.

Every environment variable used by the portal server is declared here and in
``.env.example``. The Stripe live environment and the Stripe test environment
are two env files, one per compose file:

* ``.env`` — live keys, ``PORTAL_ENV=live``, loaded by ``docker-compose.yml``
  (project ``portal-live``, host port 8200, the stack the public reaches).
* ``.env.dev`` — test keys, ``PORTAL_ENV=test``, loaded by
  ``docker-compose.dev.yml`` (project ``portal-test``, host port 8202, local).

Under docker compose the values arrive as real environment variables through
the ``env_file:`` directive, and every env file is excluded from the image by
``.dockerignore``. The ``env_file`` below therefore only applies to running the
server directly on the host (``uvicorn main:app --reload``), and it names
``.env.dev`` on purpose so that such a run defaults to the Stripe TEST
environment rather than billing real customers. Real environment variables take
precedence over it, so pointing a host run at live is an explicit act.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class PortalSettings(BaseSettings):
    # env_ignore_empty: .env files copied from .env.example keep every key with
    # unset values left empty ("PORT="); treat those as "use the default"
    # instead of failing integer parsing at startup.
    model_config = SettingsConfigDict(
        env_file=".env.dev", extra="ignore", env_ignore_empty=True
    )

    # Environment identity -------------------------------------------------
    portal_env: str = "test"  # "test" | "live" — surfaced in the client banner
    dev: str = "FALSE"  # "TRUE" pins the anonymous client ip to the dev value

    # HTTP ------------------------------------------------------------------
    # No `port` field: the Dockerfile runs `uvicorn --port 8080` and each compose
    # file publishes its host port literally, so a settings value would be read
    # by nothing while looking authoritative.
    # 5173 is the Neural Nexus application; this portal's client is 5171
    # (vite.config.ts, the client Dockerfile, and both compose files agree).
    client_origin: str = "http://localhost:5171"  # comma-separated allowlist

    # Session ---------------------------------------------------------------
    session_signing_secret: str = "change-me"
    session_ttl_hours: int = 24

    # Stripe ----------------------------------------------------------------
    stripe_secret_key: str = ""
    stripe_publishable_key: str = ""
    # Optional provisioned-object hints (output of the f-metering
    # provision_stripe_billing.py script). When absent, the portal discovers
    # the catalog from Stripe product/price metadata.
    stripe_billing_config_json: str = ""

    # Auth0 Management API (pay_per_use_enabled lives in app_metadata) -------
    auth0_domain: str = ""
    auth0_client_id: str = ""
    auth0_client_secret: str = ""

    # Usage events pushed by the Neural Nexus API ----------------------------
    # Shared secret authenticating POST /internal/usage-event. Must equal the
    # API's PORTAL_USAGE_EVENT_SECRET exactly or every event is rejected. Empty
    # makes that endpoint refuse everything, and usage falls back to the Stripe
    # read alone — correct, just not immediate.
    usage_event_shared_secret: str = ""

    # Neural Nexus application (the app that embeds this portal) -------------
    # Comma-separated origins the checkout flow may hand the customer back to
    # once Stripe is done. Deliberately NOT client_origin: that list is the CORS
    # allowlist for this portal's own client, and an origin belongs on this one
    # because it is a place to return a person to, not because it may call this
    # API. Anything not listed here is refused, so a hand-crafted
    # `?return_to=` cannot turn a Stripe receipt page into a redirect to an
    # attacker's site.
    app_return_origin: str = "https://neuralnexus.site"

    # Neural Nexus API (email + password auth: login / logout / signup) ------
    nn_api_base_url: str = "https://api.neuralnexus.site"
    # Shared secret for single sign-on out of the Neural Nexus application into
    # this portal. It authenticates this server's call to the Neural Nexus API's
    # /redeem_billing_portal_exchange_code and is the same secret that API signs
    # exchange codes with, so it must equal that API's
    # BILLING_PORTAL_EXCHANGE_SECRET exactly. Empty turns single sign-on off:
    # /auth/single_sign_on refuses, and a customer arriving in the embedded
    # frame sees this portal's ordinary sign-in card.
    nn_exchange_shared_secret: str = ""
    # Must match the Neural Nexus API's USAGE_PERIOD_DAYS. The portal reproduces
    # that API's usage-window arithmetic so the meters shown here cover exactly
    # the window its allotment gating counts against; a mismatch makes the
    # portal disagree with the 402 a user hits in the chat app. Zero (the
    # default on both sides) means calendar-month windows.
    usage_period_days: int = 0

    @property
    def dev_mode_enabled(self) -> bool:
        return str(self.dev).upper() == "TRUE"

    @property
    def client_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.client_origin.split(",") if origin.strip()]

    @property
    def app_return_origin_list(self) -> list[str]:
        return [
            origin.strip().rstrip("/")
            for origin in self.app_return_origin.split(",")
            if origin.strip()
        ]


@lru_cache(maxsize=1)
def get_portal_settings() -> PortalSettings:
    return PortalSettings()
