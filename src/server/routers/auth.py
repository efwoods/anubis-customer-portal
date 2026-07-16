"""Email one-time-passcode login."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, EmailStr

from email_delivery import send_one_time_passcode_email
from security.session import mint_session_token
from settings import get_portal_settings
from stripe_gateway import customers as stripe_customers

router = APIRouter(prefix="/auth", tags=["Authentication"])


class RequestOneTimePasscodeBody(BaseModel):
    email: EmailStr


class VerifyOneTimePasscodeBody(BaseModel):
    email: EmailStr
    code: str


@router.post("/request_otp", status_code=204)
async def request_one_time_passcode(
    body: RequestOneTimePasscodeBody, request: Request
) -> Response:
    """Send a sign-in code when the email belongs to a Stripe customer.

    Always returns 204 so the endpoint cannot be used to enumerate accounts.
    """
    customer = await stripe_customers.find_customer_by_email(str(body.email))
    if customer is not None:
        code = request.app.state.one_time_passcode_store.issue(
            str(body.email), customer["id"]
        )
        await send_one_time_passcode_email(str(body.email), code)
    return Response(status_code=204)


@router.post("/verify_otp")
async def verify_one_time_passcode(
    body: VerifyOneTimePasscodeBody, request: Request
) -> dict:
    customer_id = request.app.state.one_time_passcode_store.verify(
        str(body.email), body.code.strip()
    )
    if customer_id is None:
        raise HTTPException(
            status_code=401,
            detail="The code is incorrect or has expired. Request a new code.",
        )
    settings = get_portal_settings()
    token = mint_session_token(settings, customer_id, str(body.email))
    return {"token": token, "email": str(body.email), "customer_id": customer_id}


@router.post("/logout", status_code=204)
async def logout() -> Response:
    """Sessions are stateless bearer tokens; the client simply discards its token."""
    return Response(status_code=204)
