"""Profiles, labels, unavailability, vouching and ratings over HTTP."""

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from tests.api_helpers import API, label_id, signup


def period(start_days: int, end_days: int) -> dict[str, str]:
    now = datetime.now(UTC)
    return {
        "unavailable_from": (now + timedelta(days=start_days)).isoformat(),
        "unavailable_to": (now + timedelta(days=end_days)).isoformat(),
    }


# ---- freelancer profile -------------------------------------------------------------------


def test_freelancer_updates_own_profile(client: TestClient, session: Session) -> None:
    me = signup(client, session, "freelancer", "f1@example.com")
    body = {
        "mobile_number": "+971 50 123 4567",
        "whatsapp_availability": True,
        "nationality": "Indian",
        "primary_language": "Hindi",
        "rate_per_hour": 45.5,
        "rate_currency": "AED",
        "is_rate_negotiable": True,
    }
    response = client.put(f"{API}/freelancers/me", json=body, headers=me.headers)
    assert response.status_code == 200
    assert response.json()["mobile_number"] == "+971501234567"
    assert response.json()["rate_per_hour"] == 45.5
    assert client.get(f"{API}/freelancers/me", headers=me.headers).json()["rate_currency"] == "AED"


def test_names_can_be_edited_and_are_shown_to_the_right_people(
    client: TestClient, session: Session
) -> None:
    freelancer = signup(client, session, "freelancer", "named.f@example.com", full_name="Old Name")
    host = signup(client, session, "workhost", "named.h@example.com", full_name="Host Person")
    base = {"mobile_number": "+971501234567"}

    renamed = client.put(
        f"{API}/freelancers/me", json={**base, "full_name": "  New Name "}, headers=freelancer.headers
    )
    assert renamed.json()["full_name"] == "New Name"
    kept = client.put(f"{API}/freelancers/me", json=base, headers=freelancer.headers)
    assert kept.json()["full_name"] == "New Name"  # omitted means unchanged
    too_short = {**base, "full_name": "A"}
    assert (
        client.put(f"{API}/freelancers/me", json=too_short, headers=freelancer.headers).status_code
        == 422
    )

    public = client.get(f"{API}/freelancers/{freelancer.id}", headers=host.headers).json()
    assert public["full_name"] == "New Name"
    assert "email" not in public

    renamed_host = client.put(
        f"{API}/workhosts/me", json={**base, "full_name": "Host Renamed"}, headers=host.headers
    )
    assert renamed_host.json()["full_name"] == "Host Renamed"


def test_rate_needs_a_valid_currency(client: TestClient, session: Session) -> None:
    me = signup(client, session, "freelancer", "f2@example.com")
    base = {"mobile_number": "+971501234567"}
    for extra in (
        {"rate_per_hour": 10},  # no currency
        {"rate_currency": "AED"},  # no rate
        {"rate_per_hour": 10, "rate_currency": "aed"},  # not capitals
        {"rate_per_hour": -1, "rate_currency": "AED"},  # negative
    ):
        response = client.put(f"{API}/freelancers/me", json={**base, **extra}, headers=me.headers)
        assert response.status_code == 422, extra


def test_roles_are_enforced_on_own_profile_endpoints(client: TestClient, session: Session) -> None:
    host = signup(client, session, "workhost", "h0@example.com")
    assert client.get(f"{API}/freelancers/me", headers=host.headers).status_code == 403
    assert client.get(f"{API}/freelancers/me").status_code == 401
    me = signup(client, session, "freelancer", "f0@example.com")
    assert client.get(f"{API}/workhosts/me", headers=me.headers).status_code == 403
    assert client.get(f"{API}/organisations/me", headers=me.headers).status_code == 403


# ---- labels -------------------------------------------------------------------------------


def test_labels_with_skill_levels(client: TestClient, session: Session) -> None:
    me = signup(client, session, "freelancer", "f3@example.com")
    plumbing = label_id(session, "skill", "plumbing")
    basic = label_id(session, "skill_level", "basic")
    english = label_id(session, "language", "English")
    body = {
        "labels": [
            {"label_id": plumbing, "level_label_id": basic},
            {"label_id": english},
        ]
    }
    response = client.put(f"{API}/freelancers/me/labels", json=body, headers=me.headers)
    assert response.status_code == 200
    by_name = {item["label"]["label_name"]: item for item in response.json()}
    assert by_name["plumbing"]["level"]["label_name"] == "basic"
    assert by_name["English"]["level"] is None

    # PUT replaces the whole set.
    only_english = {"labels": [{"label_id": english}]}
    again = client.put(f"{API}/freelancers/me/labels", json=only_english, headers=me.headers)
    assert [item["label"]["label_name"] for item in again.json()] == ["English"]
    assert len(client.get(f"{API}/freelancers/me", headers=me.headers).json()["labels"]) == 1


def test_invalid_label_selections_are_rejected(client: TestClient, session: Session) -> None:
    me = signup(client, session, "freelancer", "f4@example.com")
    plumbing = label_id(session, "skill", "plumbing")
    basic = label_id(session, "skill_level", "basic")
    english = label_id(session, "language", "English")
    url = f"{API}/freelancers/me/labels"
    bad_bodies = {
        "level on a language": [{"label_id": english, "level_label_id": basic}],
        "level is not a level": [{"label_id": plumbing, "level_label_id": english}],
        "skill level on its own": [{"label_id": basic}],
        "duplicate": [{"label_id": english}, {"label_id": english}],
        "unknown label": [{"label_id": "00000000-0000-4000-8000-000000000000"}],
    }
    for name, labels in bad_bodies.items():
        response = client.put(url, json={"labels": labels}, headers=me.headers)
        assert response.status_code == 422, name


def test_admin_manages_labels(client: TestClient, session: Session) -> None:
    admin = signup(client, session, "admin", "boss@example.com")
    host = signup(client, session, "workhost", "h1@example.com")
    body = {"label_name": "carpentry", "label_type": "skill"}
    assert client.post(f"{API}/labels", json=body, headers=host.headers).status_code == 403
    created = client.post(f"{API}/labels", json=body, headers=admin.headers)
    assert created.status_code == 201
    assert client.post(f"{API}/labels", json=body, headers=admin.headers).status_code == 409

    skills = client.get(f"{API}/labels?type=skill", headers=host.headers).json()
    assert "carpentry" in [label["label_name"] for label in skills]
    assert all(label["label_type"] == "skill" for label in skills)

    label_url = f"{API}/labels/{created.json()['id']}"
    renamed = client.patch(label_url, json={"label_name": "joinery"}, headers=admin.headers)
    assert renamed.json()["label_name"] == "joinery"
    client.patch(label_url, json={"is_active": False}, headers=admin.headers)
    listed = client.get(f"{API}/labels", headers=host.headers).json()
    names = [label["label_name"] for label in listed]
    assert "joinery" not in names
    inactive = client.get(f"{API}/labels?include_inactive=true", headers=admin.headers).json()
    assert "joinery" in [label["label_name"] for label in inactive]


# ---- unavailability -----------------------------------------------------------------------


def test_unavailability_crud_and_overlap(client: TestClient, session: Session) -> None:
    me = signup(client, session, "freelancer", "f5@example.com")
    url = f"{API}/freelancers/me/unavailability"
    first = client.post(url, json=period(1, 5), headers=me.headers)
    assert first.status_code == 201
    assert client.post(url, json=period(3, 7), headers=me.headers).status_code == 409
    second = client.post(url, json=period(10, 12), headers=me.headers)
    assert second.status_code == 201

    updated = client.put(f"{url}/{first.json()['id']}", json=period(1, 6), headers=me.headers)
    assert updated.status_code == 200
    clash = client.put(f"{url}/{first.json()['id']}", json=period(9, 11), headers=me.headers)
    assert clash.status_code == 409

    assert len(client.get(url, headers=me.headers).json()) == 2
    assert client.delete(f"{url}/{second.json()['id']}", headers=me.headers).status_code == 204
    assert len(client.get(url, headers=me.headers).json()) == 1


def test_unavailability_validation_and_ownership(client: TestClient, session: Session) -> None:
    mine = signup(client, session, "freelancer", "f6@example.com")
    other = signup(client, session, "freelancer", "f7@example.com")
    url = f"{API}/freelancers/me/unavailability"
    assert client.post(url, json=period(5, 1), headers=mine.headers).status_code == 422
    naive = {"unavailable_from": "2030-01-01T00:00:00", "unavailable_to": "2030-01-02T00:00:00"}
    assert client.post(url, json=naive, headers=mine.headers).status_code == 422

    created = client.post(url, json=period(1, 2), headers=mine.headers).json()
    assert client.delete(f"{url}/{created['id']}", headers=other.headers).status_code == 404
    foreign = client.put(f"{url}/{created['id']}", json=period(1, 3), headers=other.headers)
    assert foreign.status_code == 404


# ---- vouching -----------------------------------------------------------------------------


def test_vouch_lifecycle(client: TestClient, session: Session) -> None:
    freelancer = signup(client, session, "freelancer", "f8@example.com")
    org = signup(client, session, "organisation", "o1@example.com", org_name="Acme")
    host = signup(client, session, "workhost", "h2@example.com")
    link = f"{API}/organisations/me/freelancers/{freelancer.id}"

    created = client.post(link, headers=org.headers)
    assert created.status_code == 201
    assert created.json()["status"] == "pending"
    assert client.post(link, headers=org.headers).status_code == 409

    # Pending vouches are not shown publicly.
    profile_url = f"{API}/freelancers/{freelancer.id}"
    assert client.get(profile_url, headers=host.headers).json()["vouched_by"] == []

    vouches = client.get(f"{API}/freelancers/me/vouches", headers=freelancer.headers).json()
    assert [(v["org_name"], v["status"]) for v in vouches] == [("Acme", "pending")]
    accept = f"{API}/freelancers/me/vouches/{org.id}/accept"
    assert client.post(accept, headers=freelancer.headers).json()["status"] == "approved"
    assert client.post(accept, headers=freelancer.headers).status_code == 409

    shown = client.get(profile_url, headers=host.headers).json()["vouched_by"]
    assert [v["org_name"] for v in shown] == ["Acme"]
    listing = client.get(f"{API}/organisations/me/freelancers", headers=org.headers).json()
    assert listing["total"] == 1
    assert listing["items"][0]["status"] == "approved"
    assert listing["items"][0]["is_active"] is True

    assert client.delete(link, headers=org.headers).status_code == 204
    assert client.get(profile_url, headers=host.headers).json()["vouched_by"] == []
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


def test_rating_flow(client: TestClient, session: Session) -> None:
    freelancer = signup(client, session, "freelancer", "f11@example.com")
    host_a = signup(client, session, "workhost", "ha@example.com")
    host_b = signup(client, session, "workhost", "hb@example.com")
    body = {"freelancer_id": str(freelancer.id), "rating": 8, "comment": "Great"}

    assert client.post(f"{API}/ratings", json=body, headers=freelancer.headers).status_code == 403
    first = client.post(f"{API}/ratings", json=body, headers=host_a.headers)
    assert first.status_code == 201
    assert client.post(f"{API}/ratings", json=body, headers=host_a.headers).status_code == 409
    client.post(f"{API}/ratings", json={**body, "rating": 4}, headers=host_b.headers)

    profile = client.get(f"{API}/freelancers/{freelancer.id}", headers=host_a.headers).json()
    assert profile["average_rating"] == 6.0
    assert profile["rating_count"] == 2

    rating_url = f"{API}/ratings/{first.json()['id']}"
    changed = client.put(rating_url, json={"rating": 10, "comment": None}, headers=host_a.headers)
    assert changed.status_code == 200
    assert changed.json()["rating"] == 10
    assert client.put(rating_url, json={"rating": 1}, headers=host_b.headers).status_code == 404

    page = client.get(f"{API}/freelancers/{freelancer.id}/ratings", headers=freelancer.headers)
    assert page.json()["total"] == 2
    assert all(set(item) == {"rating", "comment", "rated_on"} for item in page.json()["items"])
    mine = client.get(f"{API}/workhosts/me/ratings", headers=host_a.headers).json()
    assert mine["total"] == 1


def test_rating_validation(client: TestClient, session: Session) -> None:
    freelancer = signup(client, session, "freelancer", "f12@example.com")
    host = signup(client, session, "workhost", "h3@example.com")
    for bad in (0, 11):
        body = {"freelancer_id": str(freelancer.id), "rating": bad}
        assert client.post(f"{API}/ratings", json=body, headers=host.headers).status_code == 422
    unknown = {"freelancer_id": "00000000-0000-4000-8000-000000000000", "rating": 5}
    assert client.post(f"{API}/ratings", json=unknown, headers=host.headers).status_code == 404


def test_public_profile_privacy(client: TestClient, session: Session) -> None:
    freelancer = signup(client, session, "freelancer", "secret.person@example.com")
    host = signup(client, session, "workhost", "h4@example.com")
    org = signup(client, session, "organisation", "o5@example.com")
    other_freelancer = signup(client, session, "freelancer", "f13@example.com")
    url = f"{API}/freelancers/{freelancer.id}"

    for_host = client.get(url, headers=host.headers)
    assert for_host.status_code == 200
    assert for_host.json()["mobile_number"] is not None
    assert "secret.person" not in for_host.text
    assert "email" not in for_host.json()
    assert client.get(url, headers=org.headers).json()["mobile_number"] is None
    assert client.get(url, headers=other_freelancer.headers).status_code == 403
    assert client.get(url).status_code == 401
    missing = f"{API}/freelancers/00000000-0000-4000-8000-000000000000"
    assert client.get(missing, headers=host.headers).status_code == 404


def test_public_profile_shows_upcoming_unavailability_only(
    client: TestClient, session: Session
) -> None:
    freelancer = signup(client, session, "freelancer", "f14@example.com")
    host = signup(client, session, "workhost", "h5@example.com")
    url = f"{API}/freelancers/me/unavailability"
    client.post(url, json=period(-10, -5), headers=freelancer.headers)  # in the past
    client.post(url, json=period(5, 9), headers=freelancer.headers)
    shown = client.get(f"{API}/freelancers/{freelancer.id}", headers=host.headers).json()
    assert len(shown["unavailable"]) == 1


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
