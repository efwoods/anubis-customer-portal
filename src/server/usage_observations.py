"""Most recent usage pushed by the Neural Nexus API, per customer and meter.

Stripe's meter aggregation is the source of truth for billing, but it does not
reflect an event the instant it happens, so a portal reading only Stripe always
trails the message that just went through. The Neural Nexus API therefore posts
each caller's new cumulative usage to ``/internal/usage-event`` as soon as a turn
is metered, and this module holds that figure so ``GET /usage`` can serve
``max(stripe, observed)`` — the same reconciliation the API itself applies in
``reconcile_period_usage``. Stripe still governs what the customer is billed; the
observation only governs what is shown, and it stops mattering the moment
Stripe's own aggregate catches up and overtakes it.

Deliberately in-process, like the rest of this server's ephemeral state: the
portal runs as a single container, and losing observations on restart is
harmless because the next Stripe read is authoritative anyway.

Observations are only ever used as a FLOOR, and only for the usage period they
were recorded against. An observation whose period does not match the period
being reported is ignored rather than guessed at — falling back to Stripe is
slower but never wrong, which is the correct direction to fail when the number
on screen is what a customer believes they owe.
"""

from __future__ import annotations

import datetime
import time
from collections import OrderedDict

# One entry per (customer, meter) pair. A few thousand covers far more concurrent
# customers than a single-container portal will serve, and the cap only exists so
# a long-running process cannot grow without bound.
_MAX_OBSERVATION_ENTRIES = 4096
# Long enough to bridge Stripe's aggregation delay many times over, short enough
# that a stale figure cannot outlive the period it belongs to.
_OBSERVATION_TTL_SECONDS = 3600.0
# Tolerance when matching an observation's period against the period being
# reported. The API and the portal derive their windows from the same inputs, so
# these normally agree exactly; the tolerance only absorbs clock skew and
# sub-minute rounding between the two derivations.
_PERIOD_START_MATCH_TOLERANCE_SECONDS = 120

_observations: OrderedDict[tuple[str, str], tuple[int, int, float]] = OrderedDict()


def _parse_iso_timestamp_to_epoch(value: str | None) -> int | None:
    if not value:
        return None
    try:
        parsed = datetime.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=datetime.timezone.utc)
    return int(parsed.timestamp())


def record_observation(
    customer_id: str,
    meter_event_name: str,
    cumulative_period_usage: int,
    usage_period_start: str | None,
) -> bool:
    """Store one pushed cumulative reading. Returns whether it was kept.

    A reading is rejected when its period start cannot be parsed, because an
    observation that cannot be matched to a period could otherwise be applied to
    the wrong one and overstate a customer's usage.
    """
    period_start_epoch = _parse_iso_timestamp_to_epoch(usage_period_start)
    if period_start_epoch is None:
        return False

    key = (customer_id, meter_event_name)
    existing = _observations.get(key)
    # Usage within a period only ever grows, so an out-of-order delivery must not
    # walk the displayed figure backwards.
    if existing is not None:
        existing_period_start, existing_usage, _ = existing
        if (
            existing_period_start == period_start_epoch
            and existing_usage > cumulative_period_usage
        ):
            _observations.move_to_end(key)
            return False

    _observations[key] = (
        period_start_epoch,
        max(0, int(cumulative_period_usage)),
        time.monotonic(),
    )
    _observations.move_to_end(key)
    while len(_observations) > _MAX_OBSERVATION_ENTRIES:
        _observations.popitem(last=False)
    return True


def observed_usage(
    customer_id: str | None, meter_event_name: str, period_start_epoch: int
) -> int | None:
    """Return the pushed usage for this customer, meter, and period, if usable."""
    if not customer_id:
        return None
    entry = _observations.get((customer_id, meter_event_name))
    if entry is None:
        return None
    observed_period_start, cumulative_usage, observed_at = entry
    if time.monotonic() - observed_at >= _OBSERVATION_TTL_SECONDS:
        _observations.pop((customer_id, meter_event_name), None)
        return None
    if (
        abs(observed_period_start - period_start_epoch)
        > _PERIOD_START_MATCH_TOLERANCE_SECONDS
    ):
        # Belongs to a different usage period; Stripe is the only safe answer.
        return None
    return cumulative_usage


def clear_observations() -> None:
    """Drop every observation. For tests."""
    _observations.clear()
