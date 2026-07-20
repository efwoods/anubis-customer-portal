"""Portal server settings loaded from environment variables.

Every environment variable used by the portal server is declared here and in
``.env.example``. Switching between the Stripe test environment and the Stripe
live environment is a matter of pointing docker compose at a different env
file (``.env`` versus ``.env.live``).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class PortalSettings(BaseSettings):
    # env_ignore_empty: .env files copied from .env.example keep every key with
    # unset values left empty ("PORT="); treat those as "use the default"
    # instead of failing integer parsing at startup.
    model_config = SettingsConfigDict(
        env_file=".env", extra="ignore", env_ignore_empty=True
    )

    # Environment identity -------------------------------------------------
    portal_env: str = "test"  # "test" | "live" — surfaced in the client banner
    dev: str = "FALSE"  # "TRUE" pins the anonymous client ip to the dev value

    # HTTP ------------------------------------------------------------------
    port: int = 8080
    client_origin: str = "http://localhost:5173"  # comma-separated allowlist

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

    # Neural Nexus API (email + password auth: login / logout / signup) ------
    nn_api_base_url: str = "https://api.neuralnexus.site"

    @property
    def dev_mode_enabled(self) -> bool:
        return str(self.dev).upper() == "TRUE"

    @property
    def client_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.client_origin.split(",") if origin.strip()]


@lru_cache(maxsize=1)
def get_portal_settings() -> PortalSettings:
    return PortalSettings()
