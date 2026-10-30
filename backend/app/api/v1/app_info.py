from typing import Annotated

from fastapi import APIRouter, Depends, Response
from fastapi.responses import FileResponse

from app.api.deps import get_principal
from app.core.config import Settings, get_settings
from app.core.security import Principal
from app.schemas.app_config import AppConfig
from app.schemas.downloads import DownloadList
from app.services import downloads
from app.services.app_config import build_app_config

router = APIRouter(prefix="/app", tags=["app"])

# Words and versions change rarely and hold nothing personal, so clients and proxies may keep them.
CACHE_CONTROL = "public, max-age=300"


@router.get("/config")
def app_config(
    response: Response, settings: Annotated[Settings, Depends(get_settings)]
) -> AppConfig:
    """Public (no login): the login screen needs the right words before anyone signs in."""
    response.headers["Cache-Control"] = CACHE_CONTROL
    return build_app_config(settings)


@router.get("/downloads")
def list_downloads(
    _: Annotated[Principal, Depends(get_principal)],
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DownloadList:
    """Test builds of the mobile app. Any logged-in person; nobody else can see them."""
    response.headers["Cache-Control"] = "private, no-store"
    return DownloadList(items=downloads.list_downloads(settings))


@router.get("/downloads/android/{version}", response_class=FileResponse)
def download_android(
    version: str,
    principal: Annotated[Principal, Depends(get_principal)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> FileResponse:
    """The APK of one published version, with the bearer token like every other request."""
    path, entry = downloads.android_file(settings, version)
    downloads.limiter.check(
        f"{principal.user_type}:{principal.user_id}", settings.download_max_per_hour
    )
    return FileResponse(
        path,
        media_type=downloads.APK_MEDIA_TYPE,
        filename=entry.file,
        headers={"Cache-Control": "private, no-store"},
    )
