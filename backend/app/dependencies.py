from typing import Annotated, Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import Agency, User, UserRole

bearer_scheme = HTTPBearer(auto_error=False)
DatabaseSession = Annotated[Session, Depends(get_db)]


def get_current_agency(request: Request, db: DatabaseSession) -> Agency:
    hostname = (request.url.hostname or "").strip(".").lower()
    root_domain = settings.platform_root_domain.strip(".").lower()

    agency = db.scalar(
        select(Agency).where(
            Agency.is_active.is_(True),
            (Agency.custom_domain == hostname)
            | (
                Agency.subdomain
                == (
                    hostname[: -(len(root_domain) + 1)]
                    if hostname.endswith(f".{root_domain}")
                    else hostname.split(".", maxsplit=1)[0]
                    if hostname.endswith(".localhost")
                    else ""
                )
            ),
        )
    )
    if agency is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agency storefront not found.")
    return agency


CurrentAgency = Annotated[Agency, Depends(get_current_agency)]


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DatabaseSession,
) -> User:
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="A valid bearer token is required.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise unauthorized

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.jwt_secret_key.get_secret_value(),
            algorithms=[settings.jwt_algorithm],
        )
        if payload.get("type") != "access":
            raise unauthorized
        user_id = int(payload["sub"])
        if user_id <= 0:
            raise ValueError("Invalid user id.")
        token_agency_id = payload.get("agency_id")
        token_role = UserRole(payload["role"])
    except (InvalidTokenError, KeyError, TypeError, ValueError):
        raise unauthorized from None

    user = db.get(User, user_id)
    if (
        user is None
        or user.role is not token_role
        or user.agency_id != token_agency_id
    ):
        raise unauthorized
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_tenant_roles(*roles: UserRole) -> Callable[..., User]:
    def dependency(current_user: CurrentUser, agency: CurrentAgency) -> User:
        if current_user.agency_id != agency.id or current_user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")
        return current_user

    return dependency


TenantCustomer = Annotated[User, Depends(require_tenant_roles(UserRole.CUSTOMER))]
AgencyAdministrator = Annotated[
    User, Depends(require_tenant_roles(UserRole.AGENCY_ADMIN))
]


def require_platform_admin(current_user: CurrentUser) -> User:
    if current_user.role is not UserRole.PLATFORM_ADMIN or current_user.agency_id is not None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Platform administrator access required.")
    return current_user


PlatformAdministrator = Annotated[User, Depends(require_platform_admin)]
