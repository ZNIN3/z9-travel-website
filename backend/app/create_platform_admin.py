from getpass import getpass

from pydantic import EmailStr, TypeAdapter, ValidationError
from sqlalchemy import func, select

from app.database import SessionLocal
from app.models import User, UserRole
from app.security import hash_password


def main() -> None:
    name = input("Platform administrator name: ").strip()
    if not name:
        raise SystemExit("Name cannot be blank.")

    try:
        email = str(TypeAdapter(EmailStr).validate_python(input("Platform administrator email: "))).lower()
    except ValidationError as error:
        raise SystemExit(f"Invalid email address: {error}") from error

    password = getpass("Password (minimum 12 characters): ")
    if len(password) < 12:
        raise SystemExit("Password must be at least 12 characters.")
    confirmation = getpass("Confirm password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match.")

    with SessionLocal.begin() as db:
        existing = db.scalar(
            select(User).where(
                User.agency_id.is_(None),
                func.lower(User.email) == email,
            )
        )
        if existing is not None:
            raise SystemExit("A platform account with this email already exists.")
        db.add(
            User(
                name=name,
                email=email,
                password_hash=hash_password(password),
                agency_id=None,
                role=UserRole.PLATFORM_ADMIN,
            )
        )
    print("Platform administrator created.")


if __name__ == "__main__":
    main()
