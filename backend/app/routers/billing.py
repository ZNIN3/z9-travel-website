from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Header, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.dependencies import AgencyAdministrator, CurrentAgency, DatabaseSession
from app.models import (
    AgencySubscription,
    ProcessedStripeEvent,
    SubscriptionPlan,
)
from app.schemas import (
    BillingPlanRead,
    BillingPortalRead,
    CheckoutSessionCreate,
    CheckoutSessionRead,
)

router = APIRouter(tags=["agency billing"])

PLANS = {
    SubscriptionPlan.BASIC: {
        "monthly_booking_limit": 500,
        "custom_domain": False,
        "stripe_price_id": settings.stripe_basic_price_id,
    },
    SubscriptionPlan.PRO: {
        "monthly_booking_limit": None,
        "custom_domain": True,
        "stripe_price_id": settings.stripe_pro_price_id,
    },
}


@router.get("/api/public/plans/", response_model=list[BillingPlanRead])
def list_plans() -> list[BillingPlanRead]:
    return [
        BillingPlanRead(
            plan=plan,
            monthly_booking_limit=details["monthly_booking_limit"],
            custom_domain=details["custom_domain"],
        )
        for plan, details in PLANS.items()
    ]


@router.post("/api/agency/billing/checkout/", response_model=CheckoutSessionRead)
def create_checkout_session(
    payload: CheckoutSessionCreate,
    agency: CurrentAgency,
    _: AgencyAdministrator,
    db: DatabaseSession,
) -> CheckoutSessionRead:
    plan = payload.plan
    if settings.stripe_secret_key is None or not settings.stripe_secret_key.get_secret_value():
        raise HTTPException(status_code=503, detail="Stripe billing is not configured.")
    price_id = PLANS[plan]["stripe_price_id"]
    if not price_id:
        raise HTTPException(status_code=503, detail=f"The Stripe price for {plan.value} is not configured.")

    subscription = db.scalar(
        select(AgencySubscription).where(AgencySubscription.agency_id == agency.id)
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="Agency subscription not found.")
    if subscription.stripe_subscription_id and subscription.status in {"ACTIVE", "TRIALING"}:
        raise HTTPException(
            status_code=409,
            detail="An active Stripe subscription already exists. Use the billing portal to manage it.",
        )

    stripe.api_key = settings.stripe_secret_key.get_secret_value()
    checkout_params: dict = {
        "mode": "subscription",
        "line_items": [{"price": price_id, "quantity": 1}],
        "success_url": f"https://{agency.custom_domain or f'{agency.subdomain}.{settings.platform_root_domain}'}/dashboard/billing?checkout=success",
        "cancel_url": f"https://{agency.custom_domain or f'{agency.subdomain}.{settings.platform_root_domain}'}/dashboard/billing?checkout=cancelled",
        "client_reference_id": str(agency.id),
        "metadata": {"agency_id": str(agency.id), "plan": plan.value},
        "subscription_data": {"metadata": {"agency_id": str(agency.id), "plan": plan.value}},
    }
    if subscription.stripe_customer_id:
        checkout_params["customer"] = subscription.stripe_customer_id
    try:
        checkout = stripe.checkout.Session.create(**checkout_params)
    except stripe.StripeError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe could not create a checkout session.",
        ) from error

    if not checkout.url:
        raise HTTPException(status_code=502, detail="Stripe returned no checkout URL.")
    return CheckoutSessionRead(checkout_url=checkout.url)


@router.post("/api/agency/billing/portal/", response_model=BillingPortalRead)
def create_billing_portal_session(
    agency: CurrentAgency,
    _: AgencyAdministrator,
    db: DatabaseSession,
) -> BillingPortalRead:
    if settings.stripe_secret_key is None or not settings.stripe_secret_key.get_secret_value():
        raise HTTPException(status_code=503, detail="Stripe billing is not configured.")
    subscription = db.scalar(
        select(AgencySubscription).where(AgencySubscription.agency_id == agency.id)
    )
    if subscription is None or not subscription.stripe_customer_id:
        raise HTTPException(status_code=409, detail="This agency has no Stripe customer account yet.")

    stripe.api_key = settings.stripe_secret_key.get_secret_value()
    return_url = (
        f"https://{agency.custom_domain or f'{agency.subdomain}.{settings.platform_root_domain}'}"
        "/dashboard/billing"
    )
    try:
        portal = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=return_url,
        )
    except stripe.StripeError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Stripe could not create a billing portal session.",
        ) from error
    if not portal.url:
        raise HTTPException(status_code=502, detail="Stripe returned no billing portal URL.")
    return BillingPortalRead(portal_url=portal.url)


def _period_time(timestamp: int | None) -> datetime | None:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc) if timestamp else None


@router.post("/api/webhooks/stripe/", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    db: DatabaseSession,
    stripe_signature: str | None = Header(default=None, alias="Stripe-Signature"),
) -> dict[str, str]:
    if settings.stripe_webhook_secret is None or not settings.stripe_webhook_secret.get_secret_value():
        raise HTTPException(status_code=503, detail="Stripe webhook verification is not configured.")
    if not stripe_signature:
        raise HTTPException(status_code=400, detail="Missing Stripe-Signature header.")

    body = await request.body()
    try:
        event = stripe.Webhook.construct_event(
            body,
            stripe_signature,
            settings.stripe_webhook_secret.get_secret_value(),
        )
    except (ValueError, stripe.SignatureVerificationError) as error:
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature.") from error

    event_id = event["id"]
    if db.get(ProcessedStripeEvent, event_id) is not None:
        return {"status": "already_processed"}

    event_type = event["type"]
    stripe_object = event["data"]["object"]
    metadata = stripe_object.get("metadata") or {}
    subscription = None

    if event_type == "checkout.session.completed":
        agency_id = metadata.get("agency_id") or stripe_object.get("client_reference_id")
        if agency_id is not None:
            subscription = db.scalar(
                select(AgencySubscription).where(AgencySubscription.agency_id == int(agency_id))
            )
        if subscription is not None:
            subscription.stripe_customer_id = stripe_object.get("customer")
            subscription.stripe_subscription_id = stripe_object.get("subscription")
            if metadata.get("plan") in SubscriptionPlan.__members__:
                subscription.plan = SubscriptionPlan[metadata["plan"]]
            payment_status = stripe_object.get("payment_status")
            subscription.status = (
                "ACTIVE" if payment_status in {"paid", "no_payment_required"} else "INCOMPLETE"
            )
    elif event_type in {"customer.subscription.created", "customer.subscription.updated", "customer.subscription.deleted"}:
        stripe_subscription_id = stripe_object.get("id")
        subscription = db.scalar(
            select(AgencySubscription).where(
                AgencySubscription.stripe_subscription_id == stripe_subscription_id
            )
        )
        if subscription is None and metadata.get("agency_id"):
            subscription = db.scalar(
                select(AgencySubscription).where(
                    AgencySubscription.agency_id == int(metadata["agency_id"])
                )
            )
        if subscription is not None:
            subscription.stripe_subscription_id = stripe_subscription_id
            subscription.stripe_customer_id = stripe_object.get("customer")
            if metadata.get("plan") in SubscriptionPlan.__members__:
                subscription.plan = SubscriptionPlan[metadata["plan"]]
            stripe_status = stripe_object.get("status", "canceled").upper()
            subscription.status = "CANCELED" if event_type.endswith(".deleted") else stripe_status
            subscription.current_period_start = _period_time(
                stripe_object.get("current_period_start")
            )
            subscription.current_period_end = _period_time(
                stripe_object.get("current_period_end")
            )
            subscription.cancel_at_period_end = bool(
                stripe_object.get("cancel_at_period_end", False)
            )

    db.add(ProcessedStripeEvent(event_id=event_id))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        if db.get(ProcessedStripeEvent, event_id) is not None:
            return {"status": "already_processed"}
        raise
    return {"status": "processed"}
