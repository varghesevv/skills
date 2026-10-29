from typing import Annotated

from fastapi import APIRouter, Depends, Response

from app.core.config import Settings, get_settings
from app.schemas.app_config import AppConfig
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
