"""The initial config read when the API starts (story S100, stories/s100-initial-config.md).

The file seeds the OWNER, the churches with their ADMINs and the home groups with their leaders.
Each person's password is temporary: until they change it the API refuses everything else.
"""

import copy
import json
import secrets
from collections.abc import Callable
from contextlib import nullcontext
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.chat.runtime import load_who
from app.core.config import get_settings
from app.core.security import verify_password
from app.models import Church, HomeGroup, Person, StatusChange
from app.services import initial_config
from app.services.initial_config import InitialConfigError, apply_or_check, parse, plan
from tests.api_helpers import API
from tests.test_endpoint_matrix import MATRIX, PUBLIC, code_of, request
from tests.trust_helpers import check_rules

BACKEND_DIR = Path(__file__).resolve().parents[1]
OWNER_PASSWORD = secrets.token_urlsafe(16)
LEADER_PASSWORD = secrets.token_urlsafe(16)
ADMIN_PASSWORD = secrets.token_urlsafe(16)
WRONG_PASSWORD = secrets.token_urlsafe(16)


def config_data() -> dict[str, Any]:
    """Two churches: the OWNER's (a leader of its own) and one whose ADMIN leads a group."""
    return {
        "owner": {"email": "Ray@Example.com", "password": OWNER_PASSWORD},
        "organisations": [
            {
                "name": "Fellowship Example",
                "admin": {
                    "name": "Ray Minister",
                    "email": "ray@example.com",
                    "mobile": "+971500000001",
                },
                "homegroups": [
                    {
                        "name": "Deira",
                        "verifier": {
                            "name": "Lena Leader",
                            "email": "lena@example.com",
                            "mobile": "+971 50 000 0002",
                            "password": LEADER_PASSWORD,
                        },
                    }
                ],
            },
            {
                "name": "Hope Example",
                "admin": {
                    "name": "Ada Admin",
                    "email": "ada@example.com",
                    "mobile": "+971500000003",
                    "password": ADMIN_PASSWORD,
                },
                "homegroups": [
                    {
                        "name": "Riverside",
                        "verifier": {
                            "name": "Ada Admin",
                            "email": "ada@example.com",
                            "mobile": "+971500000003",
                        },
                    },
                    {
                        "name": "Harbour",
                        "verifier": {
                            "name": "Hal Leader",
                            "email": "hal@example.com",
                            "mobile": "+971500000004",
                            "password": LEADER_PASSWORD,
                        },
                    },
                ],
            },
        ],
    }


def problems(data: dict[str, Any], environment: str = "local") -> str:
    with pytest.raises(InitialConfigError) as caught:
        plan(parse(json.dumps(data)), environment=environment)
    message = str(caught.value)
    # Messages are logged: never a password, never an email address.
    for secret in (OWNER_PASSWORD, LEADER_PASSWORD, ADMIN_PASSWORD):
        assert secret not in message
    assert "@" not in message
    return message


# --- the file and its schema (no database) -------------------------------------------------------


def test_schema_json_is_up_to_date() -> None:
    assert initial_config._main(["--check-schema"]) == 0, "run --write-schema"


def test_the_schema_describes_the_file() -> None:
    schema = json.loads((BACKEND_DIR / "schema.json").read_text())
    assert set(schema["required"]) == {"owner", "organisations"}
    assert schema["additionalProperties"] is False
    organisation = schema["$defs"]["OrganisationEntry"]
    # Searchers and providers join through the app, with their vouches: not in the file.
    assert set(organisation["properties"]) == {"name", "admin", "homegroups"}
    assert schema["$defs"]["PersonEntry"]["properties"]["password"]["anyOf"][0]["writeOnly"]


def test_the_example_file_is_valid() -> None:
    planned = plan(parse((BACKEND_DIR / "initial.example.json").read_text()), environment="local")
    assert sorted(p.status for p in planned.people) == ["owner", "verifier"]


def test_who_is_who() -> None:
    planned = plan(parse(json.dumps(config_data())), environment="local")
    people = {p.email: p for p in planned.people}
    assert set(people) == {
        "ray@example.com",
        "lena@example.com",
        "ada@example.com",
        "hal@example.com",
    }
    ray, lena, ada, hal = (
        people[e]
        for e in ("ray@example.com", "lena@example.com", "ada@example.com", "hal@example.com")
    )
    # The OWNER leads no group here: they belong to the only one, led by Lena.
    assert (ray.status, ray.group, ray.password) == ("owner", "Deira", OWNER_PASSWORD)
    assert (lena.status, lena.group, lena.mobile) == ("verifier", "Deira", "+971500000002")
    # An ADMIN who is also named as a leader leads that group and keeps the ADMIN status.
    assert (ada.status, ada.group, ada.password) == ("admin", "Riverside", ADMIN_PASSWORD)
    assert (hal.status, hal.church, hal.group) == ("verifier", "Hope Example", "Harbour")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("{not json", "not valid JSON"),
        (
            json.dumps({"owner": {"email": "a@example.com", "password": OWNER_PASSWORD}}),
            "organisations",
        ),
    ],
)
def test_a_file_that_is_not_valid_is_refused(raw: str, expected: str) -> None:
    with pytest.raises(InitialConfigError, match=expected):
        parse(raw)


def test_searchers_and_providers_are_not_allowed() -> None:
    data = config_data()
    data["organisations"][0]["searchers"] = []
    data["organisations"][0]["providers"] = []
    with pytest.raises(InitialConfigError, match="searchers: Extra inputs"):
        parse(json.dumps(data))


def test_every_person_needs_a_mobile_number_and_a_long_enough_password() -> None:
    data = config_data()
    del data["organisations"][0]["admin"]["mobile"]
    data["owner"]["password"] = "short"
    with pytest.raises(InitialConfigError) as caught:
        parse(json.dumps(data))
    assert "organisations.0.admin.mobile: Field required" in str(caught.value)
    assert "owner.password" in str(caught.value)
    assert "short" not in str(caught.value)


def _edit(change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    data = copy.deepcopy(config_data())
    change(data)
    return data


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (
            lambda d: d["owner"].update(email="nobody@example.com"),
            "admin email of exactly one organisation",
        ),
        (
            lambda d: d["organisations"][1].update(name="fellowship example"),
            "two organisations have this name",
        ),
        (
            lambda d: d["organisations"][1]["homegroups"][1].update(name="RIVERSIDE"),
            "two home groups of this organisation",
        ),
        (
            lambda d: d["organisations"][1]["homegroups"][1].update(
                verifier=d["organisations"][0]["homegroups"][0]["verifier"]
            ),
            "more than one organisation",
        ),
        (
            lambda d: d["organisations"][1]["homegroups"][1]["verifier"].update(
                email="ada@example.com", name="Ada Admin", mobile="+971500000003"
            ),
            "lead only one home group",
        ),
        (
            lambda d: d["organisations"][1]["homegroups"][0]["verifier"].update(name="Ada Other"),
            "different names or mobiles",
        ),
        (
            lambda d: d["organisations"][1]["homegroups"][1]["verifier"].update(
                mobile="+971500000002"
            ),
            "mobile number is also given",
        ),
        (
            lambda d: d["organisations"][0]["homegroups"][0]["verifier"].pop("password"),
            "give this person's password once",
        ),
        (
            lambda d: d["organisations"][1]["homegroups"][0]["verifier"].update(
                password=secrets.token_urlsafe(16)
            ),
            "different passwords",
        ),
        (
            lambda d: d["organisations"][0]["admin"].update(password=secrets.token_urlsafe(16)),
            "owner.password, not given here",
        ),
        (
            lambda d: d["organisations"][0]["admin"].update(homegroup="Nowhere"),
            "no such home group",
        ),
        (
            lambda d: d["organisations"][1]["admin"].update(homegroup="Harbour"),
            "leads another home group",
        ),
        (
            lambda d: d["organisations"][0]["homegroups"].append(
                {
                    "name": "Second",
                    "verifier": {
                        "name": "Sam Leader",
                        "email": "sam@example.com",
                        "mobile": "+971500000009",
                        "password": LEADER_PASSWORD,
                    },
                }
            ),
            "say which home group the ADMIN belongs to",
        ),
    ],
)
def test_the_rules_of_the_trust_model_are_checked(
    change: Callable[[dict[str, Any]], None], expected: str
) -> None:
    assert expected in problems(_edit(change))


def test_an_admin_who_leads_none_of_several_groups_names_theirs() -> None:
    def change(d: dict[str, Any]) -> None:
        d["organisations"][0]["homegroups"].append(
            {
                "name": "Second",
                "verifier": {
                    "name": "Sam Leader",
                    "email": "sam@example.com",
                    "mobile": "+971500000009",
                    "password": LEADER_PASSWORD,
                },
            }
        )
        d["organisations"][0]["admin"]["homegroup"] = "second"

    planned = plan(parse(json.dumps(_edit(change))), environment="local")
    owner = next(p for p in planned.people if p.status == "owner")
    assert owner.group == "Second"


def test_demo_and_prod_need_strong_passwords() -> None:
    data = config_data()
    data["owner"]["password"] = "ten-chars!"
    assert "in prod the password must be strong" in problems(data, environment="prod")
    plan(parse(json.dumps(data)), environment="local")  # fine locally


# --- applying it to the database ------------------------------------------------------------------


@pytest.fixture
def empty(session: Session) -> Session:
    """These tests need a database without an OWNER; the test database may hold seed rows."""
    assert session.scalar(select(Person.id).where(Person.status == "owner")) is None
    return session


def applied(session: Session) -> dict[str, Person]:
    outcome = apply_or_check(session, parse(json.dumps(config_data())), environment="ci")
    assert outcome == "applied"
    check_rules(session)  # the rules that hold at commit hold now
    people = session.scalars(select(Person).where(Person.email.like("%@example.com"))).all()
    return {str(p.email): p for p in people}


@pytest.mark.db
def test_an_empty_database_gets_everyone_in_the_file(empty: Session) -> None:
    people = applied(empty)
    ray, lena, ada, hal = (
        people[e]
        for e in ("ray@example.com", "lena@example.com", "ada@example.com", "hal@example.com")
    )
    assert (ray.status, lena.status, ada.status, hal.status) == (
        "owner",
        "verifier",
        "admin",
        "verifier",
    )

    fellowship = empty.get(Church, ray.church_id)
    hope = empty.get(Church, ada.church_id)
    assert fellowship is not None and hope is not None
    assert (fellowship.name, fellowship.admin_id) == ("Fellowship Example", ray.id)
    assert (hope.name, hope.admin_id) == ("Hope Example", ada.id)
    deira = empty.get(HomeGroup, lena.home_group_id)
    assert deira is not None and (deira.name, deira.leader_id) == ("Deira", lena.id)
    assert ray.home_group_id == deira.id
    riverside = empty.get(HomeGroup, ada.home_group_id)
    assert riverside is not None and riverside.leader_id == ada.id
    harbour = empty.get(HomeGroup, hal.home_group_id)
    assert harbour is not None and (harbour.church_id, harbour.leader_id) == (hope.id, hal.id)

    for person, password in (
        (ray, OWNER_PASSWORD),
        (lena, LEADER_PASSWORD),
        (ada, ADMIN_PASSWORD),
        (hal, LEADER_PASSWORD),
    ):
        assert person.password_hash is not None and person.password_hash != password
        assert verify_password(person.password_hash, password)
        assert person.must_change_password is True
        assert person.status_set_by_id is None  # set by the operators, not by a person
        history = empty.scalars(
            select(StatusChange).where(StatusChange.person_id == person.id)
        ).all()
        assert [(h.from_status, h.to_status, h.kind, h.changed_by_id) for h in history] == [
            (None, person.status, "operator", None)
        ]


@pytest.mark.db
def test_a_set_up_database_that_matches_the_file_starts(empty: Session) -> None:
    applied(empty)
    config = parse(json.dumps(config_data()))
    assert apply_or_check(empty, config, environment="ci") == "matches"
    # Names, mobile numbers and passwords change in the app: they are not compared.
    lena = empty.scalars(select(Person).where(Person.email == "lena@example.com")).one()
    lena.full_name = "Lena Renamed"
    empty.flush()
    assert apply_or_check(empty, config, environment="ci") == "matches"


@pytest.mark.db
def test_a_set_up_database_that_differs_from_the_file_does_not_start(empty: Session) -> None:
    people = applied(empty)
    harbour = empty.get(HomeGroup, people["hal@example.com"].home_group_id)
    assert harbour is not None
    harbour.name = "Renamed"
    empty.flush()
    data = config_data()
    data["owner"]["email"] = "lena@example.com"
    data["organisations"][0]["admin"].update(
        email="lena@example.com", name="Lena Leader", mobile="+971500000002"
    )
    data["organisations"][0]["homegroups"][0]["verifier"].pop("password")
    with pytest.raises(InitialConfigError) as caught:
        apply_or_check(empty, parse(json.dumps(data)), environment="ci")
    message = str(caught.value)
    assert "the OWNER is someone else" in message
    assert "'Fellowship Example' has another ADMIN" in message
    assert "has no open home group 'Harbour'" in message
    assert "Update the file (or remove it)" in message
    assert "@" not in message


@pytest.mark.db
def test_a_database_set_up_without_the_file_does_not_match_it(empty: Session) -> None:
    from tests.trust_helpers import World

    World(empty)
    with pytest.raises(InitialConfigError, match="the OWNER is someone else"):
        apply_or_check(empty, parse(json.dumps(config_data())), environment="ci")


# --- at start-up ----------------------------------------------------------------------------------


def _settings(path: str) -> Any:
    return get_settings().model_copy(update={"initial_config_path": path})


def test_no_file_configured_or_found_means_no_initial_config(tmp_path: Path) -> None:
    def no_database() -> Session:
        raise AssertionError("the database is not needed")

    assert initial_config.run_at_startup(_settings(""), no_database) == "no_file"
    missing = str(tmp_path / "initial.json")
    assert initial_config.run_at_startup(_settings(missing), no_database) == "no_file"


def test_a_file_that_is_not_valid_stops_the_start_up(tmp_path: Path) -> None:
    path = tmp_path / "initial.json"
    path.write_text('{"owner": {}}')
    with pytest.raises(InitialConfigError):
        initial_config.run_at_startup(_settings(str(path)), lambda: None)  # type: ignore[arg-type, return-value]


@pytest.mark.db
def test_start_up_applies_the_file_then_checks_it(empty: Session, tmp_path: Path) -> None:
    path = tmp_path / "initial.json"
    path.write_text(json.dumps(config_data()))
    factory = lambda: nullcontext(empty)  # noqa: E731
    settings = _settings(str(path))
    assert initial_config.run_at_startup(settings, factory) == "applied"  # type: ignore[arg-type]
    check_rules(empty)
    assert initial_config.run_at_startup(settings, factory) == "matches"  # type: ignore[arg-type]


def test_the_file_is_kept_out_of_git_and_out_of_the_image() -> None:
    repo = BACKEND_DIR.parent
    assert "initial.json" in (repo / ".gitignore").read_text().splitlines()
    assert "initial.json" in (BACKEND_DIR / ".dockerignore").read_text().splitlines()


# --- the temporary password -----------------------------------------------------------------------


def sign_in(client: TestClient, email: str, password: str) -> dict[str, str]:
    response = client.post(f"{API}/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    tokens: dict[str, str] = response.json()
    return tokens


def bearer(tokens: dict[str, str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {tokens['access_token']}"}


@pytest.mark.db
def test_a_temporary_password_opens_only_me_and_changing_it(
    client: TestClient, empty: Session
) -> None:
    applied(empty)
    tokens = sign_in(client, "ray@example.com", OWNER_PASSWORD)
    me = client.get(f"{API}/me", headers=bearer(tokens))
    assert me.status_code == 200
    assert me.json()["must_change_password"] is True and me.json()["status"] == "owner"

    for (method, path), level in sorted(MATRIX.items()):
        if level == PUBLIC or path in ("/me", "/auth/change-password"):
            continue
        response = request(client, method, path, bearer(tokens))
        assert response.status_code == 403, (method, path, response.status_code)
        assert code_of(response) == "password_change_required", (method, path)


@pytest.mark.db
def test_chat_is_closed_until_the_password_is_changed(empty: Session) -> None:
    owner = applied(empty)["ray@example.com"]
    factory = lambda: nullcontext(empty)  # noqa: E731
    assert load_who(factory, owner.id) is None  # type: ignore[arg-type]
    owner.must_change_password = False
    empty.flush()
    assert load_who(factory, owner.id) is not None  # type: ignore[arg-type]


@pytest.mark.db
def test_changing_the_temporary_password_opens_the_app(client: TestClient, empty: Session) -> None:
    applied(empty)
    tokens = sign_in(client, "lena@example.com", LEADER_PASSWORD)
    other_session = sign_in(client, "lena@example.com", LEADER_PASSWORD)
    url = f"{API}/auth/change-password"
    new_password = secrets.token_urlsafe(16)

    wrong = client.post(
        url,
        headers=bearer(tokens),
        json={
            "current_password": WRONG_PASSWORD,
            "new_password": new_password,
        },
    )
    assert (wrong.status_code, code_of(wrong)) == (403, "invalid_password")
    same = client.post(
        url,
        headers=bearer(tokens),
        json={"current_password": LEADER_PASSWORD, "new_password": LEADER_PASSWORD},
    )
    assert (same.status_code, code_of(same)) == (422, "same_password")
    short = client.post(
        url, headers=bearer(tokens), json={"current_password": LEADER_PASSWORD, "new_password": "x"}
    )
    assert short.status_code == 422

    changed = client.post(
        url,
        headers=bearer(tokens),
        json={"current_password": LEADER_PASSWORD, "new_password": new_password},
    )
    assert changed.status_code == 200, changed.text
    fresh = changed.json()
    assert fresh["access_token"] and fresh["refresh_token"]

    me = client.get(f"{API}/me", headers=bearer(fresh))
    assert me.json()["must_change_password"] is False
    assert client.get(f"{API}/me/notifications", headers=bearer(fresh)).status_code == 200
    # The other sessions end: the temporary password may be known to whoever wrote the file.
    for old in (tokens, other_session):
        refused = client.post(f"{API}/auth/refresh", json={"refresh_token": old["refresh_token"]})
        assert refused.status_code == 401
    # The temporary password no longer works; the new one does.
    assert (
        client.post(
            f"{API}/auth/login", json={"email": "lena@example.com", "password": LEADER_PASSWORD}
        ).status_code
        == 401
    )
    sign_in(client, "lena@example.com", new_password)


@pytest.mark.db
def test_a_password_reset_also_replaces_the_temporary_password(
    client: TestClient, empty: Session, caplog: pytest.LogCaptureFixture
) -> None:
    hal = applied(empty)["hal@example.com"]
    caplog.set_level("INFO", logger="app.services.auth")
    assert (
        client.post(f"{API}/auth/forgot-password", json={"email": "hal@example.com"}).status_code
        == 202
    )
    link = next(r for r in caplog.records if hasattr(r, "reset_link")).reset_link  # type: ignore[attr-defined]
    token = link.split("token=")[1]
    new_password = secrets.token_urlsafe(16)
    response = client.post(
        f"{API}/auth/reset-password", json={"token": token, "new_password": new_password}
    )
    assert response.status_code == 204
    empty.refresh(hal)
    assert hal.must_change_password is False
