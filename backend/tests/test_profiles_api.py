"""Profiles, labels, unavailability, vouching and ratings over HTTP."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.api_helpers import API, signup


def period(start_days: int, end_days: int) -> dict[str, str]:
    now = datetime.now(UTC)
    return {
        "unavailable_from": (now + timedelta(days=start_days)).isoformat(),
        "unavailable_to": (now + timedelta(days=end_days)).isoformat(),
    }


# ---- freelancer profile -------------------------------------------------------------------


def test_old_roles_are_enforced_on_their_own_endpoints(
    client: TestClient, session: Session
) -> None:
    me = signup(client, session, "freelancer", "f0@example.com")
    assert client.get(f"{API}/workhosts/me", headers=me.headers).status_code == 403
    assert client.get(f"{API}/organisations/me", headers=me.headers).status_code == 403


# ---- labels -------------------------------------------------------------------------------


# ---- unavailability -----------------------------------------------------------------------


# ---- vouching -----------------------------------------------------------------------------


def test_organisation_directory(client: TestClient, session: Session) -> None:
    signup(client, session, "organisation", "o20@example.com", org_name="Beta Training")
    signup(client, session, "organisation", "o21@example.com", org_name="Acme Training")
    signup(client, session, "organisation", "o22@example.com", org_name="Waiting", approved=False)
    host = signup(client, session, "workhost", "h20@example.com")
    freelancer = signup(client, session, "freelancer", "f20@example.com")

    listing = client.get(f"{API}/organisations", headers=host.headers)
    assert listing.status_code == 200
    names = [item["org_name"] for item in listing.json()]
    assert names == ["Acme Training", "Beta Training"]  # approved only, by name
    assert set(listing.json()[0]) == {"id", "org_name"}  # no contact details

    assert client.get(f"{API}/organisations", headers=freelancer.headers).status_code == 403
    assert client.get(f"{API}/organisations").status_code == 401


def test_vouch_lifecycle(client: TestClient, session: Session) -> None:
    freelancer = signup(client, session, "freelancer", "f8@example.com", full_name="Fatima Khan")
    org = signup(client, session, "organisation", "o1@example.com", org_name="Acme")
    link = f"{API}/organisations/me/freelancers/{freelancer.id}"

    created = client.post(link, headers=org.headers)
    assert created.status_code == 201
    assert created.json()["status"] == "pending"
    assert client.post(link, headers=org.headers).status_code == 409

    vouches = client.get(f"{API}/freelancers/me/vouches", headers=freelancer.headers).json()
    assert [(v["org_name"], v["status"]) for v in vouches] == [("Acme", "pending")]
    accept = f"{API}/freelancers/me/vouches/{org.id}/accept"
    assert client.post(accept, headers=freelancer.headers).json()["status"] == "approved"
    assert client.post(accept, headers=freelancer.headers).status_code == 409

    listing = client.get(f"{API}/organisations/me/freelancers", headers=org.headers).json()
    assert listing["total"] == 1
    assert listing["items"][0]["status"] == "approved"
    assert listing["items"][0]["full_name"] == "Fatima Khan"
    assert listing["items"][0]["is_active"] is True

    assert client.delete(link, headers=org.headers).status_code == 204
    revoked = client.get(f"{API}/organisations/me/freelancers", headers=org.headers).json()
    assert revoked["items"][0]["is_active"] is False

    again = client.post(link, headers=org.headers)  # vouching again starts over
    assert again.status_code == 201
    assert again.json()["status"] == "pending"


def test_freelancer_can_reject_a_vouch(client: TestClient, session: Session) -> None:
    freelancer = signup(client, session, "freelancer", "f9@example.com")
    org = signup(client, session, "organisation", "o2@example.com")
    client.post(f"{API}/organisations/me/freelancers/{freelancer.id}", headers=org.headers)
    reject = f"{API}/freelancers/me/vouches/{org.id}/reject"
    assert client.post(reject, headers=freelancer.headers).json()["status"] == "revoked"
    unknown = f"{API}/freelancers/me/vouches/{freelancer.id}/accept"
    assert client.post(unknown, headers=freelancer.headers).status_code == 404


def test_vouch_rules(client: TestClient, session: Session) -> None:
    freelancer = signup(client, session, "freelancer", "f10@example.com")
    pending_org = signup(client, session, "organisation", "o3@example.com", approved=False)
    assert pending_org.headers == {}  # cannot even log in until approved
    approved = signup(client, session, "organisation", "o4@example.com")
    missing = f"{API}/organisations/me/freelancers/00000000-0000-4000-8000-000000000000"
    assert client.post(missing, headers=approved.headers).status_code == 404
    assert client.delete(missing, headers=approved.headers).status_code == 404
    other = f"{API}/organisations/me/freelancers/{freelancer.id}"
    assert client.post(other, headers=freelancer.headers).status_code == 403


# ---- ratings and public profile -----------------------------------------------------------


# ---- work host and organisation profiles --------------------------------------------------


def test_workhost_profile_and_days(client: TestClient, session: Session) -> None:
    host = signup(client, session, "workhost", "h6@example.com")
    body = {"mobile_number": "+971509999999", "available_days": ["mon", "wed", "sat"]}
    assert client.put(f"{API}/workhosts/me", json=body, headers=host.headers).status_code == 200
    got = client.get(f"{API}/workhosts/me", headers=host.headers).json()
    assert got["available_days"] == ["mon", "wed", "sat"]
    bad = {**body, "available_days": ["funday"]}
    assert client.put(f"{API}/workhosts/me", json=bad, headers=host.headers).status_code == 422


def test_organisation_profile(client: TestClient, session: Session) -> None:
    org = signup(client, session, "organisation", "o6@example.com")
    body = {"org_name": "New Name Ltd", "mobile_number": "+971508888888"}
    response = client.put(f"{API}/organisations/me", json=body, headers=org.headers)
    assert response.status_code == 200
    assert response.json()["org_name"] == "New Name Ltd"
    assert response.json()["approval_status"] == "approved"
