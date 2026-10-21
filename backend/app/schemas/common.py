import uuid
from dataclasses import dataclass
from typing import Annotated

from fastapi import Query
from pydantic import BaseModel


class Page[T](BaseModel):
    """A page of results: {items, total, page, page_size}."""

    items: list[T]
    total: int
    page: int
    page_size: int


@dataclass(frozen=True)
class Pagination:
    page: int
    page_size: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


def pagination(
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> Pagination:
    return Pagination(page, page_size)


class LabelOut(BaseModel):
    id: uuid.UUID
    label_name: str
    label_type: str
    is_active: bool = True
