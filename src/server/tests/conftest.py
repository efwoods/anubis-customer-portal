"""Test configuration: development-mode environment before the app imports."""

from __future__ import annotations

import os
import sys
from pathlib import Path

SERVER_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SERVER_ROOT))

os.environ.setdefault("PORTAL_ENV", "test")
os.environ.setdefault("DEV", "TRUE")
os.environ.setdefault("SESSION_SIGNING_SECRET", "test-signing-secret")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_placeholder")
os.environ.setdefault("STRIPE_PUBLISHABLE_KEY", "pk_test_placeholder")
# The Neural Nexus gateway is monkeypatched in the flow tests, so this URL is
# never actually dialed; set it for clarity/isolation.
os.environ.setdefault("NN_API_BASE_URL", "https://nn.test")
