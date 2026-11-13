"""The trust journey of slice S3, through the real endpoints and a real database.

The web and the mobile app make exactly these calls (their own tests check the screens against
the same contract), so this is the check that the pieces fit: people apply, collect vouches
through their links, are admitted as searchers and providers or declined, a searcher asks to
become a provider, and everybody is told. At the end the rules of the model hold.
"""

import secrets
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1 import churches
from app.models import ContactView, Notification, Person, StatusChange, Vouch, VouchLink
from app.services import rate_limit
from app.services.operators import create_first_owner
from tests.api_helpers import API
from tests.trust_helpers import check_rules

pytestmark = pytest.mark.db


@pytest.fixture(autouse=True)
def _fresh_limiters() -> None:
    churches.limiter.reset()
    for limiter in (
        rate_limit.signup_limiter,
        rate_limit.link_lookup_limiter,
        rate_limit.vouch_attempt_limiter,
    ):
        limiter.reset()


class Who:
    """A person of the journey: how to log in, and what the API says about them."""

    def __init__(self, client: TestClient, name: str, email: str, password: str) -> None:
        self.client, self.name, self.email, self.password = client, name, email, password
        self.id = ""

    @property
    def headers(self) -> dict[str, str]:
        response = self.client.post(
            f"{API}/auth/login", json={"email": self.email, "password": self.password}
        )
        assert response.status_code == 200, response.text
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def me(self) -> dict[str, Any]:
        body: dict[str, Any] = self.client.get(f"{API}/me", headers=self.headers).json()
        self.id = body["id"]
        return body

    def get(self, path: str, **params: Any) -> Any:
        return self.client.get(f"{API}{path}", headers=self.headers, params=params)

    def post(self, path: str, **body: Any) -> Any:
        return self.client.post(f"{API}{path}", headers=self.headers, json=body or None)


def sign_up(client: TestClient, group_id: str, name: str, applies_for: str) -> Who:
    email = f"{name.lower()}-{secrets.token_hex(3)}@example.com"
    password = secrets.token_urlsafe(16)
    response = client.post(
        f"{API}/auth/signup",
        json={
            "full_name": f"{name} Person",
            "email": email,
            "mobile_number": f"+9715{secrets.randbelow(10**8):08d}",
            "password": password,
            "requested_status": applies_for,
            "home_group_id": group_id,
        },
    )
    assert response.status_code == 201, response.text
    who = Who(client, f"{name} Person", email, password)
    who.me()
    return who


def kinds(session: Session, who: Who) -> list[str]:
    """The kinds of the notifications a person has, sorted (rows made in one test transaction
    share a timestamp, so their order says nothing)."""
    rows = session.scalars(select(Notification).where(Notification.person_id == who.id))
    return sorted(n.kind for n in rows)


def test_the_trust_journey(client: TestClient, session: Session) -> None:
    # 1. Skills is set up and four people apply to the leader's group.
    owner_password = secrets.token_urlsafe(16)
    create_first_owner(
        session,
        full_name="Olive Owner",
        email="olive@example.com",
        mobile_number="+971500000300",
        password=owner_password,
        church_name="Grace Church",
        group_name="Riverside",
    )
    olive = Who(client, "Olive Owner", "olive@example.com", owner_password)
    olive.me()
    church = client.get(f"{API}/churches").json()["items"][0]
    group = client.get(f"{API}/churches/{church['id']}/home-groups").json()["items"][0]["id"]
    ann = sign_up(client, group, "Ann", "searcher")
    ben = sign_up(client, group, "Ben", "provider")
    cal = sign_up(client, group, "Cal", "searcher")
    eve = sign_up(client, group, "Eve", "searcher")
    assert kinds(session, olive) == ["applicant_new"] * 4

    # 2. The leader sees them, nobody has a vouch, and no list shows a number.
    listed = olive.get("/verifier/applicants").json()
    assert listed["total"] == 4 and all(r["status"] == "pending" for r in listed["items"])
    assert not any(r["can_admit_as_provider"] for r in listed["items"])
    for person in (ann, ben, cal, eve):
        assert person.me()["mobile_number"] not in olive.get("/verifier/applicants").text

    # 3. Applicants have nothing to do with the leader's screens, or with vouching.
    assert ann.get("/verifier/applicants").status_code == 403
    link_of_ben = ben.post("/me/vouch-link").json()
    assert ann.post("/vouch-links/vouch", token=link_of_ben["token"]).status_code == 403

    # 4. A searcher needs only the leader's own sign-off: Ann is admitted, and told.
    admitted = olive.post(f"/verifier/people/{ann.id}/admit", to="searcher")
    assert admitted.status_code == 200 and admitted.json()["status"] == "searcher"
    me = ann.me()
    assert me["status"] == "searcher" and me["status_set_by"] == {"name": "Olive Owner"}
    assert me["requested_status"] is None
    assert kinds(session, ann) == ["admitted"]

    # 4b. The leader's own vouch is their sign-off, not a second one: it does not admit a provider.
    assert olive.post("/vouch-links/vouch", token=link_of_ben["token"]).status_code == 201
    row = next(r for r in olive.get("/verifier/applicants").json()["items"] if r["id"] == ben.id)
    assert row["vouch_count"] == 1 and row["can_admit_as_provider"] is False
    refused = olive.post(f"/verifier/people/{ben.id}/admit", to="provider")
    assert refused.status_code == 409 and refused.json()["error"]["code"] == "not_enough_vouches"

    # 5. Ann vouches for Ben through his link (once); Ben is told and counts two (Olive's, Ann's).
    shown = ann.post("/vouch-links/lookup", token=link_of_ben["token"]).json()
    assert shown["applicant_name"] == ben.name and shown["requested_status"] == "provider"
    assert shown["already_vouched"] is False
    assert ann.post("/vouch-links/vouch", token=link_of_ben["token"]).status_code == 201
    assert ann.post("/vouch-links/vouch", token=link_of_ben["token"]).status_code == 409
    assert ben.me()["vouch_count"] == 2
    assert kinds(session, ben) == ["vouch_received", "vouch_received"]
    given = ann.get("/me/vouches-given").json()["items"]
    assert [(v["applicant_name"], v["can_withdraw"]) for v in given] == [(ben.name, True)]

    # 6. The leader's list puts Ben first, and says a provider can now be admitted.
    top = olive.get("/verifier/applicants").json()["items"][0]
    assert top["id"] == ben.id and top["vouch_count"] == 2 and top["can_admit_as_provider"] is True
    assert {v["name"] for v in top["vouchers"]} == {ann.name, olive.name}

    # 7. Cal's own link and Cal's vouch for Ben are refused until Cal is admitted.
    assert cal.post("/vouch-links/lookup", token=link_of_ben["token"]).status_code == 403

    # 8. Ben is admitted as a provider; the history, the link and the lists follow.
    assert olive.post(f"/verifier/people/{ben.id}/admit", to="provider").status_code == 200
    assert ben.me()["status"] == "provider" and ben.me()["vouch_count"] == 2
    assert ann.post("/vouch-links/lookup", token=link_of_ben["token"]).status_code == 404
    assert [
        c.kind
        for c in session.scalars(select(StatusChange).where(StatusChange.person_id == ben.id))
    ] == [
        "signup",
        "admit",
    ]
    assert session.scalars(select(VouchLink).where(VouchLink.person_id == ben.id)).one().revoked_at
    assert ann.get("/me/vouches-given").json()["items"][0]["can_withdraw"] is False

    # 9. A searcher asks to become a provider: Ann collects a vouch from Ben, and is admitted.
    assert ann.post("/me/apply-provider").json()["requested_status"] == "provider"
    assert "provider_application" in kinds(session, olive)
    assert olive.post(f"/verifier/people/{ann.id}/admit", to="provider").status_code == 409
    link_of_ann = ann.post("/me/vouch-link").json()
    assert ben.post("/vouch-links/vouch", token=link_of_ann["token"]).status_code == 201
    asking = next(r for r in olive.get("/verifier/applicants").json()["items"] if r["id"] == ann.id)
    assert asking["status"] == "searcher" and asking["can_admit_as_provider"] is True
    assert olive.post(f"/verifier/people/{ann.id}/admit", to="provider").status_code == 200
    changes = session.scalars(select(StatusChange).where(StatusChange.person_id == ann.id))
    assert {(c.from_status, c.to_status) for c in changes} == {
        (None, "pending"),
        ("pending", "searcher"),
        ("searcher", "provider"),
    }
    assert ann.me()["status"] == "provider" and ann.me()["requested_status"] is None

    # 10. Cal is declined and may sign up again; Eve is admitted, asks, and the request is declined.
    assert olive.post(f"/verifier/people/{cal.id}/decline").status_code == 204
    closed = client.post(f"{API}/auth/login", json={"email": cal.email, "password": cal.password})
    assert closed.status_code == 401  # the account is closed
    old_row = session.get(Person, cal.id)
    assert old_row is not None and old_row.closed_at is not None  # closed, never deleted
    # Declining is not a change of status (decision D-27): the history holds only the sign-up.
    cal_history = session.scalars(select(StatusChange).where(StatusChange.person_id == cal.id))
    assert [c.kind for c in cal_history] == ["signup"]
    new_password = secrets.token_urlsafe(16)
    again = client.post(
        f"{API}/auth/signup",
        json={
            "full_name": "Cal Again",
            "email": cal.email,
            "mobile_number": f"+9715{secrets.randbelow(10**8):08d}",
            "password": new_password,
            "requested_status": "searcher",
            "home_group_id": group,
        },
    )
    assert again.status_code == 201
    new_cal = Who(client, "Cal Again", cal.email, new_password)
    assert new_cal.me()["status"] == "pending" and new_cal.id != cal.id  # a new person
    assert olive.post(f"/verifier/people/{eve.id}/admit", to="searcher").status_code == 200
    eve.post("/me/apply-provider")
    assert olive.post(f"/verifier/people/{eve.id}/decline").status_code == 204
    assert eve.me()["status"] == "searcher" and eve.me()["requested_status"] is None
    assert kinds(session, eve) == ["admitted", "provider_declined"]

    # 11. The members' list, one person's page with the number (logged), and the chain of trust.
    members = olive.get("/verifier/members", status="provider").json()["items"]
    assert {m["full_name"] for m in members} == {ann.name, ben.name}
    assert "+9715" not in olive.get("/verifier/members").text
    before = session.scalar(select(func.count()).select_from(ContactView)) or 0
    page = olive.get(f"/verifier/people/{ann.id}").json()
    assert page["mobile_number"].startswith("+9715") and page["can_admit_as_provider"] is False
    assert [link["full_name"] for link in page["chain_of_trust"]] == ["Olive Owner"]
    assert session.scalar(select(func.count()).select_from(ContactView)) == before + 1
    view = session.scalars(select(ContactView).where(ContactView.person_id == ann.id)).one()
    assert (str(view.viewer_id), view.screen) == (olive.id, "person")
    # The lists added none: they are the only other thing the leader opened.
    assert session.scalar(select(func.count()).select_from(ContactView)) == 1

    # 12. Everybody was told what concerns them, and can mark it read.
    assert kinds(session, ann) == ["admitted", "admitted", "vouch_received"]
    assert ann.get("/me/notifications").json()["unread_count"] == 3
    assert ann.post("/me/notifications/read-all").status_code == 204
    assert ann.get("/me/notifications").json()["unread_count"] == 0

    # 13. The rules of the model hold at the end: the vouches stay on record, nobody is revoked,
    # and the database accepts the whole state.
    assert session.scalar(select(func.count()).select_from(Vouch)) == 3
    assert session.scalars(select(Person).where(Person.status == "revoked")).first() is None
    check_rules(session)
