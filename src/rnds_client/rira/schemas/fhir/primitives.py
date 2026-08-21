from __future__ import annotations

from pydantic import BaseModel


class Coding(BaseModel):
    system: str
    version: str | None = None
    code: str
    display: str | None = None


class CodeableConcept(BaseModel):
    coding: list[Coding]


class Identifier(BaseModel):
    system: str
    value: str


class IdentifierRef(BaseModel):
    identifier: Identifier


class Meta(BaseModel):
    lastUpdated: str | None = None
    profile: list[str] | None = None


class Period(BaseModel):
    start: str
    end: str
