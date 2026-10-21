from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import false, func, or_, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.dependencies import (
    AgencyAdministrator,
    CurrentAgency,
    DatabaseSession,
    PlatformAdministrator,
)
from app.models import (
    Agency,
    AgencySubscription,
    Booking,
    Bus,
    Flight,
    Hotel,
    SubscriptionPlan,
    User,
    UserRole,
)
from app.schemas import (
    AgencyBrand,
    AgencyBrandUpdate,
    AgencyCreate,
    AgencyDashboardRead,
    AgencySubscriptionRead,
    BusCreate,
    BusRead,
    FlightCreate,
    FlightRead,
    HotelCreate,
    HotelRead,
    PlatformSubscriptionRead,
)
from app.security import hash_password

router = APIRouter(tags=["agencies"])


@router.get("/api/public/agency/", response_model=AgencyBrand)
def get_storefront_brand(agency: CurrentAgency) -> Agency:
    return agency


@router.post(
    "/api/platform/agencies/",
    response_model=AgencyBrand,
    status_code=status.HTTP_201_CREATED,
)
def create_agency(
    payload: AgencyCreate,
    _: PlatformAdministrator,
    db: DatabaseSession,
) -> Agency:
    requested_subdomain = payload.subdomain.lower()
    conflicting_domain = db.scalar(
        select(Agency.id).where(
            (Agency.subdomain == requested_subdomain)
            | (
                Agency.custom_domain
                == f"{requested_subdomain}.{settings.platform_root_domain}"
            )
        )
    )
    if conflicting_domain is not None:
        raise HTTPException(status_code=409, detail="The subdomain or storefront hostname is already in use.")

    agency = Agency(
        name=payload.name.strip(),
        subdomain=requested_subdomain,
        logo_url=payload.logo_url,
        primary_color=payload.primary_color.upper(),
        secondary_color=payload.secondary_color.upper(),
    )
    db.add(agency)
    try:
        db.flush()
        db.add(
            AgencySubscription(
                agency_id=agency.id,
                plan=SubscriptionPlan.BASIC,
                status="TRIALING",
            )
        )
        db.add(
            User(
                agency_id=agency.id,
                name=payload.admin_name.strip(),
                email=str(payload.admin_email).lower(),
                password_hash=hash_password(payload.admin_password),
                role=UserRole.AGENCY_ADMIN,
            )
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The subdomain or agency administrator email is already in use.",
        ) from None
    db.refresh(agency)
    return agency


@router.get("/api/platform/agencies/", response_model=list[AgencyBrand])
def list_agencies(
    _: PlatformAdministrator, db: DatabaseSession
) -> list[Agency]:
    return list(db.scalars(select(Agency).order_by(Agency.name)).all())


@router.get(
    "/api/platform/subscriptions/",
    response_model=list[PlatformSubscriptionRead],
)
def list_platform_subscriptions(
    _: PlatformAdministrator, db: DatabaseSession
) -> list[PlatformSubscriptionRead]:
    rows = db.execute(
        select(Agency, AgencySubscription)
        .join(AgencySubscription, AgencySubscription.agency_id == Agency.id)
        .order_by(Agency.name)
    ).all()
    return [
        PlatformSubscriptionRead(
            agency_id=agency.id,
            agency_name=agency.name,
            subdomain=agency.subdomain,
            plan=subscription.plan,
            status=subscription.status,
            stripe_customer_id=subscription.stripe_customer_id,
            stripe_subscription_id=subscription.stripe_subscription_id,
            current_period_start=subscription.current_period_start,
            current_period_end=subscription.current_period_end,
            cancel_at_period_end=subscription.cancel_at_period_end,
        )
        for agency, subscription in rows
    ]


@router.get("/api/agency/dashboard/", response_model=AgencyDashboardRead)
def get_agency_dashboard(
    agency: CurrentAgency,
    current_user: AgencyAdministrator,
    db: DatabaseSession,
) -> AgencyDashboardRead:
    subscription = db.scalar(
        select(AgencySubscription).where(AgencySubscription.agency_id == agency.id)
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="Agency subscription not found.")
    period_start = subscription.current_period_start or datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    bookings_count = db.scalar(
        select(func.count(Booking.id)).where(
            Booking.agency_id == agency.id,
            Booking.created_at >= period_start,
        )
    )
    return AgencyDashboardRead(
        agency=AgencyBrand.model_validate(agency),
        subscription=AgencySubscriptionRead.model_validate(subscription),
        bookings_this_period=bookings_count or 0,
        monthly_booking_limit=500 if subscription.plan is SubscriptionPlan.BASIC else None,
    )


@router.patch("/api/agency/brand/", response_model=AgencyBrand)
def update_agency_brand(
    payload: AgencyBrandUpdate,
    agency: CurrentAgency,
    _: AgencyAdministrator,
    db: DatabaseSession,
) -> Agency:
    updates = payload.model_dump(exclude_unset=True)
    if "custom_domain" in updates and updates["custom_domain"]:
        subscription = db.scalar(
            select(AgencySubscription).where(AgencySubscription.agency_id == agency.id)
        )
        if subscription is None or subscription.plan is not SubscriptionPlan.PRO:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Custom domains are available on the Pro plan.",
            )
        domain = updates["custom_domain"].strip().lower().rstrip(".")
        if "://" in domain or "/" in domain or ":" in domain:
            raise HTTPException(status_code=422, detail="Enter a hostname without a scheme or path.")
        subdomain_match = (
            domain[: -(len(settings.platform_root_domain) + 1)]
            if domain.endswith(f".{settings.platform_root_domain}")
            else None
        )
        conflicting_domain = db.scalar(
            select(Agency.id).where(
                Agency.id != agency.id,
                or_(
                    Agency.custom_domain == domain,
                    Agency.subdomain == subdomain_match if subdomain_match else false(),
                ),
            )
        )
        if conflicting_domain is not None:
            raise HTTPException(status_code=409, detail="This hostname is already assigned to another agency.")
        updates["custom_domain"] = domain

    for field, value in updates.items():
        if field in {"primary_color", "secondary_color"} and value is not None:
            value = value.upper()
        setattr(agency, field, value)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="This custom domain is already assigned.") from None
    db.refresh(agency)
    return agency


@router.post("/api/agency/inventory/flights/", response_model=FlightRead, status_code=201)
def create_flight(
    payload: FlightCreate,
    agency: CurrentAgency,
    _: AgencyAdministrator,
    db: DatabaseSession,
) -> Flight:
    flight = Flight(agency_id=agency.id, **payload.model_dump())
    db.add(flight)
    db.commit()
    db.refresh(flight)
    return flight


@router.post("/api/agency/inventory/hotels/", response_model=HotelRead, status_code=201)
def create_hotel(
    payload: HotelCreate,
    agency: CurrentAgency,
    _: AgencyAdministrator,
    db: DatabaseSession,
) -> Hotel:
    hotel = Hotel(agency_id=agency.id, **payload.model_dump())
    db.add(hotel)
    db.commit()
    db.refresh(hotel)
    return hotel


@router.post("/api/agency/inventory/buses/", response_model=BusRead, status_code=201)
def create_bus(
    payload: BusCreate,
    agency: CurrentAgency,
    _: AgencyAdministrator,
    db: DatabaseSession,
) -> Bus:
    bus = Bus(agency_id=agency.id, **payload.model_dump())
    db.add(bus)
    db.commit()
    db.refresh(bus)
    return bus
