"""Operator commands.

    python -m app.cli create-owner --name "Full Name" --email you@example.com \
        --mobile +971500000000 --church "Church name" --group "Home group name"
    python -m app.cli create-admin --email you@example.com --mobile +971500000000
    python -m app.cli purge-notifications [--months 12]
    python -m app.cli seed-demo
    python -m app.cli generate-demo-data --csv logins.csv [--reset]

Passwords are never accepted as command-line arguments (they would end up in shell history and
process lists): create-owner and create-admin ask for it (or read one line from stdin), and
seed-demo reads DEMO_USER_PASSWORD from the environment. Passwords are never printed or logged.
"""

import argparse
import csv
import getpass
import os
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TextIO

from pydantic import TypeAdapter, ValidationError
from sqlalchemy.orm import sessionmaker

from app.core.config import MIN_STRICT_SECRET_LENGTH, WEAK_SECRETS, get_settings
from app.core.db import get_engine
from app.core.logging_config import configure_logging
from app.demo_data import DEMO_DATA_DOMAIN, CredentialRow, generate, remove_generated
from app.schemas.auth import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    Email,
    PersonName,
    check_mobile,
)
from app.services import notifications
from app.services.accounts import create_account, get_by_email
from app.services.operators import SetupError, create_first_owner

DEMO_DOMAIN = "example.com"

# The same rules as the API applies to a sign-up.
_EMAIL: TypeAdapter[str] = TypeAdapter(Email)
_PERSON_NAME: TypeAdapter[str] = TypeAdapter(PersonName)


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
        {
            "full_name": "Anita Sharma",
            "nationality": "Indian",
            "primary_language": "Hindi",
            "whatsapp_availability": True,
        },
    ),
    DemoUser(
        "freelancer",
        "joseph.electrician",
        "+971500000012",
        {
            "full_name": "Joseph Thomas",
            "nationality": "Keralite",
            "primary_language": "Malayalam",
        },
    ),
    DemoUser(
        "freelancer",
        "maria.carer",
        "+971500000013",
        {
            "full_name": "Maria Santos",
            "nationality": "Philippines",
            "primary_language": "English",
        },
    ),
    DemoUser("workhost", "host.one", "+971500000021", {"full_name": "Hassan Host"}),
    DemoUser("workhost", "host.two", "+971500000022", {"full_name": "Layla Host"}),
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


def _ask_password(use_stdin: bool) -> str | None:
    """Read and check a new password; print why and return None when it cannot be used."""
    settings = get_settings()
    if use_stdin:
        password = sys.stdin.readline().rstrip("\n")
    else:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Repeat password: "):
            print("The passwords do not match.", file=sys.stderr)
            return None
    problem = _check_password(password)
    weak = password.lower() in WEAK_SECRETS or len(password) < MIN_STRICT_SECRET_LENGTH
    if problem is None and settings.environment in ("demo", "prod") and weak:
        problem = f"In {settings.environment} the password must be strong and long enough"
    if problem:
        print(problem, file=sys.stderr)
        return None
    return password


def create_owner(
    name: str, email: str, mobile: str, church: str, group: str, use_stdin: bool
) -> int:
    """Set up Skills: the first OWNER, their church and their home group."""
    try:
        mobile = check_mobile(mobile)
    except ValueError as error:
        print(error, file=sys.stderr)
        return 1
    try:
        name = _PERSON_NAME.validate_python(name)
        email = str(_EMAIL.validate_python(email))
    except ValidationError as error:
        print("; ".join(str(e["msg"]) for e in error.errors()), file=sys.stderr)
        return 1
    if not church.strip() or not group.strip():
        print("The church and the home group must not be empty.", file=sys.stderr)
        return 1
    if len(church.strip()) > 200 or len(group.strip()) > 200:
        print("The church and the home group names are at most 200 characters.", file=sys.stderr)
        return 1
    password = _ask_password(use_stdin)
    if password is None:
        return 1
    with sessionmaker(bind=get_engine(), expire_on_commit=False)() as db:
        try:
            create_first_owner(
                db,
                full_name=name,
                email=email,
                mobile_number=mobile,
                password=password,
                church_name=church,
                group_name=group,
            )
        except SetupError as error:
            print(error, file=sys.stderr)
            return 1
    print(f"OWNER created: {email.strip().lower()}, church {church.strip()!r}")
    return 0


def create_admin(email: str, mobile: str, use_stdin: bool) -> int:
    password = _ask_password(use_stdin)
    if password is None:
        return 1
    with sessionmaker(bind=get_engine(), expire_on_commit=False)() as db:
        if get_by_email(db, "admin", email) is not None:
            print("An admin with this email already exists.", file=sys.stderr)
            return 1
        create_account(db, "admin", email=email, mobile_number=mobile, password=password)
    print(f"Admin created: {email.lower()}")
    return 0


def _demo_password() -> str | None:
    """DEMO_USER_PASSWORD from the environment, or None after printing why it cannot be used."""
    settings = get_settings()
    if settings.environment == "prod":
        print("Refusing to create demo users in the prod environment.", file=sys.stderr)
        return None
    if settings.demo_user_password is None or not settings.demo_user_password.get_secret_value():
        print("DEMO_USER_PASSWORD is not set (run `make env`).", file=sys.stderr)
        return None
    password = settings.demo_user_password.get_secret_value()
    problem = _check_password(password)
    weak = password.lower() in WEAK_SECRETS or len(password) < MIN_STRICT_SECRET_LENGTH
    if problem is None and settings.environment == "demo" and weak:
        problem = "In demo, DEMO_USER_PASSWORD must be strong and long enough"
    if problem:
        print(problem, file=sys.stderr)
        return None
    return password


def generate_demo_data(csv_path: str, reset: bool) -> int:
    """Create the larger demo data set and write the login list (with the shared password)."""
    password = _demo_password()
    if password is None:
        return 1
    with sessionmaker(bind=get_engine(), expire_on_commit=False)() as db:
        if reset:
            print(f"Removed {remove_generated(db)} earlier generated accounts.", file=sys.stderr)
        elif get_by_email(db, "organisation", f"admin.gulf.care.staffing@{DEMO_DATA_DOMAIN}"):
            print("Demo data already exists. Use --reset to replace it.", file=sys.stderr)
            return 1
        rows = generate(db, password)
    # The file holds the password on purpose (it is the login list), so it is owner-only, and
    # nothing is printed to the log. "-" writes to standard output for redirecting into a file.
    if csv_path == "-":
        _write_logins(sys.stdout, rows, password)
    else:
        with os.fdopen(os.open(csv_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600), "w") as out:
            _write_logins(out, rows, password)
    counts: dict[str, int] = {}
    for row in rows:
        counts[row.user_type] = counts.get(row.user_type, 0) + 1
    target = "standard output" if csv_path == "-" else csv_path
    print(f"Created accounts {counts}. Login list written to {target}.", file=sys.stderr)
    return 0


def _write_logins(out: TextIO, rows: list[CredentialRow], password: str) -> None:
    writer = csv.writer(out)
    writer.writerow(["user_type", "email", "password", "name", "status"])
    for row in rows:
        writer.writerow([row.user_type, row.email, password, row.name, row.status])


def seed_demo() -> int:
    """Create the fake demo users (idempotent), all with the DEMO_USER_PASSWORD password."""
    password = _demo_password()
    if password is None:
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


def purge_notifications(months: int) -> int:
    """Delete notifications older than the retention (12 months by default; decision O-02)."""
    cutoff = notifications.months_before(datetime.now(UTC), months)
    with sessionmaker(bind=get_engine(), expire_on_commit=False)() as db:
        deleted = notifications.purge_older_than(db, cutoff)
    print(f"Deleted {deleted} notifications older than {months} months.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    sub = parser.add_subparsers(dest="command", required=True)
    owner = sub.add_parser(
        "create-owner", help="set up Skills: the first OWNER with their church and home group"
    )
    owner.add_argument("--name", required=True)
    owner.add_argument("--email", required=True)
    owner.add_argument("--mobile", required=True)
    owner.add_argument("--church", required=True, help="name of the first church")
    owner.add_argument("--group", required=True, help="name of the OWNER's home group")
    owner.add_argument("--password-stdin", action="store_true", help="read one line from stdin")
    admin = sub.add_parser("create-admin", help="create an admin account (older model)")
    admin.add_argument("--email", required=True)
    admin.add_argument("--mobile", required=True)
    admin.add_argument("--password-stdin", action="store_true", help="read one line from stdin")
    purge = sub.add_parser(
        "purge-notifications", help="delete in-app notifications older than the retention"
    )
    purge.add_argument("--months", type=int, default=12, choices=range(1, 121), metavar="1-120")
    sub.add_parser("seed-demo", help="create fake demo users (not allowed in prod)")
    gen = sub.add_parser(
        "generate-demo-data",
        help="create ~10 organisations, ~50 work hosts, ~200 freelancers and write a login CSV",
    )
    gen.add_argument("--csv", required=True, help="where to write the login list; - for stdout")
    gen.add_argument("--reset", action="store_true", help="remove earlier generated data first")
    args = parser.parse_args(argv)
    configure_logging()
    if args.command == "create-owner":
        return create_owner(
            args.name, args.email, args.mobile, args.church, args.group, args.password_stdin
        )
    if args.command == "create-admin":
        return create_admin(args.email, args.mobile, args.password_stdin)
    if args.command == "purge-notifications":
        return purge_notifications(args.months)
    if args.command == "generate-demo-data":
        return generate_demo_data(args.csv, args.reset)
    return seed_demo()


if __name__ == "__main__":
    raise SystemExit(main())
