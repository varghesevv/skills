import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import current_person
from app.chat import moderation
from app.core.db import get_session
from app.models.church import Person
from app.schemas.chat import AdminReportOut, ReportedMessage
from app.schemas.common import Page, Pagination, pagination

router = APIRouter(prefix="/owner/chat-reports", tags=["chat"])

Owner = Annotated[Person, Depends(current_person("owner"))]


@router.get("")
def list_reports(
    owner: Owner,
    db: Annotated[Session, Depends(get_session)],
    handled: Annotated[bool | None, Query()] = None,
    paging: Pagination = Depends(pagination),
) -> Page[AdminReportOut]:
    """Reports newest first; `handled=false` for the open ones. No message text here."""
    items, total = moderation.list_reports(
        db, handled=handled, offset=paging.offset, limit=paging.page_size
    )
    return Page[AdminReportOut](
        items=items, total=total, page=paging.page, page_size=paging.page_size
    )


@router.get("/{report_id}/messages")
def read_messages(
    report_id: uuid.UUID, owner: Owner, db: Annotated[Session, Depends(get_session)]
) -> list[ReportedMessage]:
    """The reported conversation, oldest first. Each call is logged (who and when)."""
    report = moderation.get_report(db, report_id)
    messages = moderation.read_reported_conversation(db, report, owner)
    db.commit()
    return messages


@router.post("/{report_id}/handle", status_code=status.HTTP_204_NO_CONTENT)
def handle(
    report_id: uuid.UUID, owner: Owner, db: Annotated[Session, Depends(get_session)]
) -> Response:
    report = moderation.get_report(db, report_id)
    moderation.handle_report(db, report, owner)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
