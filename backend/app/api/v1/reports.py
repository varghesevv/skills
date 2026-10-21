import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Annotated, Literal

from apscheduler.triggers.cron import CronTrigger
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import Settings, get_settings
from app.core.db import get_session
from app.core.errors import ApiError
from app.core.security import Principal
from app.models.reports import ReportRun, ReportSchedule
from app.reports.definitions import REGISTRY, REPORTS, get_definition
from app.reports.render import to_csv, to_json
from app.reports.runner import build_report, run_report
from app.reports.types import ReportDef, ReportError, ReportParams
from app.reports.windows import default_window, window_from_dates, zone_of
from app.schemas.common import Page, Pagination, pagination
from app.schemas.reports import (
    ReportInfo,
    ReportRunOut,
    RunRequest,
    ScheduleOut,
    ScheduleUpdate,
)

router = APIRouter(prefix="/reports", tags=["reports"])

AdminOnly = Annotated[Principal, Depends(require_roles("admin"))]
Reader = Annotated[Principal, Depends(require_roles("admin", "organisation"))]


def _definition(name: str) -> ReportDef:
    try:
        return get_definition(name)
    except ReportError:
        raise ApiError(404, "not_found", "Unknown report") from None


def _run_out(run: ReportRun) -> ReportRunOut:
    return ReportRunOut(
        id=run.id,
        report_name=run.report_name,
        window_from=run.window_from,
        window_to=run.window_to,
        started_at=run.started_at,
        finished_at=run.finished_at,
        status=run.status,
        row_count=run.row_count,
        error_message=run.error_message,
        has_files=run.file_path is not None,
    )


def _schedule_out(schedule: ReportSchedule) -> ScheduleOut:
    return ScheduleOut(
        report_name=schedule.report_name,
        cron_expression=schedule.cron_expression,
        timezone=schedule.timezone,
        is_enabled=schedule.is_enabled,
    )


@router.get("")
def list_reports(principal: Reader) -> list[ReportInfo]:
    """The reports you may run. Organisations see only reports limited to their own data."""
    return [
        ReportInfo(
            name=report.name,
            code=report.code,
            title=report.title,
            description=report.description,
            filters=list(report.filters),
        )
        for report in REPORTS
        if principal.user_type == "admin" or report.org_scoped
    ]


# ---- run history, downloads and schedules (admin) -----------------------------------------


@router.get("/runs")
def list_runs(
    _: AdminOnly,
    db: Session = Depends(get_session),
    paging: Pagination = Depends(pagination),
    report_name: str | None = None,
    status: Literal["running", "succeeded", "failed"] | None = None,
) -> Page[ReportRunOut]:
    query = select(ReportRun)
    count = select(func.count()).select_from(ReportRun)
    if report_name:
        query = query.where(ReportRun.report_name == report_name)
        count = count.where(ReportRun.report_name == report_name)
    if status:
        query = query.where(ReportRun.status == status)
        count = count.where(ReportRun.status == status)
    rows = db.scalars(
        query.order_by(ReportRun.started_at.desc(), ReportRun.id)
        .offset(paging.offset)
        .limit(paging.page_size)
    ).all()
    return Page[ReportRunOut](
        items=[_run_out(run) for run in rows],
        total=db.scalar(count) or 0,
        page=paging.page,
        page_size=paging.page_size,
    )


@router.get("/runs/{run_id}/download")
def download_run(
    run_id: uuid.UUID,
    _: AdminOnly,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    output_format: Annotated[Literal["csv", "html"], Query(alias="format")] = "csv",
) -> FileResponse:
    run = db.get(ReportRun, run_id)
    if run is None or run.status != "succeeded" or not run.file_path:
        raise ApiError(404, "not_found", "No file for this run")
    base = Path(settings.reports_output_dir).resolve()
    csv_path = (base / run.file_path).resolve()
    path = csv_path if output_format == "csv" else csv_path.with_suffix(".html")
    if not path.is_relative_to(base) or not path.is_file():
        raise ApiError(404, "not_found", "The file is no longer available")
    media = "text/csv" if output_format == "csv" else "text/html"
    return FileResponse(path, media_type=media, filename=f"{run.report_name}_{path.name}")


@router.get("/schedules")
def list_schedules(_: AdminOnly, db: Session = Depends(get_session)) -> list[ScheduleOut]:
    rows = db.scalars(select(ReportSchedule).order_by(ReportSchedule.report_name)).all()
    return [_schedule_out(row) for row in rows]


@router.put("/schedules/{report_name}")
def update_schedule(
    report_name: str,
    body: ScheduleUpdate,
    _: AdminOnly,
    db: Session = Depends(get_session),
) -> ScheduleOut:
    """Change when a report runs. The worker picks the change up within a minute."""
    if report_name not in REGISTRY:
        raise ApiError(404, "not_found", "Unknown report")
    try:
        CronTrigger.from_crontab(body.cron_expression, timezone=zone_of(body.timezone))
    except (ValueError, ReportError):
        raise ApiError(
            422, "invalid_schedule", "The cron expression or time zone is not valid"
        ) from None
    schedule = db.scalar(select(ReportSchedule).where(ReportSchedule.report_name == report_name))
    if schedule is None:
        schedule = ReportSchedule(report_name=report_name)
        db.add(schedule)
    schedule.cron_expression = body.cron_expression
    schedule.timezone = body.timezone
    schedule.is_enabled = body.is_enabled
    db.commit()
    return _schedule_out(schedule)


# ---- running a report ---------------------------------------------------------------------


@router.get("/{name}", response_model=None)
def run_on_demand(
    name: str,
    principal: Reader,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    output_format: Annotated[Literal["json", "csv"], Query(alias="format")] = "json",
    user_type: Literal["freelancer", "workhost", "organisation", "admin"] | None = None,
    skill: Annotated[str | None, Query(max_length=100)] = None,
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    min_ratings: Annotated[int, Query(ge=1, le=1000)] = 1,
    org_id: uuid.UUID | None = None,
) -> Response:
    """Run a report now and return it as JSON or CSV. Nothing is stored."""
    definition = _definition(name)
    org_filter = org_id
    if principal.user_type == "organisation":
        if not definition.org_scoped:
            raise ApiError(403, "forbidden", "You are not allowed to run this report")
        org_filter = principal.user_id  # an organisation only ever sees its own data
    if (date_from is None) != (date_to is None):
        raise ApiError(422, "report_window", "Give both from and to, or neither")
    timezone = settings.report_timezone
    try:
        if date_from is not None and date_to is not None:
            start, end = window_from_dates(date_from, date_to, timezone)
        else:
            start, end = default_window(datetime.now(UTC), timezone)
        params = ReportParams(
            start=start,
            end=end,
            timezone=timezone,
            user_type=user_type,
            skill=skill,
            currency=currency,
            min_ratings=min_ratings,
            org_id=org_filter,
        )
        result = build_report(db, name, params)
    except ReportError as exc:
        raise ApiError(422, "report_error", str(exc)) from None
    if output_format == "csv":
        filename = f"{name}_{start:%Y%m%d}_{end:%Y%m%d}.csv"
        return Response(
            to_csv(result),
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    return JSONResponse(to_json(name, definition.title, start, end, result))


@router.post("/{name}/run")
def run_and_store(
    name: str,
    body: RunRequest,
    response: Response,
    _: AdminOnly,
    db: Session = Depends(get_session),
    settings: Settings = Depends(get_settings),
) -> ReportRunOut:
    """Run a report for a window and keep its files. Repeating a finished run does nothing."""
    _definition(name)
    try:
        start, end = window_from_dates(body.date_from, body.date_to, settings.report_timezone)
    except ReportError as exc:
        raise ApiError(422, "report_window", str(exc)) from None
    run, executed = run_report(
        db,
        name,
        start,
        end,
        output_dir=Path(settings.reports_output_dir),
        timezone=settings.report_timezone,
    )
    response.status_code = 201 if executed else 200
    return _run_out(run)
