"""Helpers that build accounts of the older kind (freelancers), for the tests of what still
reads them: the reports and the demo data generator, until slice S5.3."""

import secrets
import uuid

from sqlalchemy.orm import Session

from app.models.labels import FreelancerLabel
from app.models.users import Freelancer
from app.services.accounts import create_account
from tests.api_helpers import label_id


def freelancer(
    session: Session,
    email: str,
    *,
    rate: float | None = 50,
    currency: str = "AED",
    negotiable: bool = False,
    skills: tuple[tuple[str, str | None], ...] = (("plumbing", None),),
    labels: tuple[tuple[str, str], ...] = (),
    full_name: str | None = None,
) -> Freelancer:
    """A freelancer with skills (name, level) and other labels (type, name)."""
    extra: dict[str, object] = {"is_rate_negotiable": negotiable}
    if full_name is not None:
        extra["full_name"] = full_name
    if rate is not None:
        extra.update(rate_per_hour=rate, rate_currency=currency)
    account = create_account(
        session,
        "freelancer",
        email=email,
        mobile_number="+971500000001",
        password=secrets.token_urlsafe(16),
        **extra,
    )
    assert isinstance(account, Freelancer)
    for name, level in skills:
        level_id = uuid.UUID(label_id(session, "skill_level", level)) if level else None
        session.add(
            FreelancerLabel(
                freelancer_id=account.id,
                label_id=uuid.UUID(label_id(session, "skill", name)),
                level_label_id=level_id,
            )
        )
    for label_type, name in labels:
        session.add(
            FreelancerLabel(
                freelancer_id=account.id, label_id=uuid.UUID(label_id(session, label_type, name))
            )
        )
    session.commit()
    return account
