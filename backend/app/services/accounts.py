"""Finding and creating accounts for the four user types."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import ApiError
from app.core.security import hash_password
from app.models.users import Admin, Freelancer, Organisation, WorkHost

Account = Freelancer | WorkHost | Organisation | Admin

MODELS: dict[str, Any] = {
    "freelancer": Freelancer,
    "workhost": WorkHost,
    "organisation": Organisation,
    "admin": Admin,
}


def get_by_email(db: Session, user_type: str, email: str) -> Account | None:
    model = MODELS[user_type]
    account: Account | None = db.scalar(select(model).where(model.user_email == email.lower()))
    return account


def get_by_id(db: Session, user_type: str, user_id: uuid.UUID) -> Account | None:
    account: Account | None = db.get(MODELS[user_type], user_id)
    return account


def create_account(
    db: Session, user_type: str, *, email: str, mobile_number: str, password: str, **extra: Any
) -> Account:
    """Create and commit an account. The password is hashed here and never stored as given."""
    model = MODELS[user_type]
    account: Account = model(
        user_email=email.lower(),
        mobile_number=mobile_number,
        password_hash=hash_password(password),
        **extra,
    )
    db.add(account)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ApiError(409, "email_taken", "An account with this email already exists") from None
    return account
