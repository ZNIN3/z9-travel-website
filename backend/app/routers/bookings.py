from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.dependencies import AgencyAdministrator, CurrentAgency, DatabaseSession, TenantCustomer
from app.models import (
    Agency,
    AgencySubscription,
    Booking,
    BookingItemType,
    BookingStatus,
    Bus,
    Flight,
    Hotel,
    SubscriptionPlan,
)
from app.schemas import BookingCreate, BookingRead

router = APIRouter(tags=["bookings"])


@router.post("/api/bookings/create/", response_model=BookingRead, status_code=status.HTTP_201_CREATED)
def create_booking(
    payload: BookingCreate,
    agency: CurrentAgency,
    current_user: TenantCustomer,
    db: DatabaseSession,
) -> Booking:
    # Serialize each tenant's quota check and inventory reservation within one transaction.
    locked_agency = db.scalar(
        select(Agency).where(Agency.id == agency.id).with_for_update()
    )
    subscription = db.scalar(
        select(AgencySubscription)
        .where(AgencySubscription.agency_id == agency.id)
        .with_for_update()
    )
    if locked_agency is None or subscription is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Agency subscription is unavailable.")
    if subscription.status not in {"ACTIVE", "TRIALING"}:
        raise HTTPException(status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Agency subscription is not active.")

    period_start = subscription.current_period_start or datetime.now(timezone.utc).replace(
        day=1, hour=0, minute=0, second=0, microsecond=0
    )
    monthly_limit = 500 if subscription.plan is SubscriptionPlan.BASIC else None
    if monthly_limit is not None:
        booking_count = db.scalar(
            select(func.count(Booking.id)).where(
                Booking.agency_id == agency.id,
                Booking.created_at >= period_start,
            )
        )
        if booking_count is not None and booking_count >= monthly_limit:
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail="This agency has reached its monthly booking limit. Upgrade the subscription to continue.",
            )

    # Polymorphic item_id cannot have a regular foreign key; lock the selected
    # table's row before changing inventory.
    if payload.item_type is BookingItemType.FLIGHT:
        flight = db.scalar(
            select(Flight)
            .where(Flight.id == payload.item_id, Flight.agency_id == agency.id)
            .with_for_update()
        )
        if flight is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Flight not found.")
        if flight.available_seats < payload.quantity:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Not enough seats are available.")
        flight.available_seats -= payload.quantity
        unit_price = flight.price
    elif payload.item_type is BookingItemType.HOTEL:
        hotel = db.scalar(
            select(Hotel)
            .where(Hotel.id == payload.item_id, Hotel.agency_id == agency.id)
            .with_for_update()
        )
        if hotel is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Hotel not found.")
        if hotel.available_rooms < payload.quantity:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Not enough rooms are available.")
        hotel.available_rooms -= payload.quantity
        if payload.check_in is None or payload.check_out is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Hotel bookings require check-in and check-out dates.",
            )
        nights = (payload.check_out - payload.check_in).days
        unit_price = hotel.price_per_night * nights
    else:
        bus = db.scalar(
            select(Bus)
            .where(Bus.id == payload.item_id, Bus.agency_id == agency.id)
            .with_for_update()
        )
        if bus is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Bus not found.")
        if bus.available_seats < payload.quantity:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Not enough seats are available.")
        bus.available_seats -= payload.quantity
        unit_price = bus.price

    booking = Booking(
        agency_id=agency.id,
        user_id=current_user.id,
        item_type=payload.item_type,
        item_id=payload.item_id,
        status=BookingStatus.PENDING,
        quantity=payload.quantity,
        total_price=Decimal(unit_price) * payload.quantity,
        check_in=payload.check_in,
        check_out=payload.check_out,
        passenger_details=[passenger.model_dump(mode="json") for passenger in payload.passenger_details],
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    return booking


@router.get("/api/user/bookings/", response_model=list[BookingRead])
def list_user_bookings(
    agency: CurrentAgency, current_user: TenantCustomer, db: DatabaseSession
) -> list[Booking]:
    statement = (
        select(Booking)
        .where(Booking.agency_id == agency.id, Booking.user_id == current_user.id)
        .order_by(Booking.created_at.desc())
    )
    return list(db.scalars(statement).all())


@router.get("/api/agency/bookings/", response_model=list[BookingRead])
def list_agency_bookings(
    agency: CurrentAgency, current_user: AgencyAdministrator, db: DatabaseSession
) -> list[Booking]:
    statement = (
        select(Booking)
        .where(Booking.agency_id == agency.id)
        .order_by(Booking.created_at.desc())
    )
    return list(db.scalars(statement).all())
