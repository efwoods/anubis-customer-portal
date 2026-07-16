"""One-time passcode issuance and verification.

Codes are six digits, stored only as sha256 hashes in a process-local store
with a short time-to-live and a bounded attempt count. The portal server is a
single local container, so process-local storage is sufficient: a restart
simply invalidates outstanding codes and the user requests a new one.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from dataclasses import dataclass


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


@dataclass
class _PendingPasscode:
    hashed_code: str
    customer_id: str
    expires_at_monotonic: float
    attempts_remaining: int


class OneTimePasscodeStore:
    def __init__(self, ttl_seconds: int, max_attempts: int) -> None:
        self._ttl_seconds = ttl_seconds
        self._max_attempts = max_attempts
        self._pending_by_email: dict[str, _PendingPasscode] = {}

    def issue(self, email: str, customer_id: str) -> str:
        """Generate a passcode for this email, replacing any previous one."""
        code = f"{secrets.randbelow(1_000_000):06d}"
        self._pending_by_email[email.lower()] = _PendingPasscode(
            hashed_code=_hash_code(code),
            customer_id=customer_id,
            expires_at_monotonic=time.monotonic() + self._ttl_seconds,
            attempts_remaining=self._max_attempts,
        )
        return code

    def verify(self, email: str, code: str) -> str | None:
        """Return the Stripe customer id when the code is valid, else None.

        A successful verification consumes the passcode. Expired passcodes and
        exhausted attempt budgets remove the pending entry.
        """
        normalized_email = email.lower()
        pending = self._pending_by_email.get(normalized_email)
        if pending is None:
            return None
        if time.monotonic() >= pending.expires_at_monotonic:
            del self._pending_by_email[normalized_email]
            return None
        if not secrets.compare_digest(pending.hashed_code, _hash_code(code)):
            pending.attempts_remaining -= 1
            if pending.attempts_remaining <= 0:
                del self._pending_by_email[normalized_email]
            return None
        del self._pending_by_email[normalized_email]
        return pending.customer_id
