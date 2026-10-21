import enum
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Boolean,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class BookingStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    CANCELLED = "CANCELLED"


class BookingItemType(str, enum.Enum):
    FLIGHT = "FLIGHT"
    HOTEL = "HOTEL"
    BUS = "BUS"


class UserRole(str, enum.Enum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    AGENCY_ADMIN = "AGENCY_ADMIN"
    CUSTOMER = "CUSTOMER"


class SubscriptionPlan(str, enum.Enum):
    BASIC = "BASIC"
    PRO = "PRO"


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        Index(
            "uq_users_agency_email",
            "agency_id",
            "email",
            unique=True,
            postgresql_where=text("agency_id IS NOT NULL"),
            sqlite_where=text("agency_id IS NOT NULL"),
        ),
        Index(
            "uq_users_platform_email",
            "email",
            unique=True,
            postgresql_where=text("agency_id IS NULL"),
            sqlite_where=text("agency_id IS NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agency_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("agencies.id", ondelete="RESTRICT"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="user_role"), nullable=False, default=UserRole.CUSTOMER
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    bookings: Mapped[list["Booking"]] = relationship(back_populates="user")
    agency: Mapped["Agency | None"] = relationship(back_populates="users")


class Agency(Base):
    __tablename__ = "agencies"
    __table_args__ = (
        Index("uq_agencies_subdomain", "subdomain", unique=True),
        Index(
            "uq_agencies_custom_domain",
            "custom_domain",
            unique=True,
            postgresql_where=text("custom_domain IS NOT NULL"),
            sqlite_where=text("custom_domain IS NOT NULL"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    subdomain: Mapped[str] = mapped_column(String(63), nullable=False)
    custom_domain: Mapped[str | None] = mapped_column(String(253))
    logo_url: Mapped[str | None] = mapped_column(String(2048))
    primary_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#0F172A")
    secondary_color: Mapped[str] = mapped_column(String(7), nullable=False, default="#0D9488")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    users: Mapped[list[User]] = relationship(back_populates="agency")
    subscription: Mapped["AgencySubscription | None"] = relationship(
        back_populates="agency", uselist=False
    )


class Flight(Base):
    __tablename__ = "flights"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_flights_price_nonnegative"),
        CheckConstraint("available_seats >= 0", name="ck_flights_seats_nonnegative"),
        Index(
            "ix_flights_agency_route_departure",
            "agency_id",
            "origin_city",
            "destination_city",
            "departure_time",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agency_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    flight_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    airline: Mapped[str] = mapped_column(String(120), nullable=False)
    origin_city: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_city: Mapped[str] = mapped_column(String(120), nullable=False)
    departure_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    available_seats: Mapped[int] = mapped_column(Integer, nullable=False)


class Hotel(Base):
    __tablename__ = "hotels"
    __table_args__ = (
        CheckConstraint("price_per_night >= 0", name="ck_hotels_price_nonnegative"),
        CheckConstraint("available_rooms >= 0", name="ck_hotels_rooms_nonnegative"),
        CheckConstraint("star_rating >= 1 AND star_rating <= 5", name="ck_hotels_rating_range"),
        Index("ix_hotels_agency_city", "agency_id", "city"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agency_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    city: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    price_per_night: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    available_rooms: Mapped[int] = mapped_column(Integer, nullable=False)
    star_rating: Mapped[int] = mapped_column(Integer, nullable=False)


class Bus(Base):
    __tablename__ = "buses"
    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_buses_price_nonnegative"),
        CheckConstraint("available_seats >= 0", name="ck_buses_seats_nonnegative"),
        Index("ix_buses_agency_route_departure", "agency_id", "origin", "destination", "departure_time"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agency_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    operator: Mapped[str] = mapped_column(String(120), nullable=False)
    origin: Mapped[str] = mapped_column(String(120), nullable=False)
    destination: Mapped[str] = mapped_column(String(120), nullable=False)
    departure_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    arrival_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    available_seats: Mapped[int] = mapped_column(Integer, nullable=False)


class Booking(Base):
    __tablename__ = "bookings"
    __table_args__ = (
        CheckConstraint(
            "item_id > 0",
            name="ck_bookings_item_id_positive",
        ),
        CheckConstraint("quantity > 0", name="ck_bookings_quantity_positive"),
        CheckConstraint("total_price >= 0", name="ck_bookings_total_nonnegative"),
        CheckConstraint(
            "(check_in IS NULL AND check_out IS NULL) OR "
            "(check_in IS NOT NULL AND check_out IS NOT NULL AND check_out > check_in)",
            name="ck_bookings_stay_dates",
        ),
        Index("ix_bookings_agency_user_created", "agency_id", "user_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agency_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agencies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    item_type: Mapped[BookingItemType] = mapped_column(
        Enum(BookingItemType, name="booking_item_type"), nullable=False
    )
    item_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus, name="booking_status"), nullable=False, default=BookingStatus.PENDING
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    total_price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    check_in: Mapped[date | None] = mapped_column(Date)
    check_out: Mapped[date | None] = mapped_column(Date)
    passenger_details: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    user: Mapped[User] = relationship(back_populates="bookings")
    agency: Mapped[Agency] = relationship()


class AgencySubscription(Base):
    __tablename__ = "agency_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    agency_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("agencies.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    plan: Mapped[SubscriptionPlan] = mapped_column(
        Enum(SubscriptionPlan, name="subscription_plan"),
        nullable=False,
        default=SubscriptionPlan.BASIC,
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="TRIALING")
    stripe_customer_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    stripe_subscription_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    current_period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    current_period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancel_at_period_end: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    agency: Mapped[Agency] = relationship(back_populates="subscription")


class ProcessedStripeEvent(Base):
    __tablename__ = "processed_stripe_events"

    event_id: Mapped[str] = mapped_column(String(255), primary_key=True)
    processed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
