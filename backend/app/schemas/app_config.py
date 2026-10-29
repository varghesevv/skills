from pydantic import BaseModel


class Terminology(BaseModel):
    profile: str
    # Words and web-address slugs by key, for example `workhost`, `organisation_path`.
    # Stored `user_type` values and API paths never change with the wording.
    terms: dict[str, str]


class AppVersions(BaseModel):
    min_version: str  # apps older than this must ask the person to update
    latest_version: str


class AppConfig(BaseModel):
    terminology: Terminology
    app: AppVersions
