"""Immediate usage: ingest pushes from the Neural Nexus API, stream them out.

``GET /usage`` reads Stripe, which is authoritative for billing but does not
reflect a meter event the instant it happens. So the Neural Nexus API posts each
caller's new cumulative usage here the moment a turn is metered, and an open
portal page receives it over server-sent events and moves its meters right away.
``routers/usage.py`` folds the same figure in as a floor, so a page load or a
reconnect is just as current as a live stream.

Three routes:

* ``POST /internal/usage-event`` — machine-to-machine, authenticated by an HMAC
  shared with the Neural Nexus API. Never called by a browser.
* ``POST /usage/stream-ticket`` — exchanges the caller's normal credentials for a
  short-lived ticket, because ``EventSource`` cannot send an Authorization
  header (see ``security/session.py``).
* ``GET /usage/stream`` — the event stream itself, scoped to one customer.

Anonymous visitors need no ticket: they are resolved by hashed client ip like
everywhere else in this server, so their stream works with no credential at all.
"""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import time

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

import usage_observations
from security.identity import CustomerIdentity, resolve_customer_identity
from security.session import decode_usage_stream_ticket, mint_usage_stream_ticket
from settings import PortalSettings, get_portal_settings
from usage_event_signature import (
    SIGNATURE_HEADER_NAME,
    TIMESTAMP_HEADER_NAME,
    build_usage_event_signature,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Usage"])

# How far a usage event's timestamp may be from now. Bounds replay of a captured
# request without being so tight that ordinary clock drift rejects real events.
_MAXIMUM_EVENT_AGE_SECONDS = 300

# Bounded so a subscriber that stops reading (a laptop asleep with the tab open)
# cannot grow a queue without limit; the oldest pending frame is dropped instead,
# which is harmless because every frame carries the full cumulative figure rather
# than a delta.
_SUBSCRIBER_QUEUE_MAXIMUM_SIZE = 16
_KEEPALIVE_INTERVAL_SECONDS = 25.0

_subscribers_by_customer_id: dict[str, set[asyncio.Queue]] = {}


def _publish_to_subscribers(customer_id: str, event_document: dict) -> None:
    for queue in list(_subscribers_by_customer_id.get(customer_id, ())):
        if queue.full():
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        try:
            queue.put_nowait(event_document)
        except asyncio.QueueFull:
            pass


def _verify_usage_event_signature(
    settings: PortalSettings, raw_body: bytes, timestamp: str | None, signature: str | None
) -> None:
    shared_secret = (settings.usage_event_shared_secret or "").strip()
    if not shared_secret:
        # Refuse rather than accept unauthenticated writes: this endpoint changes
        # what a customer is told about their own spending.
        raise HTTPException(
            status_code=503, detail="Usage event ingestion is not configured."
        )
    if not timestamp or not signature:
        raise HTTPException(status_code=401, detail="Missing usage event signature.")
    try:
        event_age_seconds = abs(int(time.time()) - int(timestamp))
    except ValueError:
        raise HTTPException(status_code=401, detail="Malformed usage event timestamp.")
    if event_age_seconds > _MAXIMUM_EVENT_AGE_SECONDS:
        raise HTTPException(status_code=401, detail="Usage event timestamp is too old.")
    expected_signature = build_usage_event_signature(shared_secret, timestamp, raw_body)
    # Constant-time comparison so a mismatched signature cannot be discovered
    # byte by byte from response timing.
    if not hmac.compare_digest(expected_signature, signature):
        raise HTTPException(status_code=401, detail="Invalid usage event signature.")


@router.post("/internal/usage-event", include_in_schema=False)
async def ingest_usage_event(
    request: Request, settings: PortalSettings = Depends(get_portal_settings)
) -> dict:
    """Record a usage figure pushed by the Neural Nexus API and fan it out.

    The value is cumulative for the period, not a delta, so a duplicate or
    retried delivery is harmless.
    """
    raw_body = await request.body()
    _verify_usage_event_signature(
        settings,
        raw_body,
        request.headers.get(TIMESTAMP_HEADER_NAME),
        request.headers.get(SIGNATURE_HEADER_NAME),
    )

    try:
        event_document = json.loads(raw_body)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Usage event body is not JSON.")

    customer_id = event_document.get("stripe_customer_id")
    meter_event_name = event_document.get("meter_event_name")
    cumulative_period_usage = event_document.get("cumulative_period_usage")
    if not customer_id or not meter_event_name or cumulative_period_usage is None:
        raise HTTPException(status_code=400, detail="Usage event is missing fields.")

    recorded = usage_observations.record_observation(
        customer_id,
        meter_event_name,
        int(cumulative_period_usage),
        event_document.get("usage_period_start"),
    )
    if recorded:
        _publish_to_subscribers(
            customer_id,
            {
                "meter_event_name": meter_event_name,
                "used_to_date": int(cumulative_period_usage),
                "usage_period_start": event_document.get("usage_period_start"),
                "usage_period_end": event_document.get("usage_period_end"),
            },
        )
    return {"recorded": recorded}


@router.post("/usage/stream-ticket")
async def create_usage_stream_ticket(
    identity: CustomerIdentity = Depends(resolve_customer_identity),
    settings: PortalSettings = Depends(get_portal_settings),
) -> dict:
    """Exchange normal credentials for a short-lived usage-stream ticket."""
    if not identity.customer_id:
        raise HTTPException(
            status_code=404, detail="No billing record found for this visitor."
        )
    return {
        "ticket": mint_usage_stream_ticket(settings, identity.customer_id),
        "customer_id": identity.customer_id,
    }


@router.get("/usage/stream")
async def stream_usage(
    request: Request,
    ticket: str | None = None,
    identity: CustomerIdentity = Depends(resolve_customer_identity),
    settings: PortalSettings = Depends(get_portal_settings),
) -> StreamingResponse:
    """Server-sent events carrying this customer's usage as it changes.

    A verified caller presents a ticket (``EventSource`` cannot send an
    Authorization header). An anonymous visitor presents nothing and is resolved
    by hashed client ip, exactly as on every other route.
    """
    customer_id: str | None = None
    if ticket:
        customer_id = decode_usage_stream_ticket(settings, ticket)
        if customer_id is None:
            raise HTTPException(
                status_code=401, detail="Stream ticket is invalid or expired."
            )
    else:
        # No ticket: only an anonymous visitor may open a stream this way, so a
        # session token in a query string is never an accepted substitute.
        if identity.is_verified:
            raise HTTPException(
                status_code=401, detail="A stream ticket is required for this account."
            )
        customer_id = identity.customer_id

    if not customer_id:
        raise HTTPException(
            status_code=404, detail="No billing record found for this visitor."
        )

    subscriber_queue: asyncio.Queue = asyncio.Queue(
        maxsize=_SUBSCRIBER_QUEUE_MAXIMUM_SIZE
    )
    _subscribers_by_customer_id.setdefault(customer_id, set()).add(subscriber_queue)

    async def event_publisher():
        try:
            # Tell the client the stream is live before anything is metered, so a
            # failure to connect is distinguishable from an idle stream.
            yield "event: ready\ndata: {}\n\n"
            while True:
                if await request.is_disconnected():
                    return
                try:
                    event_document = await asyncio.wait_for(
                        subscriber_queue.get(), timeout=_KEEPALIVE_INTERVAL_SECONDS
                    )
                except asyncio.TimeoutError:
                    # A comment frame keeps intermediaries (the Cloudflare tunnel
                    # among them) from closing an idle connection.
                    yield ": keepalive\n\n"
                    continue
                yield f"event: usage\ndata: {json.dumps(event_document)}\n\n"
        finally:
            subscribers = _subscribers_by_customer_id.get(customer_id)
            if subscribers is not None:
                subscribers.discard(subscriber_queue)
                if not subscribers:
                    _subscribers_by_customer_id.pop(customer_id, None)

    return StreamingResponse(
        event_publisher(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Defeats proxy buffering, which would otherwise hold frames back and
            # defeat the entire point of streaming.
            "X-Accel-Buffering": "no",
        },
    )
