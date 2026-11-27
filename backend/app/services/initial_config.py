"""The initial config: the first people of Skills, read from `initial.json` when the API starts.

Story S100 (stories/s100-initial-config.md). The file names the OWNER, the churches
("organisations") with their ADMINs, and the home groups with their leaders (VERIFIERs): the
people the trust model needs before anyone else can join (docs/verification.md). Searchers and
providers are not in it: they sign up and are admitted in the app, with their vouches, as usual.

What happens at start-up (`run_at_startup`):

- no file configured, or no file at the path: nothing; the API starts as before;
- an empty database (no OWNER): everything in the file is created in one transaction, written to
  the history as operator changes;
- a database that has an OWNER: the file is checked against it, and the API refuses to start when
  they disagree (the message says what differs). After a legitimate change in the app (a handover,
  a succession) update the file or remove it.

Every password in the file is temporary. It is hashed like any other and never logged; the person
must choose their own the first time they sign in (`Person.must_change_password`), and nothing else
is open to them until then. The file holds passwords and personal details: git and the Docker image
leave it out, and it must never be committed (the repository is public).

`backend/schema.json` is the JSON Schema of the file, generated from the models here:

    python -m app.services.initial_config --write-schema   # after changing the models
    python -m app.services.initial_config --check-schema   # the tests do this too
"""

import argparse
import json
import logging
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, SecretStr, StringConstraints, ValidationError
from sqlalchemy import func, select, text
from sqlalchemy.exc import DataError, IntegrityError
from sqlalchemy.orm import Session

from app.core.config import (
    MIN_STRICT_SECRET_LENGTH,
    STRICT_ENVIRONMENTS,
    WEAK_SECRETS,
    Settings,
)
from app.core.security import hash_password
from app.models.church import Church, HomeGroup, Person
from app.models.trust import StatusChange
from app.schemas.auth import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, Email, Mobile, PersonName

logger = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[2]
SCHEMA_FILE = BACKEND_DIR / "schema.json"
# One start-up at a time applies or checks the file (several API processes may start together).
_LOCK_KEY = "skills-initial-config"


class InitialConfigError(Exception):
    """The file cannot be used. The message is safe to log: no password and no email address."""


# --- the file ------------------------------------------------------------------------------------

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
TemporaryPassword = Annotated[
    SecretStr,
    Field(
        min_length=MIN_PASSWORD_LENGTH,
        max_length=MAX_PASSWORD_LENGTH,
        description=(
            "A temporary password. The person must change it the first time they sign in. "
            f"In demo and prod it must be at least {MIN_STRICT_SECRET_LENGTH} characters."
        ),
    ),
]
MobileNumber = Annotated[
    Mobile,
    Field(
        description="7 to 15 digits, optionally starting with +; spaces and dashes are ignored. "
        "Unique across Skills."
    ),
]


class _Entry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OwnerEntry(_Entry):
    """The OWNER. Their name and mobile number are on the `admin` of their own organisation."""

    email: Annotated[Email, Field(description="Must be the admin email of one organisation.")]
    password: TemporaryPassword


class PersonEntry(_Entry):
    name: PersonName
    email: Email
    mobile: MobileNumber
    password: Annotated[
        TemporaryPassword | None,
        Field(
            description="Required once for every person except the OWNER, whose password is "
            "`owner.password`. A person named twice (ADMIN and leader) gives it once."
        ),
    ] = None


class AdminEntry(PersonEntry):
    """The church's ADMIN, or the OWNER in the OWNER's own church."""

    homegroup: Annotated[
        Name | None,
        Field(
            description="The home group the ADMIN belongs to, when they do not lead one. "
            "Needed only when the organisation has more than one home group."
        ),
    ] = None


class HomeGroupEntry(_Entry):
    name: Name
    verifier: Annotated[
        PersonEntry,
        Field(description="The group's leader. May be the organisation's ADMIN (same email)."),
    ]


class OrganisationEntry(_Entry):
    """A church."""

    name: Name
    admin: AdminEntry
    homegroups: Annotated[list[HomeGroupEntry], Field(min_length=1)]


class InitialConfig(_Entry):
    """The first people of Skills: the OWNER, the churches with their ADMINs and the home groups
    with their leaders. Searchers and providers are not in the file: they join through the app.
    A row of demo-logins.csv maps here as: status owner/admin/verifier = where the person is
    named, church = organisation name, home_group = home group name."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, title="Skills initial config (initial.json)"
    )

    schema_: Annotated[str | None, Field(alias="$schema")] = None
    owner: OwnerEntry
    organisations: Annotated[list[OrganisationEntry], Field(min_length=1)]


def json_schema() -> dict[str, Any]:
    schema = InitialConfig.model_json_schema(by_alias=True)
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", **schema}


def parse(raw: str) -> InitialConfig:
    """Read the file's text. Raises InitialConfigError with every problem found."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise InitialConfigError(f"initial.json is not valid JSON (line {error.lineno})") from None
    try:
        return InitialConfig.model_validate(data)
    except ValidationError as error:
        problems = [
            f"{'.'.join(str(part) for part in e['loc']) or '(file)'}: {e['msg']}"
            for e in error.errors(include_input=False, include_url=False)
        ]
        raise InitialConfigError("initial.json is not valid: " + "; ".join(problems)) from None


# --- what the file means -------------------------------------------------------------------------


@dataclass
class PlannedPerson:
    email: str
    name: str
    mobile: str
    password: str
    status: Literal["owner", "admin", "verifier"]
    church: str  # the organisation's name, as written
    group: str  # their home group's name
    where: str  # where in the file, for messages


@dataclass
class PlannedChurch:
    name: str
    admin_email: str
    groups: dict[str, str] = field(default_factory=dict)  # group name -> leader email


@dataclass
class Plan:
    owner_email: str
    churches: list[PlannedChurch]
    people: list[PlannedPerson]


def _key(name: str) -> str:
    return name.strip().lower()


def plan(config: InitialConfig, *, environment: str) -> Plan:
    """Check the rules the schema cannot express, and work out who is who.

    The rules are those of docs/verification.md: one OWNER, the ADMIN of their own church; one
    ADMIN per church; one leader per group, who leads no other; every person in one church and one
    home group; email and mobile number unique. Raises InitialConfigError with every problem.
    """
    problems: list[str] = []
    owner_email = config.owner.email
    owner_orgs = [o for o in config.organisations if o.admin.email == owner_email]
    if len(owner_orgs) != 1:
        problems.append(
            "owner.email must be the admin email of exactly one organisation "
            f"(found {len(owner_orgs)}): the OWNER is the ADMIN of their own church"
        )

    seen_orgs: set[str] = set()
    for i, org in enumerate(config.organisations):
        if _key(org.name) in seen_orgs:
            problems.append(f"organisations[{i}].name: two organisations have this name")
        seen_orgs.add(_key(org.name))

    # Every mention of a person, by email.
    mentions: dict[str, list[tuple[str, int, PersonEntry]]] = {}
    for i, org in enumerate(config.organisations):
        mentions.setdefault(org.admin.email, []).append((f"organisations[{i}].admin", i, org.admin))
        for j, group in enumerate(org.homegroups):
            where = f"organisations[{i}].homegroups[{j}].verifier"
            mentions.setdefault(group.verifier.email, []).append((where, i, group.verifier))

    people: list[PlannedPerson] = []
    mobiles: dict[str, str] = {}
    churches: list[PlannedChurch] = []
    for i, org in enumerate(config.organisations):
        church = PlannedChurch(name=org.name.strip(), admin_email=org.admin.email)
        churches.append(church)
        for j, group in enumerate(org.homegroups):
            if _key(group.name) in {_key(g) for g in church.groups}:
                problems.append(
                    f"organisations[{i}].homegroups[{j}].name: two home groups of this "
                    "organisation have this name"
                )
            church.groups[group.name.strip()] = group.verifier.email

    for email, found in mentions.items():
        where, org_index, first = found[0]
        if len({m[1] for m in found}) > 1:
            problems.append(f"{where}: the same email is used in more than one organisation")
            continue
        if any(m[2].name != first.name or m[2].mobile != first.mobile for m in found[1:]):
            problems.append(f"{where}: the same email is given with different names or mobiles")
        org = config.organisations[org_index]
        led = [g.name.strip() for g in org.homegroups if g.verifier.email == email]
        if len(led) > 1:
            problems.append(f"{where}: one person can lead only one home group")
            continue
        is_owner = email == owner_email
        is_admin = org.admin.email == email
        status: Literal["owner", "admin", "verifier"] = (
            "owner" if is_owner else "admin" if is_admin else "verifier"
        )

        group_name = led[0] if led else None
        if is_admin and org.admin.homegroup is not None:
            chosen = next(
                (
                    g.name.strip()
                    for g in org.homegroups
                    if _key(g.name) == _key(org.admin.homegroup)
                ),
                None,
            )
            if chosen is None:
                problems.append(f"organisations[{org_index}].admin.homegroup: no such home group")
            elif group_name is not None and chosen != group_name:
                problems.append(
                    f"organisations[{org_index}].admin.homegroup: the ADMIN leads another home "
                    "group, and a leader belongs to the group they lead"
                )
            group_name = group_name or chosen
        if group_name is None:
            if len(org.homegroups) == 1:
                group_name = org.homegroups[0].name.strip()
            else:
                problems.append(
                    f"organisations[{org_index}].admin.homegroup: say which home group the ADMIN "
                    "belongs to (they lead none)"
                )
                continue

        passwords = {m[2].password.get_secret_value() for m in found if m[2].password is not None}
        if is_owner:
            if passwords:
                problems.append(f"{where}: the OWNER's password is owner.password, not given here")
            password = config.owner.password.get_secret_value()
        elif len(passwords) != 1:
            problems.append(
                f"{where}: give this person's password once"
                if not passwords
                else f"{where}: this person is given different passwords"
            )
            continue
        else:
            password = passwords.pop()
        if environment in STRICT_ENVIRONMENTS and (
            password.lower() in WEAK_SECRETS or len(password) < MIN_STRICT_SECRET_LENGTH
        ):
            problems.append(
                f"{where}: in {environment} the password must be strong and at least "
                f"{MIN_STRICT_SECRET_LENGTH} characters"
            )

        if first.mobile in mobiles:
            problems.append(f"{where}: the mobile number is also given at {mobiles[first.mobile]}")
        mobiles.setdefault(first.mobile, where)
        people.append(
            PlannedPerson(
                email=email,
                name=first.name,
                mobile=first.mobile,
                password=password,
                status=status,
                church=org.name.strip(),
                group=group_name,
                where=where,
            )
        )

    if problems:
        raise InitialConfigError("initial.json breaks the rules: " + "; ".join(problems))
    return Plan(owner_email=owner_email, churches=churches, people=people)


# --- applying and checking -----------------------------------------------------------------------


def _owner(db: Session) -> Person | None:
    return db.scalar(select(Person).where(Person.status == "owner", Person.closed_at.is_(None)))


def apply(db: Session, planned: Plan) -> None:
    """Create everyone in the plan, in one transaction committed here. The database must have no
    OWNER (an empty installation)."""
    if _owner(db) is not None:
        raise InitialConfigError("Skills is already set up: there is an OWNER")
    person_ids = {p.email: uuid.uuid4() for p in planned.people}
    church_ids: dict[str, uuid.UUID] = {}
    group_ids: dict[tuple[str, str], uuid.UUID] = {}
    try:
        # Churches and groups name their ADMIN and leader before those exist: checked at commit.
        for church in planned.churches:
            church_ids[church.name] = uuid.uuid4()
            db.add(
                Church(
                    id=church_ids[church.name],
                    name=church.name,
                    admin_id=person_ids[church.admin_email],
                )
            )
        db.flush()
        for church in planned.churches:
            for group_name, leader_email in church.groups.items():
                group_ids[(church.name, group_name)] = uuid.uuid4()
                db.add(
                    HomeGroup(
                        id=group_ids[(church.name, group_name)],
                        church_id=church_ids[church.name],
                        name=group_name,
                        leader_id=person_ids[leader_email],
                    )
                )
        db.flush()
        for person in planned.people:
            db.add(
                Person(
                    id=person_ids[person.email],
                    status=person.status,
                    church_id=church_ids[person.church],
                    home_group_id=group_ids[(person.church, person.group)],
                    full_name=person.name,
                    email=person.email,
                    mobile_number=person.mobile,
                    password_hash=hash_password(person.password),
                    must_change_password=True,
                )
            )
        db.flush()
        for person in planned.people:
            # Nobody in the app set these statuses: an operator change, as for the first OWNER.
            db.add(
                StatusChange(
                    person_id=person_ids[person.email],
                    from_status=None,
                    to_status=person.status,
                    changed_by_id=None,
                    kind="operator",
                )
            )
        db.commit()
    except (IntegrityError, DataError):
        db.rollback()
        raise InitialConfigError(
            "initial.json could not be applied: the database refused it (nothing was created)"
        ) from None


def differences(db: Session, planned: Plan) -> list[str]:
    """What in the file the database does not have. Names, mobile numbers and passwords are not
    compared: people change those themselves in the app. More in the database is fine."""

    def email_of(person_id: uuid.UUID) -> str | None:
        person = db.get(Person, person_id)
        return person.email if person is not None and person.closed_at is None else None

    found: list[str] = []
    owner = _owner(db)
    if owner is None or owner.email != planned.owner_email:
        found.append("the OWNER is someone else")
    for church in planned.churches:
        row = db.scalar(
            select(Church).where(
                func.lower(Church.name) == _key(church.name), Church.closed_at.is_(None)
            )
        )
        if row is None:
            found.append(f"there is no open church named {church.name!r}")
            continue
        if email_of(row.admin_id) != church.admin_email:
            found.append(f"the church {church.name!r} has another ADMIN")
        for group_name, leader_email in church.groups.items():
            group = db.scalar(
                select(HomeGroup).where(
                    HomeGroup.church_id == row.id,
                    func.lower(HomeGroup.name) == _key(group_name),
                    HomeGroup.closed_at.is_(None),
                )
            )
            if group is None:
                found.append(f"the church {church.name!r} has no open home group {group_name!r}")
            elif email_of(group.leader_id) != leader_email:
                found.append(f"the home group {group_name!r} of {church.name!r} has another leader")
    return found


Outcome = Literal["no_file", "applied", "matches"]


def apply_or_check(db: Session, config: InitialConfig, *, environment: str) -> Outcome:
    """Apply the config to an empty database, or check it against one that is set up."""
    planned = plan(config, environment=environment)
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": _LOCK_KEY})
    if _owner(db) is None:
        apply(db, planned)
        return "applied"
    found = differences(db, planned)
    db.rollback()  # ends the transaction and its lock; nothing was changed
    if found:
        raise InitialConfigError(
            "initial.json does not match the database: "
            + "; ".join(found)
            + ". Update the file (or remove it) after a change made in the app."
        )
    return "matches"


def run_at_startup(settings: Settings, session_factory: Callable[[], Session]) -> Outcome:
    """Called when the API starts. Raises InitialConfigError, which stops the start-up."""
    if not settings.initial_config_path:
        return "no_file"
    path = Path(settings.initial_config_path)
    if not path.is_file():
        logger.info("No initial config at %s: starting without one", path)
        return "no_file"
    config = parse(path.read_text(encoding="utf-8"))
    with session_factory() as db:
        outcome = apply_or_check(db, config, environment=settings.environment)
    if outcome == "applied":
        logger.info(
            "Initial config applied: %d churches; each person must change their password",
            len(config.organisations),
        )
    else:
        logger.info("Initial config matches the database")
    return outcome


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="The JSON Schema of initial.json")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write-schema", action="store_true", help=f"write {SCHEMA_FILE.name}")
    mode.add_argument("--check-schema", action="store_true", help="fail when it is out of date")
    args = parser.parse_args(argv)
    wanted = json.dumps(json_schema(), indent=2, sort_keys=True) + "\n"
    if args.write_schema:
        SCHEMA_FILE.write_text(wanted, encoding="utf-8")
        return 0
    current = SCHEMA_FILE.read_text(encoding="utf-8") if SCHEMA_FILE.is_file() else ""
    if current != wanted:
        print(f"{SCHEMA_FILE} is out of date: run --write-schema", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(_main())
