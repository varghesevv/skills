"""The chat metrics report RP-11 (S8.10): counts only, answers measured, reveals followed."""

import uuid
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from app.models.chat import Conversation, Message
from app.models.reveals import PhoneReveal
from app.reports.runner import build_report
from tests.test_reports import params
from tests.trust_helpers import World

pytestmark = pytest.mark.db

DAY = datetime(2026, 11, 10, 8, 0, tzinfo=UTC)


@pytest.fixture
def world(session: Session) -> World:
    return World(session)


def window(session: Session) -> dict[str, object]:
    result = build_report(session, "chat_metrics", params(date(2026, 11, 1), date(2026, 12, 1)))
    summary, by_day = result.sections
    return {
        "summary": {row[0]: row[1] for row in summary.rows},
        "days": by_day.rows,
        "text": str(result.sections),
    }


def talk(
    world: World,
    starter: object,
    provider: object,
    *,
    started: datetime,
    asked: datetime | None = None,
    answered: datetime | None = None,
    body: str = "private words",
) -> Conversation:
    session = world.session
    conversation = Conversation(
        starter_id=starter.id,  # type: ignore[attr-defined]
        provider_id=provider.id,  # type: ignore[attr-defined]
        created_at=started,
    )
    session.add(conversation)
    session.flush()
    for side, person, when in (
        ("starter", starter, asked),
        ("provider", provider, answered),
    ):
        if when is not None:
            session.add(
                Message(
                    conversation_id=conversation.id,
                    sender_side=side,
                    sender_id=person.id,  # type: ignore[attr-defined]
                    body=body,
                    client_message_id=uuid.uuid4(),
                    created_at=when,
                )
            )
    session.flush()
    return conversation


def test_an_empty_window_has_zeros_and_no_rates(world: World) -> None:
    summary = window(world.session)["summary"]
    assert summary["conversations_started"] == 0  # type: ignore[index]
    assert summary["messages_sent"] == 0  # type: ignore[index]
    assert summary["first_answer_rate_percent"] is None  # type: ignore[index]
    assert summary["median_minutes_to_first_answer"] is None  # type: ignore[index]
    assert summary["reveal_to_conversation_percent"] is None  # type: ignore[index]


def test_conversations_messages_and_people_are_counted_in_the_window(world: World) -> None:
    a, b, c = (world.add_person("provider") for _ in range(3))
    s = world.add_person("searcher")
    talk(
        world,
        s,
        a,
        started=DAY,
        asked=DAY + timedelta(minutes=1),
        answered=DAY + timedelta(minutes=5),
    )
    talk(world, s, b, started=DAY + timedelta(days=1), asked=DAY + timedelta(days=1))
    talk(
        world,
        s,
        c,
        started=datetime(2026, 10, 1, tzinfo=UTC),
        asked=datetime(2026, 10, 1, tzinfo=UTC),
    )
    result = window(world.session)
    summary = result["summary"]
    assert summary["conversations_started"] == 2  # type: ignore[index]
    assert summary["messages_sent"] == 3  # type: ignore[index]
    assert summary["people_who_wrote"] == 2  # type: ignore[index]  # the searcher and one provider
    assert summary["conversations_with_messages"] == 2  # type: ignore[index]
    assert result["days"] == [["2026-11-10", 1, 2], ["2026-11-11", 1, 1]]


def test_the_first_answer_rate_and_the_median_time_use_the_first_answer(world: World) -> None:
    s = world.add_person("searcher")
    p1, p2, p3, p4 = (world.add_person("provider") for _ in range(4))
    talk(world, s, p1, started=DAY, asked=DAY, answered=DAY + timedelta(minutes=10))
    talk(world, s, p2, started=DAY, asked=DAY, answered=DAY + timedelta(minutes=30))
    talk(world, s, p3, started=DAY, asked=DAY)  # never answered
    talk(world, s, p4, started=DAY)  # the starter never wrote: not counted
    summary = window(world.session)["summary"]
    assert summary["conversations_where_the_starter_wrote"] == 3  # type: ignore[index]
    assert summary["answered_by_the_provider"] == 2  # type: ignore[index]
    assert summary["first_answer_rate_percent"] == 66.7  # type: ignore[index]
    assert summary["median_minutes_to_first_answer"] == 20.0  # type: ignore[index]


def test_a_provider_message_before_the_first_ask_is_not_an_answer(world: World) -> None:
    s, p = world.add_person("searcher"), world.add_person("provider")
    talk(
        world,
        s,
        p,
        started=DAY,
        asked=DAY + timedelta(minutes=5),
        answered=DAY + timedelta(minutes=1),
    )
    summary = window(world.session)["summary"]
    assert summary["answered_by_the_provider"] == 0  # type: ignore[index]
    assert summary["first_answer_rate_percent"] == 0.0  # type: ignore[index]


def test_revealed_numbers_that_lead_to_a_conversation_within_a_week(world: World) -> None:
    s = world.add_person("searcher")
    p1, p2, p3 = (world.add_person("provider") for _ in range(3))
    for provider in (p1, p2, p3):
        world.session.add(
            PhoneReveal(
                revealer_id=s.id,
                provider_id=provider.id,
                revealed_at=DAY,
                channel="show",
                source="detail",
            )
        )
    world.session.add(  # a second reveal of the same pair counts once
        PhoneReveal(
            revealer_id=s.id,
            provider_id=p1.id,
            revealed_at=DAY + timedelta(hours=1),
            channel="dial",
            source="search",
        )
    )
    world.session.flush()
    talk(world, s, p1, started=DAY + timedelta(days=2), asked=DAY + timedelta(days=2))  # yes
    talk(world, s, p2, started=DAY + timedelta(days=8), asked=DAY + timedelta(days=8))  # too late
    # p3: no conversation at all
    summary = window(world.session)["summary"]
    assert summary["numbers_revealed_to_providers"] == 3  # type: ignore[index]
    assert summary["of_these_a_conversation_within_7_days"] == 1  # type: ignore[index]
    assert summary["reveal_to_conversation_percent"] == 33.3  # type: ignore[index]


def test_a_conversation_started_by_the_provider_side_person_also_counts(world: World) -> None:
    s, p = world.add_person("provider"), world.add_person("provider")
    world.session.add(
        PhoneReveal(
            revealer_id=s.id, provider_id=p.id, revealed_at=DAY, channel="show", source="detail"
        )
    )
    world.session.flush()
    talk(world, p, s, started=DAY + timedelta(hours=3), asked=DAY + timedelta(hours=3))
    summary = window(world.session)["summary"]
    assert summary["of_these_a_conversation_within_7_days"] == 1  # type: ignore[index]


def test_the_report_holds_no_names_text_or_ids(world: World) -> None:
    s, p = world.add_person("searcher"), world.add_person("provider")
    conversation = talk(
        world,
        s,
        p,
        started=DAY,
        asked=DAY,
        answered=DAY + timedelta(minutes=2),
        body="text that must not appear",
    )
    text = str(window(world.session)["text"])
    for private in ("text that must not appear", str(s.full_name), str(conversation.id), str(s.id)):
        assert private not in text
