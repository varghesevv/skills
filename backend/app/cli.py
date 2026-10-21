"""Operator commands.

    python -m app.cli create-admin --email you@example.com --mobile +971500000000
    python -m app.cli seed-demo

Passwords are never accepted as command-line arguments (they would end up in shell history and
process lists): create-admin asks for it (or reads one line from stdin), and seed-demo reads
DEMO_USER_PASSWORD from the environment. Passwords are never printed or logged.
"""

import argparse
import getpass
import sys
from dataclasses import dataclass

from sqlalchemy.orm import sessionmaker

from app.core.config import MIN_STRICT_SECRET_LENGTH, WEAK_SECRETS, get_settings
from app.core.db import get_engine
from app.core.logging_config import configure_logging
from app.schemas.auth import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH
from app.services.accounts import create_account, get_by_email

DEMO_DOMAIN = "example.com"


@dataclass(frozen=True)
class DemoUser:
    user_type: str
    name: str  # used in the email address
    mobile: str
    extra: dict[str, object]
    approved: bool = True


DEMO_USERS = [
    DemoUser("admin", "admin", "+971500000001", {}),
    DemoUser(
        "freelancer",
        "anita.plumber",
        "+971500000011",
        {"nationality": "Indian", "primary_language": "Hindi", "whatsapp_availability": True},
    ),
    DemoUser(
        "freelancer",
        "joseph.electrician",
        "+971500000012",
        {"nationality": "Keralite", "primary_language": "Malayalam"},
    ),
    DemoUser(
        "freelancer",
        "maria.carer",
        "+971500000013",
        {"nationality": "Philippines", "primary_language": "English"},
    ),
    DemoUser("workhost", "host.one", "+971500000021", {}),
    DemoUser("workhost", "host.two", "+971500000022", {}),
    DemoUser("organisation", "org.approved", "+971500000031", {"org_name": "Demo Staffing"}),
    DemoUser(
        "organisation",
        "org.pending",
        "+971500000032",
        {"org_name": "Demo Pending Org"},
        approved=False,
    ),
]


def _check_password(password: str) -> str | None:
    """Return a problem description, or None. Never includes the password."""
    if not MIN_PASSWORD_LENGTH <= len(password) <= MAX_PASSWORD_LENGTH:
        return f"Password must be {MIN_PASSWORD_LENGTH} to {MAX_PASSWORD_LENGTH} characters long"
    return None


def create_admin(email: str, mobile: str, use_stdin: bool) -> int:
    settings = get_settings()
    if use_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            print("The passwords do not match.", file=sys.stderr)
            return 1
    problem = _check_password(password)
    if problem is None and settings.environment in ("demo", "prod"):
        if password.lower() in WEAK_SECRETS or len(password) < MIN_STRICT_SECRET_LENGTH:
            problem = f"In {settings.environment} the password must be strong and long enough"
    if problem:
        print(problem, file=sys.stderr)
        return 1
    with sessionmaker(bind=get_engine(), expire_on_commit=False)() as db:
        if get_by_email(db, "admin", email) is not None:
            print("An admin with this email already exists.", file=sys.stderr)
            return 1
        create_account(db, "admin", email=email, mobile_number=mobile, password=password)
    print(f"Admin created: {email.lower()}")
    return 0


def seed_demo() -> int:
    """Create the fake demo users (idempotent). All share the DEMO_USER_PASSWORD from the environment."""
    settings = get_settings()
    if settings.environment == "prod":
        print("Refusing to create demo users in the prod environment.", file=sys.stderr)
        return 1
    if settings.demo_user_password is None or not settings.demo_user_password.get_secret_value():
        print("DEMO_USER_PASSWORD is not set (run `make env`).", file=sys.stderr)
        return 1
    password = settings.demo_user_password.get_secret_value()
    problem = _check_password(password)
    if problem is None and settings.environment == "demo":
        if password.lower() in WEAK_SECRETS or len(password) < MIN_STRICT_SECRET_LENGTH:
            problem = "In demo, DEMO_USER_PASSWORD must be strong and long enough"
    if problem:
        print(problem, file=sys.stderr)
        return 1
    created = 0
    with sessionmaker(bind=get_engine(), expire_on_commit=False)() as db:
        for user in DEMO_USERS:
            email = f"{user.name}@{DEMO_DOMAIN}"
            if get_by_email(db, user.user_type, email) is not None:
                continue
            account = create_account(
                db,
                user.user_type,
                email=email,
                mobile_number=user.mobile,
                password=password,
                **user.extra,
            )
            if user.user_type == "organisation" and user.approved:
                account.approval_status = "approved"  # type: ignore[union-attr]
                db.commit()
            created += 1
    print(f"Demo users created: {created} (already present: {len(DEMO_USERS) - created})")
    print("Log in with these emails and the DEMO_USER_PASSWORD value from your environment:")
    for user in DEMO_USERS:
        print(f"  {user.user_type:<13} {user.name}@{DEMO_DOMAIN}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    admin = sub.add_parser("create-admin", help="create an admin account")
    admin.add_argument("--email", required=True)
    admin.add_argument("--mobile", required=True)
    admin.add_argument("--password-stdin", action="store_true", help="read one line from stdin")
    sub.add_parser("seed-demo", help="create fake demo users (not allowed in prod)")
    args = parser.parse_args(argv)
    configure_logging()
    if args.command == "create-admin":
        return create_admin(args.email, args.mobile, args.password_stdin)
    return seed_demo()


if __name__ == "__main__":
    raise SystemExit(main())
