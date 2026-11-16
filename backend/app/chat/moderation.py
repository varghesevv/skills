"""Reporting a conversation, and the OWNER reading a reported one (ADR-0014, section 7).

Only a reported conversation can be read by the OWNER, and every reading is logged (who and when,
never what). Messages and notes are never written to a log.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.chat.rules import now
from app.core.errors import ApiError
from app.models.chat import ChatReport, ChatReportView, Conversation, Message
from app.models.church import Person
from app.schemas.chat import AdminReportOut, NamedPerson, ReportedMessage

MAX_READ_MESSAGES = 500


def report_conversation(
    db: Session,
    conversation: Conversation,
    side: str,
    reporter: Person,
    reason: str,
    note: str | None,
) -> tuple[ChatReport, bool]:
    """File a report; `(report, created)`. A second report by the same person while one is open
    changes nothing and returns the open one."""
    open_report = db.scalar(
        select(ChatReport).where(
            ChatReport.conversation_id == conversation.id,
            ChatReport.reporter_id == reporter.id,
            ChatReport.handled_at.is_(None),
        )
    )
    if open_report is not None:
        return open_report, False
    report = ChatReport(
        conversation_id=conversation.id,
        reporter_id=reporter.id,
        reported_by_side=side,
        reason=reason,
        note=(note or "").strip() or None,
    )
    db.add(report)
    try:
        db.flush()
    except IntegrityError:  # the same person reported twice at once
        db.rollback()
        again = db.scalar(
            select(ChatReport).where(
                ChatReport.conversation_id == conversation.id,
                ChatReport.reporter_id == reporter.id,
                ChatReport.handled_at.is_(None),
            )
        )
        if again is None:
            raise
        return again, False
    db.refresh(report)
    return report, True


def get_report(db: Session, report_id: uuid.UUID) -> ChatReport:
    report = db.get(ChatReport, report_id)
    if report is None:
        raise ApiError(404, "not_found", "Report not found")
    return report


def _named(person: Person | None, person_id: uuid.UUID) -> NamedPerson:
    if person is None or person.closed_at is not None:
        return NamedPerson(id=person_id, full_name=None)
    return NamedPerson(id=person_id, full_name=person.full_name)


def list_reports(
    db: Session, *, handled: bool | None, offset: int, limit: int
) -> tuple[list[AdminReportOut], int]:
    where = []
    if handled is True:
        where.append(ChatReport.handled_at.is_not(None))
    elif handled is False:
        where.append(ChatReport.handled_at.is_(None))
    total = db.scalar(select(func.count()).select_from(ChatReport).where(*where)) or 0
    rows = db.execute(
        select(ChatReport, Conversation)
        .join(Conversation, Conversation.id == ChatReport.conversation_id)
        .where(*where)
        .order_by(ChatReport.created_at.desc(), ChatReport.id)
        .offset(offset)
        .limit(limit)
    ).all()
    ids = {report.reporter_id for report, _ in rows} | {
        pid for _, c in rows for pid in (c.starter_id, c.provider_id)
    }
    people = {p.id: p for p in db.scalars(select(Person).where(Person.id.in_(ids))).all()}
    items = []
    for report, conversation in rows:
        other_id = (
            conversation.provider_id
            if report.reporter_id == conversation.starter_id
            else conversation.starter_id
        )
        items.append(
            AdminReportOut(
                id=report.id,
                conversation_id=conversation.id,
                reason=report.reason,
                note=report.note,
                created_at=report.created_at,
                handled_at=report.handled_at,
                reporter=_named(people.get(report.reporter_id), report.reporter_id),
                other=_named(people.get(other_id), other_id),
            )
        )
    return items, total


def read_reported_conversation(
    db: Session, report: ChatReport, owner: Person
) -> list[ReportedMessage]:
    """The messages of a reported conversation, oldest first (the newest 500). The reading is
    logged before anything is returned."""
    db.add(ChatReportView(report_id=report.id, viewer_id=owner.id))
    db.flush()
    conversation = db.get(Conversation, report.conversation_id)
    if conversation is None:  # cannot happen (the report cascades); kept as a safety net
        raise ApiError(404, "not_found", "Report not found")
    rows = db.scalars(
        select(Message)
        .where(Message.conversation_id == conversation.id)
        .order_by(Message.seq.desc())
        .limit(MAX_READ_MESSAGES)
    ).all()
    names = {
        p.id: p.full_name
        for p in db.scalars(select(Person).where(Person.id.in_({m.sender_id for m in rows}))).all()
        if p.closed_at is None
    }
    return [
        ReportedMessage(
            id=m.id,
            seq=m.seq,
            conversation_id=m.conversation_id,
            sender_side=m.sender_side,
            body=m.body,
            created_at=m.created_at,
            sender_name=names.get(m.sender_id),
        )
        for m in reversed(rows)
    ]


def handle_report(db: Session, report: ChatReport, owner: Person) -> None:
    if report.handled_at is None:
        report.handled_at = now()
        report.handled_by_id = owner.id
        db.flush()
