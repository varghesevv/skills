from datetime import datetime

from pydantic import BaseModel


class DownloadOut(BaseModel):
    platform: str  # "android"
    version: str  # X.Y.Z
    build: int
    released_at: datetime
    size_bytes: int
    sha256: str  # lower-case hex, so a tester can verify the file
    notes: str
    filename: str


class DownloadList(BaseModel):
    items: list[DownloadOut]
