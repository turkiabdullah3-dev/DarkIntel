"""Validated dashboard write payloads."""

from pydantic import BaseModel, Field


class AnalystNoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=500)
    description: str | None = Field(default=None, max_length=10_000)
    timestamp: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=100)


class AnalystGraphNodeCreate(BaseModel):
    type: str = Field(pattern="^(analyst_entity|threat_actor|organization)$")
    value: str = Field(min_length=1, max_length=4_000)
    label: str = Field(min_length=1, max_length=500)


class AnalystGraphEdgeCreate(BaseModel):
    source: str = Field(min_length=36, max_length=36)
    target: str = Field(min_length=36, max_length=36)
    relationship: str = Field(min_length=1, max_length=64)
    confidence: float = Field(default=0.75, ge=0, le=1)
