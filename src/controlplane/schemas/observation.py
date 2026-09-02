"""Observation schema — represents only what was observed, no interpretation."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field

from controlplane.schemas.enums import ObservationType


class Observation(BaseModel):
    """A single raw observation from runtime.

    Observation represents ONLY something actually observable.
    It must not contain interpretation, risk judgment, or conclusion.
    """

    observation_id: UUID
    interaction_id: UUID
    observation_type: ObservationType
    timestamp: datetime
    source: str = Field(description="Component or system that produced this observation")
    payload: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured observation data specific to observation_type",
    )
    duration_ms: Annotated[float, Field(ge=0)] | None = Field(
        default=None, description="Duration of the observed event in milliseconds"
    )

    model_config = {"extra": "forbid"}
