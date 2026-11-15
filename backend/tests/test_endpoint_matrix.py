"""Every endpoint against the permission matrix (S5.13).

The table below is the contract of `docs/specification/04-api.md`, written out by hand: the
lowest status that may call each endpoint. Three things are checked:

1. every endpoint of the API is in the table, so a new one cannot ship without a decision about
   who may call it;
2. nobody without a token, and nobody below the lowest status, gets past the status check;
3. everybody at or above it does (the call may still fail for another reason, such as an unknown
   id or a body that is not valid, but never because of who is calling).
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import Principal, create_access_token
from app.main import app
from app.models.enums import STATUS_RANK
from tests.test_person_auth import add_member
from tests.trust_helpers import World

pytestmark = pytest.mark.db

PUBLIC = "public"  # no token at all
ANY = "any"  # any person with a valid token, even a revoked one (`GET /me`)
# Otherwise the lowest status: pending, searcher, provider, verifier, admin or owner. A revoked
# person is refused by every one of these.

MATRIX: dict[tuple[str, str], str] = {
    # ---- public -----------------------------------------------------------------------------
    ("POST", "/admin-invitations/accept"): PUBLIC,
    ("POST", "/admin-invitations/lookup"): PUBLIC,
    ("GET", "/app/config"): PUBLIC,
    ("POST", "/auth/forgot-password"): PUBLIC,
    ("POST", "/auth/login"): PUBLIC,
    ("POST", "/auth/logout"): PUBLIC,
    ("POST", "/auth/refresh"): PUBLIC,
    ("POST", "/auth/reset-password"): PUBLIC,
    ("POST", "/auth/signup"): PUBLIC,
    ("GET", "/churches"): PUBLIC,
    ("GET", "/churches/{church_id}/home-groups"): PUBLIC,
    ("POST", "/group-invitations/lookup"): PUBLIC,
    # ---- the person's own account ------------------------------------------------------------
    ("GET", "/me"): ANY,
    ("PUT", "/me"): "pending",
    ("DELETE", "/me"): "pending",
    ("PUT", "/me/application"): "pending",
    ("GET", "/me/notifications"): "pending",
    ("POST", "/me/notifications/read-all"): "pending",
    ("POST", "/me/notifications/{notification_id}/read"): "pending",
    ("GET", "/me/vouch-link"): "pending",
    ("POST", "/me/vouch-link"): "pending",
    ("GET", "/me/vouches"): "pending",
    ("GET", "/app/downloads"): "pending",
    ("GET", "/app/downloads/android/{version}"): "pending",
    # ---- a SEARCHER or above -------------------------------------------------------------------
    ("GET", "/me/vouches-given"): "searcher",
    ("POST", "/me/apply-provider"): "searcher",
    ("GET", "/group-requests"): "searcher",
    ("POST", "/group-requests"): "searcher",
    ("GET", "/move-requests"): "searcher",
    ("POST", "/move-requests"): "searcher",
    ("POST", "/move-requests/{request_id}/agree"): "searcher",
    ("POST", "/move-requests/{request_id}/cancel"): "searcher",
    ("POST", "/vouch-links/lookup"): "searcher",
    ("POST", "/vouch-links/vouch"): "searcher",
    ("DELETE", "/vouches/{vouch_id}"): "searcher",
    ("GET", "/freelancers/{freelancer_id}"): "searcher",
    ("GET", "/freelancers/{freelancer_id}/ratings"): "searcher",
    ("POST", "/freelancers/{freelancer_id}/reveal-mobile"): "searcher",
    ("POST", "/ratings"): "searcher",
    ("PUT", "/ratings/{rating_id}"): "searcher",
    ("GET", "/search/freelancers"): "searcher",
    ("GET", "/labels"): "searcher",
    ("GET", "/workhosts/me/ratings"): "searcher",
    # ---- a PROVIDER or above -------------------------------------------------------------------
    ("GET", "/freelancers/me"): "provider",
    ("PUT", "/freelancers/me"): "provider",
    ("PUT", "/freelancers/me/labels"): "provider",
    ("GET", "/freelancers/me/unavailability"): "provider",
    ("POST", "/freelancers/me/unavailability"): "provider",
    ("PUT", "/freelancers/me/unavailability/{period_id}"): "provider",
    ("DELETE", "/freelancers/me/unavailability/{period_id}"): "provider",
    # ---- a VERIFIER or above (within their scope) -------------------------------------------
    ("GET", "/verifier/applicants"): "verifier",
    ("GET", "/verifier/members"): "verifier",
    ("GET", "/verifier/revoked"): "verifier",
    ("GET", "/verifier/flagged"): "verifier",
    ("GET", "/verifier/people/{person_id}"): "verifier",
    ("POST", "/verifier/people/{person_id}/admit"): "verifier",
    ("POST", "/verifier/people/{person_id}/decline"): "verifier",
    ("PUT", "/verifier/people/{person_id}/status"): "verifier",
    ("POST", "/verifier/people/{person_id}/reconfirm"): "verifier",
    ("GET", "/verifier/group-invitations"): "verifier",
    ("POST", "/verifier/group-invitations"): "verifier",
    ("DELETE", "/verifier/group-invitations/{invitation_id}"): "verifier",
    ("POST", "/home-groups/{group_id}/close"): "verifier",
    # ---- an ADMIN or above ---------------------------------------------------------------------
    ("POST", "/verifier/people/{person_id}/move"): "admin",
    ("PUT", "/home-groups/{group_id}/leader"): "admin",
    ("POST", "/group-requests/{request_id}/approve"): "admin",
    ("POST", "/group-requests/{request_id}/decline"): "admin",
    ("GET", "/reports"): "admin",
    ("GET", "/reports/{name}"): "admin",
    ("GET", "/owner/handover"): "admin",
    ("POST", "/owner/handover/{request_id}/accept"): "admin",
    ("POST", "/owner/handover/{request_id}/cancel"): "admin",
    # ---- the OWNER -----------------------------------------------------------------------------
    ("PUT", "/churches/{church_id}/admin"): "owner",
    ("GET", "/owner/churches"): "owner",
    ("POST", "/owner/churches"): "owner",
    ("GET", "/owner/churches/invitations"): "owner",
    ("DELETE", "/owner/churches/invitations/{invitation_id}"): "owner",
    ("POST", "/owner/churches/{church_id}/close"): "owner",
    ("GET", "/owner/contact-views"): "owner",
    ("POST", "/owner/handover"): "owner",
    ("POST", "/labels"): "owner",
    ("PATCH", "/labels/{label_id}"): "owner",
    ("POST", "/reports/{name}/run"): "owner",
    ("GET", "/reports/runs"): "owner",
    ("GET", "/reports/runs/{run_id}/download"): "owner",
    ("GET", "/reports/schedules"): "owner",
    ("PUT", "/reports/schedules/{report_name}"): "owner",
}

# Answers that mean "you may not": the check on the caller, not on what was asked.
REFUSALS = {"not_admitted", "account_revoked", "forbidden", "not_authenticated", "invalid_token"}

# Health checks are not part of the versioned API.
UNVERSIONED = {("GET", "/health"), ("GET", "/health/ready")}

STATUSES = ("revoked", "pending", "searcher", "provider", "verifier", "admin", "owner")


def operations() -> set[tuple[str, str]]:
    found: set[tuple[str, str]] = set()
    for path, item in app.openapi()["paths"].items():
        for method in item:
            if method in {"get", "post", "put", "patch", "delete"}:
                found.add((method.upper(), path.removeprefix("/api/v1")))
    return found


def test_every_endpoint_is_in_the_matrix_and_nothing_else() -> None:
    found = operations() - UNVERSIONED
    assert found - set(MATRIX) == set(), "an endpoint has no entry in the permission matrix"
    assert set(MATRIX) - found == set(), "the matrix names an endpoint that does not exist"


def test_the_matrix_uses_known_levels_only() -> None:
    assert set(MATRIX.values()) <= {PUBLIC, ANY, *STATUSES}


@pytest.fixture
def callers(session: Session) -> dict[str, dict[str, str]]:
    """One person of every status, as the Authorization header each would send."""
    world = World(session)
    people = {
        "revoked": add_member(world, "revoked").person,
        "pending": add_member(world, "pending").person,
        "searcher": add_member(world, "searcher").person,
        "provider": add_member(world, "provider").person,
        "verifier": add_member(world, "verifier").person,
        "admin": world.add_church("Matrix church")[2],
        "owner": world.owner,
    }
    secret = get_settings().require_jwt_secret()
    headers = {}
    for status, person in people.items():
        token, _ = create_access_token(
            Principal(person.id),
            secret=secret,
            lifetime_minutes=5,
            now=datetime.now(UTC) - timedelta(seconds=1),
        )
        headers[status] = {"Authorization": f"Bearer {token}"}
    return headers


def request(client: TestClient, method: str, path: str, headers: dict[str, str]):  # type: ignore[no-untyped-def]
    """The call with ids that do not exist and a body that is not valid, so that a call which is
    let through changes nothing (it answers 404 or 422)."""
    ghost = str(uuid.uuid4())
    url = "/api/v1" + path
    for name in (
        "church_id",
        "group_id",
        "request_id",
        "person_id",
        "invitation_id",
        "run_id",
        "label_id",
        "vouch_id",
        "period_id",
        "rating_id",
        "notification_id",
        "freelancer_id",
    ):
        url = url.replace("{" + name + "}", ghost)
    url = url.replace("{version}", "9.9.9").replace("{name}", "no_such_report")
    url = url.replace("{report_name}", "no_such_report")
    if method == "GET" or method == "DELETE" and "/me" not in path:
        return client.request(method, url, headers=headers)
    return client.request(method, url, headers=headers, json={})


def code_of(response) -> str:  # type: ignore[no-untyped-def]
    try:
        return str(response.json()["error"]["code"])
    except (ValueError, KeyError, TypeError):
        return ""


@pytest.mark.parametrize(
    ("method", "path"), sorted(k for k, level in MATRIX.items() if level != PUBLIC)
)
def test_who_may_call(
    client: TestClient, callers: dict[str, dict[str, str]], method: str, path: str
) -> None:
    level = MATRIX[(method, path)]
    no_token = request(client, method, path, {})
    assert no_token.status_code == 401, (method, path, "needs a token")
    for status in STATUSES:
        response = request(client, method, path, callers[status])
        if level == ANY:
            allowed = True
        else:
            allowed = status != "revoked" and STATUS_RANK[status] >= STATUS_RANK[level]
        refused = response.status_code in (401, 403) and code_of(response) in REFUSALS
        if allowed:
            assert not refused, (method, path, status, response.status_code, code_of(response))
        else:
            assert response.status_code == 403, (method, path, status, response.status_code)
            assert code_of(response) in REFUSALS, (method, path, status, code_of(response))


@pytest.mark.parametrize(
    ("method", "path"), sorted(k for k, level in MATRIX.items() if level == PUBLIC)
)
def test_public_endpoints_need_no_token(client: TestClient, method: str, path: str) -> None:
    response = request(client, method, path, {})
    assert response.status_code != 401, (method, path)
    assert code_of(response) not in {"not_authenticated", "invalid_token"}, (method, path)
