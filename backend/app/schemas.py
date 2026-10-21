from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from app.models import BookingItemType, BookingStatus, SubscriptionPlan, UserRole


class AgencyBrand(BaseModel):
    id: int
    name: str
    subdomain: str
    custom_domain: str | None
    logo_url: str | None
    primary_color: str
    secondary_color: str

    model_config = ConfigDict(from_attributes=True)


class AgencyCreate(BaseModel):
    name: str = Field(min_length=2, max_length=160)
    subdomain: str = Field(pattern=r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?$")
    admin_name: str = Field(min_length=1, max_length=120)
    admin_email: EmailStr
    admin_password: str = Field(min_length=10, max_length=128)
    logo_url: str | None = Field(default=None, max_length=2048)
    primary_color: str = Field(default="#0F172A", pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str = Field(default="#0D9488", pattern=r"^#[0-9A-Fa-f]{6}$")

    @field_validator("name", "admin_name")
    @classmethod
    def trim_required_names(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name cannot be blank.")
        return normalized


class AgencySubscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    plan: SubscriptionPlan
    status: str
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool


class PlatformSubscriptionRead(BaseModel):
    agency_id: int
    agency_name: str
    subdomain: str
    plan: SubscriptionPlan
    status: str
    stripe_customer_id: str | None
    stripe_subscription_id: str | None
    current_period_start: datetime | None
    current_period_end: datetime | None
    cancel_at_period_end: bool


class AgencyDashboardRead(BaseModel):
    agency: AgencyBrand
    subscription: AgencySubscriptionRead
    bookings_this_period: int
    monthly_booking_limit: int | None


class BillingPlanRead(BaseModel):
    plan: SubscriptionPlan
    monthly_booking_limit: int | None
    custom_domain: bool


class CheckoutSessionRead(BaseModel):
    checkout_url: str


class BillingPortalRead(BaseModel):
    portal_url: str


class CheckoutSessionCreate(BaseModel):
    plan: SubscriptionPlan


class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    @field_validator("name")
    @classmethod
    def trim_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("Name cannot be blank.")
        return normalized


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    agency_id: int | None
    role: UserRole
    name: str
    email: EmailStr
    created_at: datetime


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int


class FlightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    flight_number: str
    airline: str
    origin_city: str
    destination_city: str
    departure_time: datetime
    arrival_time: datetime
    price: Decimal
    available_seats: int


class HotelRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    city: str
    description: str
    price_per_night: Decimal
    available_rooms: int
    star_rating: int


class BusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    operator: str
    origin: str
    destination: str
    departure_time: datetime
    arrival_time: datetime
    price: Decimal
    available_seats: int


class PassengerDetails(BaseModel):
    full_name: str = Field(min_length=1, max_length=120)
    email: EmailStr | None = None
    phone: str | None = Field(default=None, max_length=30)
    passport_number: str | None = Field(default=None, max_length=40)


class BookingCreate(BaseModel):
    item_type: BookingItemType
    item_id: int = Field(gt=0)
    quantity: int = Field(default=1, ge=1, le=9)
    passenger_details: list[PassengerDetails] = Field(default_factory=list, max_length=9)
    check_in: date | None = None
    check_out: date | None = None

    @model_validator(mode="after")
    def validate_booking_details(self) -> "BookingCreate":
        if self.item_type is BookingItemType.HOTEL:
            if self.check_in is None or self.check_out is None:
                raise ValueError("Hotel bookings require check_in and check_out.")
            if self.check_out <= self.check_in:
                raise ValueError("check_out must be later than check_in.")
        else:
            if self.check_in is not None or self.check_out is not None:
                raise ValueError("check_in and check_out are only valid for hotel bookings.")
            if len(self.passenger_details) != self.quantity:
                raise ValueError("Provide one passenger_details entry for each seat.")
        return self


class BookingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    item_type: BookingItemType
    item_id: int
    status: BookingStatus
    quantity: int
    total_price: Decimal
    check_in: date | None
    check_out: date | None
    passenger_details: list[dict[str, Any]]
    created_at: datetime


class FlightCreate(BaseModel):
    flight_number: str = Field(min_length=1, max_length=20)
    airline: str = Field(min_length=1, max_length=120)
    origin_city: str = Field(min_length=1, max_length=120)
    destination_city: str = Field(min_length=1, max_length=120)
    departure_time: datetime
    arrival_time: datetime
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    available_seats: int = Field(ge=0)


class HotelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=180)
    city: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=10000)
    price_per_night: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    available_rooms: int = Field(ge=0)
    star_rating: int = Field(ge=1, le=5)


class BusCreate(BaseModel):
    operator: str = Field(min_length=1, max_length=120)
    origin: str = Field(min_length=1, max_length=120)
    destination: str = Field(min_length=1, max_length=120)
    departure_time: datetime
    arrival_time: datetime
    price: Decimal = Field(ge=0, max_digits=10, decimal_places=2)
    available_seats: int = Field(ge=0)


class AgencyBrandUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=160)
    logo_url: str | None = Field(default=None, max_length=2048)
    primary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    custom_domain: str | None = Field(default=None, max_length=253)
