"""Envelopes and pagination helpers shared by all endpoints."""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Message(BaseModel):
    message: str
    detail: str | None = None


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    pages: int


class PaginationQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=200)


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    environment: str
    database: str
    timestamp: str


class OptionItem(BaseModel):
    value: str
    label: str
    count: int | None = None
