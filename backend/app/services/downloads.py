"""Test builds of the mobile app, served only to logged-in people.

Layout of the downloads folder (`DOWNLOADS_DIR`, mounted read-only into the API container):

    index.json                                   {"android": [{"version", "build", ...}, ...]}
    android/<version>/<file>.apk

`scripts/add-download.py` writes both. The API never lists the folder: only files named in
`index.json` can be fetched, the version must be `X.Y.Z`, and the resolved path must stay inside
the folder, so no request can reach any other file.
"""

import json
import logging
import math
import re
import time
from collections import defaultdict, deque
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, StringConstraints, ValidationError

from app.core.config import Settings
from app.core.errors import ApiError
from app.schemas.downloads import DownloadOut

logger = logging.getLogger(__name__)

VERSION_RE = re.compile(r"^\d{1,5}\.\d{1,5}\.\d{1,5}$")
FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,100}\.apk$")
APK_MEDIA_TYPE = "application/vnd.android.package-archive"
WINDOW_SECONDS = 3600


class IndexEntry(BaseModel):
    version: Annotated[str, StringConstraints(pattern=VERSION_RE.pattern)]
    build: int
    released_at: datetime
    size_bytes: int
    sha256: Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
    notes: Annotated[str, StringConstraints(max_length=4000)] = ""
    file: Annotated[str, StringConstraints(pattern=FILENAME_RE.pattern)]


class Index(BaseModel):
    android: list[IndexEntry] = []


def _base(settings: Settings) -> Path | None:
    return Path(settings.downloads_dir).resolve() if settings.downloads_dir else None


def _version_key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def read_index(settings: Settings) -> list[IndexEntry]:
    """The published Android builds, newest first. Empty when the feature is off or not set up."""
    base = _base(settings)
    if base is None or not (base / "index.json").is_file():
        return []
    try:
        index = Index.model_validate(json.loads((base / "index.json").read_text("utf-8")))
    except (OSError, ValueError, ValidationError):
        # Never log the content of the file, only that it is unusable.
        logger.error("downloads index.json is unreadable or invalid")
        return []
    return sorted(index.android, key=lambda e: (_version_key(e.version), e.build), reverse=True)


def list_downloads(settings: Settings) -> list[DownloadOut]:
    return [
        DownloadOut(
            platform="android",
            version=entry.version,
            build=entry.build,
            released_at=entry.released_at,
            size_bytes=entry.size_bytes,
            sha256=entry.sha256,
            notes=entry.notes,
            filename=entry.file,
        )
        for entry in read_index(settings)
    ]


def android_file(settings: Settings, version: str) -> tuple[Path, IndexEntry]:
    """The file for a published version, or 404. Nothing outside the index can be reached."""
    not_found = ApiError(404, "not_found", "That build is not available")
    base = _base(settings)
    if base is None or not VERSION_RE.fullmatch(version):
        raise not_found
    entry = next((e for e in read_index(settings) if e.version == version), None)
    if entry is None:
        raise not_found
    path = (base / "android" / entry.version / entry.file).resolve()
    if not path.is_relative_to(base) or not path.is_file():
        raise not_found
    logger.info("download android version=%s", entry.version)  # no person is recorded
    return path, entry


class DownloadLimiter:
    """At most `limit` downloads per person per hour. Kept in this process's memory, which is
    enough for one API instance; with several instances each allows its own share."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._seen: dict[str, deque[float]] = defaultdict(deque)

    def check(self, person: str, limit: int) -> None:
        now = self._clock()
        times = self._seen[person]
        while times and now - times[0] >= WINDOW_SECONDS:
            times.popleft()
        if len(times) >= limit:
            wait = math.ceil(WINDOW_SECONDS - (now - times[0]))
            raise ApiError(
                429,
                "download_limit_reached",
                "You have downloaded too many files. Try again later.",
                headers={"Retry-After": str(max(wait, 1))},
            )
        times.append(now)

    def reset(self) -> None:
        self._seen.clear()


limiter = DownloadLimiter()
