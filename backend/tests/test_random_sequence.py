"""Random sequences of every operation of the trust model, with the rules checked after each step.

Each test case is a seed that fixes the dice: which operation, who acts and on whom. People get
random ids from the database, so a seed does not repeat a walk exactly; a failure prints the last
calls instead. A step picks an operation and its arguments at random, some sensible and
some not (a stranger, a person of another church, a closed group), and makes the real API call as
the person who would make it. A call may succeed or be refused, but it must never fail with a
server error, and after every step:

- the rules the database holds at COMMIT are checked (`check_rules`);
- the six invariants of docs/verification.md are checked again here, in plain code, over every
  person, group and church, so a hole in a database rule shows up too;
- the history of each person is a chain, and ends at their current status.

At the end every operation must have succeeded at least once over the seeds, so a test that only
ever sees refusals cannot pass.
"""

import random
import secrets
import uuid
from collections import Counter
from collections.abc import Callable
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1 import churches
from app.core.config import get_settings
from app.core.errors import ApiError
from app.core.security import Principal, create_access_token
from app.models import (
    Church,
    GroupRequest,
    HandoverRequest,
    HomeGroup,
    MoveRequest,
    Person,
    StatusChange,
    Vouch,
)
from app.services import rate_limit
from app.services.operators import SetupError, change_owner, create_first_owner
from tests.api_helpers import API
from tests.trust_helpers import check_rules

pytestmark = pytest.mark.db

SEEDS = list(range(1, 13))
STEPS = 160
HIGHER = ("verifier", "admin", "owner")
ORDER = ["revoked", "pending", "searcher", "provider", "verifier", "admin", "owner"]

# What the seeds together must have done at least once (the key is the operation's name).
succeeded: Counter[str] = Counter()


def _reset_limiters() -> None:
    churches.limiter.reset()
    for limiter in (
        rate_limit.signup_limiter,
        rate_limit.link_lookup_limiter,
        rate_limit.vouch_attempt_limiter,
    ):
        limiter.reset()


class Run:
    """One random walk: the API client, the people we can act as, and the dice."""

    def __init__(self, client: TestClient, session: Session, seed: int) -> None:
        self.client, self.session, self.rng = client, session, random.Random(seed)  # noqa: S311 - dice for a test, not a secret
        self.passwords: dict[uuid.UUID, str] = {}
        self.invitations: list[str] = []
        self.log: list[str] = []

    # ---- what exists now ---------------------------------------------------------------

    def people(self, *statuses: str) -> list[Person]:
        rows = self.session.scalars(select(Person).where(Person.closed_at.is_(None)))
        return [p for p in rows if not statuses or p.status in statuses]

    def groups(self) -> list[HomeGroup]:
        return list(self.session.scalars(select(HomeGroup).where(HomeGroup.closed_at.is_(None))))

    def churches(self) -> list[Church]:
        return list(self.session.scalars(select(Church).where(Church.closed_at.is_(None))))

    def pick(self, items: list[Any]) -> Any:
        return self.rng.choice(items) if items else None

    def some_id(self, items: list[Any]) -> str:
        """The id of one of `items`, or now and then of something that is not there."""
        if not items or self.rng.random() < 0.08:
            return str(uuid.uuid4())
        return str(self.rng.choice(items).id)

    def maybe_id(self, items: list[Any]) -> str | None:
        return None if self.rng.random() < 0.3 else self.some_id(items)

    def member_of(self, group_id: uuid.UUID | None) -> list[Person]:
        return [p for p in self.people() if p.home_group_id == group_id and p.status != "revoked"]

    # ---- calls ---------------------------------------------------------------------------

    def headers(self, person: Person) -> dict[str, str]:
        token, _ = create_access_token(
            Principal("person", person.id),
            secret=get_settings().require_jwt_secret(),
            lifetime_minutes=30,
        )
        return {"Authorization": f"Bearer {token}"}

    def call(
        self, name: str, method: str, path: str, actor: Person | None, **body: Any
    ) -> tuple[bool, Any]:
        """Make a call; True when it succeeded. Never a server error; a refusal has a code."""
        _reset_limiters()
        headers = self.headers(actor) if actor is not None else {}
        response = self.client.request(
            method, f"{API}{path}", headers=headers, json=body if body else None
        )
        self.log.append(f"{name} {method} {path} {body} -> {response.status_code}")
        assert response.status_code < 500, (name, response.status_code, response.text)
        if response.status_code >= 400:
            self.session.rollback()  # as the application does for a refused request
            self.session.expire_all()
            assert response.json()["error"]["code"], response.text
            return False, response.json()
        self.session.expire_all()
        succeeded[name] += 1
        return True, (response.json() if response.content else None)

    # ---- the operations -----------------------------------------------------------------

    def sign_up(self) -> None:
        groups = self.groups()
        if not groups:
            return
        password = secrets.token_urlsafe(16)
        email = f"p{secrets.token_hex(5)}@example.com"
        ok, body = self.call(
            "sign_up",
            "POST",
            "/auth/signup",
            None,
            full_name="Random Person",
            email=email,
            mobile_number=f"+9715{secrets.randbelow(10**8):08d}",
            password=password,
            requested_status=self.pick(["searcher", "provider"]),
            home_group_id=self.some_id(groups),
        )
        if ok:
            self.passwords[uuid.UUID(body["id"])] = password

    def change_application(self) -> None:
        who = self.pick(self.people("pending"))
        if who:
            self.call(
                "change_application",
                "PUT",
                "/me/application",
                who,
                home_group_id=self.maybe_id(self.groups()),
                requested_status=self.pick([None, "searcher", "provider"]),
            )

    def apply_provider(self) -> None:
        who = self.pick(self.people("searcher"))
        if who:
            self.call("apply_provider", "POST", "/me/apply-provider", who)

    def vouch(self) -> None:
        seekers = self.people("pending", "searcher")
        applicant = self.pick(seekers)
        if not applicant:
            return
        ok, body = self.call("make_vouch_link", "POST", "/me/vouch-link", applicant)
        if not ok:
            return
        voucher = self.pick(self.people("provider", "verifier", "admin", "owner"))
        if voucher:
            self.call("vouch", "POST", "/vouch-links/vouch", voucher, token=body["token"])

    def withdraw_vouch(self) -> None:
        row = self.pick(list(self.session.scalars(select(Vouch))))
        if row:
            voucher = self.session.get(Person, row.voucher_id)
            if voucher and voucher.closed_at is None:
                self.call("withdraw_vouch", "DELETE", f"/vouches/{row.id}", voucher)

    def leader_of_someone(self) -> tuple[Person | None, Person | None]:
        """A person with authority and a person they might act on, often in scope."""
        actor = self.pick(self.people(*HIGHER))
        everyone = self.people()
        if actor is None or not everyone:
            return None, None
        if self.rng.random() < 0.8:
            scope = [
                p
                for p in everyone
                if actor.status == "owner"
                or (actor.status == "admin" and p.church_id == actor.church_id)
                or p.home_group_id == actor.home_group_id
            ]
            everyone = scope or everyone
        return actor, self.pick(everyone)

    def admit(self) -> None:
        actor, target = self.leader_of_someone()
        if self.rng.random() < 0.6:
            # A leader other than the OWNER admits someone waiting in their group: the people
            # they admit are the ones flagged if they are revoked later.
            leaders = [p for p in self.people("verifier", "admin") if p.home_group_id]
            actor = self.pick(leaders) or actor
            waiting = [
                p
                for p in self.people("pending")
                if actor and p.home_group_id == actor.home_group_id
            ]
            target = self.pick(waiting) or target
        if actor and target:
            self.call(
                "admit",
                "POST",
                f"/verifier/people/{target.id}/admit",
                actor,
                to=self.pick(["searcher", "provider"]),
            )

    def decline(self) -> None:
        actor, target = self.leader_of_someone()
        if actor and target:
            self.call("decline", "POST", f"/verifier/people/{target.id}/decline", actor)

    def revoke(self) -> None:
        actor, target = self.leader_of_someone()
        if actor and self.rng.random() < 0.4:
            # Someone who admitted others: revoking them flags the people they set.
            setters = {p.status_set_by_id for p in self.people()} - {None}
            people = [p for p in self.people() if p.id in setters and p.id != actor.id]
            target = self.pick(people) or target
        if not (actor and target):
            return
        church_people = [p for p in self.people() if p.church_id == target.church_id]
        group_people = self.member_of(target.home_group_id)
        body: dict[str, Any] = {"to": "revoked"}
        if self.rng.random() < 0.7:
            body["successor_id"] = self.maybe_id(
                church_people if target.status == "admin" else group_people
            )
        if target.status == "admin" and self.rng.random() < 0.7:
            body["group_successor_id"] = self.maybe_id(group_people)
        ok, _ = self.call("revoke", "PUT", f"/verifier/people/{target.id}/status", actor, **body)
        if ok and self.rng.random() < 0.8:
            self.reconfirm()  # people the revoked person admitted are flagged: the usual next step

    def reinstate(self) -> None:
        actor = self.pick(self.people(*HIGHER))
        revoked = [p for p in self.session.scalars(select(Person)) if p.status == "revoked"]
        target = self.pick(revoked)
        if actor and target:
            group = self.pick([g for g in self.groups() if g.church_id == actor.church_id])
            self.call(
                "reinstate",
                "PUT",
                f"/verifier/people/{target.id}/status",
                actor,
                to=self.pick(["searcher", "provider"]),
                home_group_id=self.some_id([group] if group else []),
            )

    def reconfirm(self) -> None:
        target = self.pick([p for p in self.people() if p.flagged_for_recheck])
        if not target:
            return
        scope = [
            p
            for p in self.people(*HIGHER)
            if p.status == "owner"
            or (p.status == "admin" and p.church_id == target.church_id)
            or p.home_group_id == target.home_group_id
        ]
        actor = self.pick(scope if scope and self.rng.random() < 0.9 else self.people(*HIGHER))
        if actor:
            self.call("reconfirm", "POST", f"/verifier/people/{target.id}/reconfirm", actor)

    def replace_leader(self) -> None:
        group = self.pick(self.groups())
        if not group:
            return
        actor = self.pick(self.people("verifier", "admin", "owner"))
        if actor is None:
            return
        successors = self.member_of(group.id)
        self.call(
            "replace_leader",
            "PUT",
            f"/home-groups/{group.id}/leader",
            actor,
            successor_id=self.some_id(successors),
            former_leader_status=self.pick(["provider", "searcher", "keep"]),
        )

    def replace_admin(self) -> None:
        owner = self.pick(self.people("owner"))
        churches = self.churches()
        if owner and self.rng.random() < 0.9:
            churches = [c for c in churches if c.id != owner.church_id] or churches
        church = self.pick(churches)
        if not (owner and church):
            return
        members = [p for p in self.people() if p.church_id == church.id]
        if self.rng.random() < 0.9:
            members = [p for p in members if p.id != church.admin_id] or members
        self.call(
            "replace_admin",
            "PUT",
            f"/churches/{church.id}/admin",
            owner,
            successor_id=self.some_id(members),
            former_admin_status=self.pick(["provider", "searcher"]),
            group_successor_id=self.maybe_id(members),
        )

    def ask_to_move(self) -> None:
        who = self.pick(self.people("pending", "searcher", "provider", "verifier"))
        if who:
            own = [g for g in self.groups() if g.church_id == who.church_id]
            ok, _ = self.call(
                "ask_to_move",
                "POST",
                "/move-requests",
                who,
                home_group_id=self.some_id(own),
            )
            if ok and self.rng.random() < 0.8:
                self.agree_to_move()

    def agree_to_move(self) -> None:
        row = self.pick(
            [m for m in self.session.scalars(select(MoveRequest)) if m.completed_at is None]
        )
        actor = self.pick(self.people(*HIGHER))
        if row and actor:
            leader = None
            for group_id in (row.from_group_id, row.to_group_id):
                group = self.session.get(HomeGroup, group_id)
                if group and self.rng.random() < 0.5:
                    leader = self.session.get(Person, group.leader_id)
            self.call("agree_to_move", "POST", f"/move-requests/{row.id}/agree", leader or actor)

    def cancel_move(self) -> None:
        row = self.pick(
            [
                m
                for m in self.session.scalars(select(MoveRequest))
                if m.completed_at is None and m.cancelled_at is None
            ]
        )
        if row:
            who = self.session.get(Person, row.person_id)
            if who and who.closed_at is None:
                self.call("cancel_move", "POST", f"/move-requests/{row.id}/cancel", who)

    def move_directly(self) -> None:
        actor = self.pick(self.people("admin", "owner"))
        if not actor:
            return
        pool = [
            p for p in self.people() if p.church_id == actor.church_id and p.status in ORDER[2:5]
        ]
        target = self.pick(pool if pool and self.rng.random() < 0.9 else self.people())
        if target:
            own = [g for g in self.groups() if g.church_id == target.church_id]
            if self.rng.random() < 0.9:
                own = [g for g in own if g.id != target.home_group_id] or own
            self.call(
                "move_directly",
                "POST",
                f"/verifier/people/{target.id}/move",
                actor,
                home_group_id=self.some_id(own),
            )

    def close_group(self) -> None:
        leaders = self.people(*HIGHER)
        alone = [
            p for p in leaders if p.home_group_id and len(self.member_of(p.home_group_id)) == 1
        ]
        leader = self.pick(alone if alone and self.rng.random() < 0.7 else leaders)
        if not leader:
            return
        own = [g for g in self.groups() if g.church_id == leader.church_id]
        others = [g for g in own if g.id != leader.home_group_id]
        group = self.session.get(HomeGroup, leader.home_group_id) if leader.home_group_id else None
        self.call(
            "close_group",
            "POST",
            f"/home-groups/{(group or self.pick(own) or HomeGroup(id=uuid.uuid4())).id}/close",
            leader,
            move_to_group_id=self.some_id(others if self.rng.random() < 0.8 else own),
            former_leader_status=self.pick(["provider", "searcher", "keep"]),
        )

    def close_church(self) -> None:
        owner = self.pick(self.people("owner"))
        church = self.pick(self.churches())
        if owner and church and self.rng.random() < 0.5:
            self.call("close_church", "POST", f"/owner/churches/{church.id}/close", owner)

    def ask_for_group(self) -> None:
        who = self.pick(self.people("provider", "verifier", "admin", "owner"))
        if not who:
            return
        successors = self.member_of(who.home_group_id)
        ok, _ = self.call(
            "ask_for_group",
            "POST",
            "/group-requests",
            who,
            group_name=f"Group {secrets.token_hex(3)}",
            successor_id=self.maybe_id(successors),
        )
        if ok and self.rng.random() < 0.8:
            self.answer_group_request()

    def answer_group_request(self) -> None:
        row = self.pick(
            [g for g in self.session.scalars(select(GroupRequest)) if g.state == "open"]
        )
        actor = self.pick(self.people("admin", "owner"))
        if not (row and actor):
            return
        if self.rng.random() < 0.75:
            requester = self.session.get(Person, row.requester_id)
            members = self.member_of(requester.home_group_id) if requester else []
            self.call(
                "approve_group",
                "POST",
                f"/group-requests/{row.id}/approve",
                actor,
                successor_id=self.maybe_id(members),
            )
        else:
            self.call("decline_group", "POST", f"/group-requests/{row.id}/decline", actor)

    def invite_church(self) -> None:
        owner = self.pick(self.people("owner"))
        if not owner:
            return
        ok, body = self.call(
            "invite_church",
            "POST",
            "/owner/churches",
            owner,
            church_name=f"Church {secrets.token_hex(3)}",
            email=f"a{secrets.token_hex(5)}@example.com",
        )
        if ok:
            self.invitations.append(body["token"])

    def accept_invitation(self) -> None:
        if not self.invitations:
            return
        token = self.invitations.pop(self.rng.randrange(len(self.invitations)))
        password = secrets.token_urlsafe(16)
        ok, body = self.call(
            "accept_invitation",
            "POST",
            "/admin-invitations/accept",
            None,
            token=token,
            full_name="New Admin",
            mobile_number=f"+9715{secrets.randbelow(10**8):08d}",
            password=password,
            home_group_name=f"Home {secrets.token_hex(3)}",
        )
        if ok:
            self.passwords[uuid.UUID(body["id"])] = password

    def propose_handover(self) -> None:
        owner = self.pick(self.people("owner"))
        admins = self.people("admin")
        if not owner:
            return
        church = self.people()
        mine = [p for p in church if p.church_id == owner.church_id]
        self.call(
            "propose_handover",
            "POST",
            "/owner/handover",
            owner,
            new_owner_id=self.some_id(admins),
            successor_admin_id=self.maybe_id(mine),
            successor_leader_id=self.maybe_id(self.member_of(owner.home_group_id)),
            former_owner_status=self.pick(["provider", "searcher"]),
        )

    def answer_handover(self) -> None:
        row = self.pick(
            [
                h
                for h in self.session.scalars(select(HandoverRequest))
                if h.accepted_at is None and h.cancelled_at is None
            ]
        )
        if not row:
            return
        if self.rng.random() < 0.8:
            who = self.session.get(Person, row.new_owner_id)
            if who and who.closed_at is None:
                self.call("accept_handover", "POST", f"/owner/handover/{row.id}/accept", who)
        else:
            who = self.session.get(Person, row.owner_id)
            if who and who.closed_at is None:
                self.call("cancel_handover", "POST", f"/owner/handover/{row.id}/cancel", who)

    def operators_change_owner(self) -> None:
        admins = self.people("admin")
        if not admins or self.rng.random() < 0.6:
            return
        new = self.pick(admins)
        members = [p for p in self.people() if p.church_id == self.people("owner")[0].church_id]
        owner = self.people("owner")[0]
        group_people = self.member_of(owner.home_group_id)
        succ_a = self.pick([m for m in members if m.id != owner.id] + [None])
        succ_l = self.pick([m for m in group_people if m.id != owner.id] + [None])
        try:
            change_owner(
                self.session,
                new_owner_email=str(new.email),
                former_status=self.pick(["provider", "searcher"]),
                admin_successor_email=str(succ_a.email) if succ_a else None,
                leader_successor_email=str(succ_l.email) if succ_l else None,
                revoke_old_owner=self.rng.random() < 0.3,
            )
        except Exception as error:  # a refusal, as the command prints, never a crash
            assert isinstance(error, (SetupError, ApiError)), repr(error)
            self.session.rollback()
            self.session.expire_all()
            self.log.append(f"change_owner refused: {error}")
            return
        self.session.expire_all()
        succeeded["change_owner"] += 1

    def close_account(self) -> None:
        who = self.pick(self.people())
        if who is not None and who.id in self.passwords and self.rng.random() < 0.5:
            self.call("close_account", "DELETE", "/me", who, password=self.passwords[who.id])

    # ---- the rules, in plain code ----------------------------------------------------------

    def check(self) -> None:
        check_rules(self.session)
        self.session.expire_all()
        people = list(self.session.scalars(select(Person)))
        open_people = [p for p in people if p.closed_at is None]
        groups = {g.id: g for g in self.session.scalars(select(HomeGroup))}
        church_rows = {c.id: c for c in self.session.scalars(select(Church))}
        by_id = {p.id: p for p in people}

        owners = [p for p in open_people if p.status == "owner"]
        assert len(owners) == 1, "1: exactly one OWNER"
        for p in open_people:
            if p.status != "revoked":  # 2
                group = groups.get(p.home_group_id)  # type: ignore[arg-type]
                assert group is not None and group.church_id == p.church_id, f"2: {p.id}"
                assert group.closed_at is None, f"2: {p.id} is in a closed group"
            else:
                assert p.home_group_id is None and not p.flagged_for_recheck
        for church in church_rows.values():  # 3
            if church.closed_at is not None:
                continue
            admin = by_id[church.admin_id]
            assert admin.closed_at is None and admin.church_id == church.id
            assert admin.status in ("admin", "owner"), f"3: church {church.id}"
            others = [p for p in open_people if p.church_id == church.id and p.status == "admin"]
            assert all(p.id == church.admin_id for p in others), f"3: two ADMINs in {church.id}"
        for p in open_people:
            if p.status == "admin":
                assert church_rows[p.church_id].admin_id == p.id, f"3: stray ADMIN {p.id}"
        assert church_rows[owners[0].church_id].admin_id == owners[0].id
        led: Counter[uuid.UUID] = Counter()
        for group in groups.values():  # 4
            if group.closed_at is not None:
                continue
            leader = by_id[group.leader_id]
            assert leader.closed_at is None and leader.home_group_id == group.id, f"4: {group.id}"
            assert ORDER.index(leader.status) >= ORDER.index("verifier"), f"4: {group.id}"
            led[leader.id] += 1
        assert all(count == 1 for count in led.values()), "4: leads two groups"
        for p in open_people:  # 5
            if p.status == "verifier":
                assert led[p.id] == 1, f"5: VERIFIER {p.id} leads nothing"
            if ORDER.index(p.status) >= ORDER.index("verifier"):
                assert led[p.id] <= 1
        self._history(people)

    def _history(self, people: list[Person]) -> None:
        """Each person's changes can be put in an order that is a chain ending at their status.
        (The test shares one transaction, so the database's own clock cannot order them.)"""
        edges: dict[uuid.UUID, list[tuple[str | None, str]]] = {}
        for row in self.session.scalars(select(StatusChange)):
            edges.setdefault(row.person_id, []).append((row.from_status, row.to_status))
        for person in people:
            mine = edges.get(person.id, [])
            if mine:
                ends = None if person.closed_at is not None else person.status
                assert _is_chain(mine, ends), f"history of {person.id}: {mine} ends at {ends}"


def _is_chain(edges: list[tuple[str | None, str]], end: str | None) -> bool:
    """Can every edge be used once, each starting where the last ended, finishing at `end` (any
    place when `end` is None)?"""

    def walk(at: str, left: list[tuple[str | None, str]]) -> bool:
        if not left:
            return end is None or at == end
        return any(
            walk(to, left[:i] + left[i + 1 :]) for i, (start, to) in enumerate(left) if start == at
        )

    return any(walk(to, edges[:i] + edges[i + 1 :]) for i, (_, to) in enumerate(edges))


OPERATIONS: list[tuple[int, Callable[[Run], None]]] = [
    (6, Run.sign_up),
    (2, Run.change_application),
    (2, Run.apply_provider),
    (4, Run.vouch),
    (1, Run.withdraw_vouch),
    (6, Run.admit),
    (1, Run.decline),
    (4, Run.revoke),
    (3, Run.reinstate),
    (5, Run.reconfirm),
    (2, Run.replace_leader),
    (2, Run.replace_admin),
    (3, Run.ask_to_move),
    (3, Run.agree_to_move),
    (1, Run.cancel_move),
    (4, Run.move_directly),
    (2, Run.close_group),
    (1, Run.close_church),
    (3, Run.ask_for_group),
    (3, Run.answer_group_request),
    (2, Run.invite_church),
    (2, Run.accept_invitation),
    (4, Run.propose_handover),
    (4, Run.answer_handover),
    (1, Run.operators_change_owner),
    (1, Run.close_account),
]


@pytest.mark.parametrize("seed", SEEDS, ids=lambda s: f"seed-{s}")
def test_random_sequences_keep_the_rules(client: TestClient, session: Session, seed: int) -> None:
    create_first_owner(
        session,
        full_name="Olive Owner",
        email="olive@example.com",
        mobile_number="+971500000300",
        password=secrets.token_urlsafe(16),
        church_name="Grace Church",
        group_name="Riverside",
    )
    run = Run(client, session, seed)
    run.check()
    weights = [w for w, _ in OPERATIONS]
    for step in range(STEPS):
        _, operation = run.rng.choices(OPERATIONS, weights=weights)[0]
        try:
            operation(run)
            run.check()
        except Exception:
            print(f"seed {seed}, step {step}, last calls:")
            print("\n".join(run.log[-6:]))
            raise


def test_the_walks_reached_the_main_operations() -> None:
    """Runs after the seeds (file order): a walk that only met refusals proves nothing. The
    operations named here succeed many times in every run; the rarer ones (a reconfirmation, an
    accepted handover, a closed church) vary with the dice and have their own tests."""
    expected = {
        "sign_up",
        "vouch",
        "admit",
        "revoke",
        "reinstate",
        "replace_admin",
        "move_directly",
        "close_account",
        "ask_for_group",
        "invite_church",
        "accept_invitation",
        "propose_handover",
    }
    if not succeeded:
        pytest.skip("the seeded walks did not run")
    print("succeeded:", dict(sorted(succeeded.items())))
    assert expected <= set(succeeded), f"never succeeded: {sorted(expected - set(succeeded))}"
