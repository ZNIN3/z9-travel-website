from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.dependencies import CurrentAgency, DatabaseSession
from app.models import Bus, Flight, Hotel
from app.schemas import BusRead, FlightRead, HotelRead

router = APIRouter(prefix="/api", tags=["travel search"])


@router.get("/flights/search/", response_model=list[FlightRead])
def search_flights(
    agency: CurrentAgency,
    db: DatabaseSession,
    from_city: str = Query(alias="from", min_length=2, max_length=120),
    to_city: str = Query(alias="to", min_length=2, max_length=120),
    travel_date: date = Query(alias="date"),
) -> list[Flight]:
    # Flight schedules are stored in UTC; date searches use the UTC calendar day.
    day_start = datetime.combine(travel_date, time.min, tzinfo=timezone.utc)
    next_day = day_start + timedelta(days=1)
    statement = (
        select(Flight)
        .where(
            Flight.agency_id == agency.id,
            Flight.origin_city.ilike(from_city.strip()),
            Flight.destination_city.ilike(to_city.strip()),
            Flight.departure_time >= day_start,
            Flight.departure_time < next_day,
            Flight.available_seats > 0,
        )
        .order_by(Flight.departure_time)
    )
    return list(db.scalars(statement).all())


@router.get("/hotels/search/", response_model=list[HotelRead])
def search_hotels(
    agency: CurrentAgency,
    db: DatabaseSession,
    location: str = Query(min_length=2, max_length=120),
    check_in: date = Query(),
    check_out: date = Query(),
) -> list[Hotel]:
    if check_out <= check_in:
        raise HTTPException(status_code=422, detail="check_out must be later than check_in.")

    statement = (
        select(Hotel)
        .where(
            Hotel.agency_id == agency.id,
            Hotel.city.ilike(f"%{location.strip()}%"),
            Hotel.available_rooms > 0,
        )
        .order_by(Hotel.star_rating.desc(), Hotel.price_per_night)
    )
    return list(db.scalars(statement).all())


@router.get("/buses/search/", response_model=list[BusRead])
def search_buses(
    agency: CurrentAgency,
    db: DatabaseSession,
    from_city: str = Query(alias="from", min_length=2, max_length=120),
    to_city: str = Query(alias="to", min_length=2, max_length=120),
    travel_date: date = Query(alias="date"),
) -> list[Bus]:
    day_start = datetime.combine(travel_date, time.min, tzinfo=timezone.utc)
    next_day = day_start + timedelta(days=1)
    statement = (
        select(Bus)
        .where(
            Bus.agency_id == agency.id,
            Bus.origin.ilike(from_city.strip()),
            Bus.destination.ilike(to_city.strip()),
            Bus.departure_time >= day_start,
            Bus.departure_time < next_day,
            Bus.available_seats > 0,
        )
        .order_by(Bus.departure_time)
    )
    return list(db.scalars(statement).all())
