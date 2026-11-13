import uuid
from typing import Annotated, Literal, cast

from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import current_person
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.models.church import HomeGroup, Person
from app.schemas.church import IdName
from app.schemas.moves import DirectMove, Moved
from app.schemas.signup import (
    GroupInvitationCreated,
    GroupInvitationList,
    GroupInvitationSummary,
)
from app.schemas.verifier import (
    AdmitRequest,
    AdmitResult,
    ApplicantList,
    FlaggedList,
    Limit,
    MemberList,
    Offset,
    PersonDetail,
    RevokedList,
    StatusRequest,
    StatusResult,
)
from app.services import admission, moves, revocation, signup, verifier_views

router = APIRouter(prefix="/verifier", tags=["verifier"])

# A leader: VERIFIER or higher.
Verifier = Annotated[Person, Depends(current_person("verifier"))]


@router.post("/group-invitations", status_code=status.HTTP_201_CREATED)
def create_group_invitation(
    leader: Verifier,
    db: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> GroupInvitationCreated:
    """A new link into your own home group. The token is shown once; only a hash is kept."""
    invitation, token = signup.create_group_invitation(db, settings, leader)
    return GroupInvitationCreated(id=invitation.id, token=token, expires_at=invitation.expires_at)


@router.get("/group-invitations")
def list_group_invitations(
    leader: Verifier, db: Annotated[Session, Depends(get_session)]
) -> GroupInvitationList:
    """The links into your home group that still work (the tokens are not shown again)."""
    return GroupInvitationList(
        items=[
            GroupInvitationSummary(id=i.id, created_at=i.created_at, expires_at=i.expires_at)
            for i in signup.active_invitations(db, leader)
        ]
    )


@router.delete("/group-invitations/{invitation_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_group_invitation(
    invitation_id: uuid.UUID, leader: Verifier, db: Annotated[Session, Depends(get_session)]
) -> Response:
    signup.revoke_invitation(db, leader, invitation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


Page = Annotated[Limit, Query()]
From = Annotated[Offset, Query()]


@router.get("/applicants")
def applicants(
    verifier: Verifier,
    db: Annotated[Session, Depends(get_session)],
    limit: Page = 50,
    offset: From = 0,
) -> ApplicantList:
    """PENDING applicants in scope, the most vouched first. No phone numbers."""
    return verifier_views.applicants(db, verifier, limit, offset)


@router.get("/members")
def members(
    verifier: Verifier,
    db: Annotated[Session, Depends(get_session)],
    limit: Page = 50,
    offset: From = 0,
    status_filter: Annotated[
        Literal["searcher", "provider", "verifier", "admin", "owner"] | None,
        Query(alias="status"),
    ] = None,
    home_group_id: uuid.UUID | None = None,
) -> MemberList:
    """Admitted people in scope, by name. Filter by `status` or `home_group_id`."""
    return verifier_views.members(
        db, verifier, limit, offset, status=status_filter, home_group_id=home_group_id
    )


@router.get("/revoked")
def revoked(
    verifier: Verifier,
    db: Annotated[Session, Depends(get_session)],
    limit: Page = 50,
    offset: From = 0,
) -> RevokedList:
    return verifier_views.revoked(db, verifier, limit, offset)


@router.get("/flagged")
def flagged(
    verifier: Verifier,
    db: Annotated[Session, Depends(get_session)],
    limit: Page = 50,
    offset: From = 0,
) -> FlaggedList:
    return verifier_views.flagged(db, verifier, limit, offset)


@router.get("/people/{person_id}")
def person(
    person_id: uuid.UUID, verifier: Verifier, db: Annotated[Session, Depends(get_session)]
) -> PersonDetail:
    """One person in scope, with their history, chain of trust and mobile number. Each call is
    logged (who looked at whom, never the number); `404` for anyone out of scope."""
    return verifier_views.person_detail(db, verifier, person_id)


@router.post("/people/{person_id}/admit")
def admit(
    person_id: uuid.UUID,
    body: AdmitRequest,
    verifier: Verifier,
    db: Annotated[Session, Depends(get_session)],
) -> AdmitResult:
    """Admit an applicant as a searcher or a provider. A provider needs a live vouch from
    someone besides you (`409 not_enough_vouches`)."""
    admitted = admission.admit(db, verifier, person_id, body.to)
    return AdmitResult(
        id=admitted.id, status=admitted.status, requested_status=admitted.requested_status
    )


@router.post("/people/{person_id}/decline", status_code=status.HTTP_204_NO_CONTENT)
def decline(
    person_id: uuid.UUID, verifier: Verifier, db: Annotated[Session, Depends(get_session)]
) -> Response:
    """Close an application. Nobody is revoked, and the person can sign up again."""
    admission.decline(db, verifier, person_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _status_result(person: Person) -> StatusResult:
    return StatusResult(
        id=person.id,
        status=person.status,
        home_group_id=person.home_group_id,
        flagged_for_recheck=person.flagged_for_recheck,
    )


@router.put("/people/{person_id}/status")
def set_status(
    person_id: uuid.UUID,
    body: StatusRequest,
    verifier: Verifier,
    db: Annotated[Session, Depends(get_session)],
) -> StatusResult:
    """Revoke a person in scope who is below you, or reinstate a revoked one into a home group
    (`home_group_id`). A leader is replaced first (`409 successor_required`). A revocation made
    by a higher leader cannot be undone by a lower one (`403 status_not_allowed`)."""
    if body.to == "revoked":
        return _status_result(
            revocation.revoke(db, verifier, person_id, body.successor_id, body.group_successor_id)
        )
    group_id = cast(uuid.UUID, body.home_group_id)  # the request model guarantees it
    return _status_result(revocation.reinstate(db, verifier, person_id, body.to, group_id))


@router.post("/people/{person_id}/reconfirm")
def reconfirm(
    person_id: uuid.UUID, verifier: Verifier, db: Annotated[Session, Depends(get_session)]
) -> StatusResult:
    """Clear the re-check flag of a person in scope. You become the new link in their chain of
    trust. `409 not_flagged` if there is no flag."""
    return _status_result(revocation.reconfirm(db, verifier, person_id))


@router.post("/people/{person_id}/move")
def move(
    person_id: uuid.UUID,
    body: DirectMove,
    admin: Annotated[Person, Depends(current_person("admin"))],
    db: Annotated[Session, Depends(get_session)],
) -> Moved:
    """An ADMIN (of the person's church) or the OWNER moves an admitted member to another open home
    group of the church, without the agreements a move by request needs. A leader steps down first
    (`409 leads_a_group`); the member is told, and so are both leaders."""
    person = moves.move_directly(db, admin, person_id, body.home_group_id)
    group = db.get(HomeGroup, person.home_group_id)
    return Moved(
        person=IdName(id=person.id, name=person.full_name or ""),
        home_group=IdName(id=person.home_group_id, name=group.name if group else ""),
    )
