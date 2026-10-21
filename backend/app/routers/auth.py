from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.config import settings
from app.dependencies import CurrentAgency, DatabaseSession
from app.models import User, UserRole
from app.schemas import LoginRequest, TokenResponse, UserCreate, UserRead
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post("/register/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_user(
    payload: UserCreate, agency: CurrentAgency, db: DatabaseSession
) -> User:
    normalized_email = str(payload.email).lower()
    existing_user = db.scalar(
        select(User).where(
            User.agency_id == agency.id,
            func.lower(User.email) == normalized_email,
        )
    )
    if existing_user is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.")

    user = User(
        name=payload.name,
        email=normalized_email,
        password_hash=hash_password(payload.password),
        agency_id=agency.id,
        role=UserRole.CUSTOMER,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists.") from None
    db.refresh(user)
    return user


@router.post("/login/", response_model=TokenResponse)
def login(
    payload: LoginRequest, agency: CurrentAgency, db: DatabaseSession
) -> TokenResponse:
    normalized_email = str(payload.email).lower()
    user = db.scalar(
        select(User).where(
            User.agency_id == agency.id,
            func.lower(User.email) == normalized_email,
        )
    )
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=60 * settings.access_token_expire_minutes,
    )


@router.post("/platform/login/", response_model=TokenResponse)
def platform_login(payload: LoginRequest, db: DatabaseSession) -> TokenResponse:
    normalized_email = str(payload.email).lower()
    user = db.scalar(
        select(User).where(
            User.agency_id.is_(None),
            User.role == UserRole.PLATFORM_ADMIN,
            func.lower(User.email) == normalized_email,
        )
    )
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email or password is incorrect.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return TokenResponse(
        access_token=create_access_token(user),
        expires_in=60 * settings.access_token_expire_minutes,
    )
