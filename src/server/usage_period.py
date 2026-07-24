"""The usage window the Neural Nexus API counts allotment against, reproduced.

The portal shows usage meters; the Neural Nexus API decides when to refuse a
request with HTTP 402. If the two measure different spans of time they disagree
in the way that matters most — a customer sees remaining budget in the portal
while the chat app refuses them, or the reverse. This module is a faithful port
of that API's ``resolve_usage_period_start`` /
``resolve_usage_period_start_for_user`` (``src/anubis/utils/billing/metering.py``
and ``src/api/webapp.py``) so both sides answer the same question the same way.

The inputs, in the order they take precedence:

1. ``usage_period_anchor`` — an ISO-8601 UTC instant in Auth0 app_metadata,
   written by the Neural Nexus API whenever the local usage window restarts (a
   tier upgrade, the first checkout, a mid-period cancellation). Expanded into a
   recurring window per ``usage_period_days``.
2. The Stripe billing period start, which wins when it is LATER than the
   anchor-derived start — a fresh billing period always restarts the count.
3. The plain configured period when there is no anchor at all: calendar month
   when ``usage_period_days`` is zero, otherwise fixed-length windows counted
   from a fixed global instant.
"""

from __future__ import annotations

import calendar
import datetime

# The Neural Nexus API's GLOBAL_USAGE_PERIOD_ANCHOR. Fixed-length windows are
# counted from this instant so every process agrees on the boundaries; it must
# stay identical on both sides.
GLOBAL_USAGE_PERIOD_ANCHOR = datetime.datetime(
    2025, 1, 1, tzinfo=datetime.timezone.utc
)


def _parse_anchor(usage_period_anchor: str | None) -> datetime.datetime | None:
    """Parse the stored anchor defensively; malformed values yield ``None``."""
    if not usage_period_anchor:
        return None
    try:
        anchor = datetime.datetime.fromisoformat(
            usage_period_anchor.replace("Z", "+00:00")
        )
    except ValueError:
        return None
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=datetime.timezone.utc)
    return anchor.astimezone(datetime.timezone.utc)


def _monthly_boundary_for(
    year: int, month: int, anchor: datetime.datetime
) -> datetime.datetime:
    """The anchor's monthly boundary inside (year, month).

    Keeps the anchor's day-of-month and time-of-day, clamping the day to the
    target month's length — an anchor on January 31 yields February 28 or 29,
    the same clamping Stripe applies to ``billing_cycle_anchor``.
    """
    last_day_of_month = calendar.monthrange(year, month)[1]
    return anchor.replace(
        year=year, month=month, day=min(anchor.day, last_day_of_month)
    )


def resolve_usage_period_start(
    now: datetime.datetime,
    usage_period_days: int,
    period_anchor: datetime.datetime | None,
) -> datetime.datetime:
    """The start of the usage period containing ``now``."""
    if period_anchor is not None and period_anchor > now:
        # A future anchor should not happen; treat it as the period start rather
        # than producing a window that has not begun.
        return period_anchor

    if usage_period_days > 0:
        anchor = period_anchor or GLOBAL_USAGE_PERIOD_ANCHOR
        period_length = datetime.timedelta(days=usage_period_days)
        elapsed_periods = (now - anchor) // period_length
        return anchor + elapsed_periods * period_length

    if period_anchor is None:
        return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    boundary_this_month = _monthly_boundary_for(now.year, now.month, period_anchor)
    if boundary_this_month <= now:
        period_start = boundary_this_month
    else:
        previous_month_year = now.year if now.month > 1 else now.year - 1
        previous_month = now.month - 1 if now.month > 1 else 12
        period_start = _monthly_boundary_for(
            previous_month_year, previous_month, period_anchor
        )
    # The first period begins at the anchor itself, never before.
    return max(period_start, period_anchor)


def resolve_usage_period_end(
    period_start: datetime.datetime, usage_period_days: int
) -> datetime.datetime:
    """The exclusive end of the period beginning at ``period_start``."""
    if usage_period_days > 0:
        return period_start + datetime.timedelta(days=usage_period_days)
    next_month_year = (
        period_start.year if period_start.month < 12 else period_start.year + 1
    )
    next_month = period_start.month + 1 if period_start.month < 12 else 1
    return _monthly_boundary_for(next_month_year, next_month, period_start)


def resolve_usage_period_bounds(
    usage_period_days: int,
    usage_period_anchor: str | None,
    stripe_period_start: int | None,
    stripe_period_end: int | None,
    now: datetime.datetime | None = None,
) -> tuple[int, int]:
    """Return ``(start, end)`` epoch seconds for the window to report usage over.

    Mirrors the Neural Nexus API: the anchor-derived start and the Stripe
    billing-period start are combined by taking the LATER of the two (a new
    billing period always restarts the count), and the Stripe period end is
    preferred for the end when present.
    """
    now = now or datetime.datetime.now(datetime.timezone.utc)
    period_start = resolve_usage_period_start(
        now, usage_period_days, _parse_anchor(usage_period_anchor)
    )
    if stripe_period_start:
        try:
            period_start = max(
                period_start,
                datetime.datetime.fromtimestamp(
                    int(stripe_period_start), tz=datetime.timezone.utc
                ),
            )
        except (TypeError, ValueError, OSError):
            pass

    if stripe_period_end:
        try:
            period_end = datetime.datetime.fromtimestamp(
                int(stripe_period_end), tz=datetime.timezone.utc
            )
        except (TypeError, ValueError, OSError):
            period_end = resolve_usage_period_end(period_start, usage_period_days)
    else:
        period_end = resolve_usage_period_end(period_start, usage_period_days)

    return int(period_start.timestamp()), int(period_end.timestamp())
