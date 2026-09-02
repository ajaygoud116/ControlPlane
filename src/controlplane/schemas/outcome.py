"""Outcome schema — what actually happened after intervention."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from controlplane.schemas.enums import OutcomeType


class Outcome(BaseModel):
    """Records eventual observable reality after ControlPlane intervention.

    ControlPlane can itself be wrong. Outcome data is essential for
    evaluating whether decisions and interventions were correct.
    """

    outcome_id: UUID
    interaction_id: UUID
    intervention_id: UUID | None = Field(
        default=None,
        description="Intervention this outcome is associated with (None if no intervention occurred)",
    )

    outcome_type: OutcomeType = Field(description="What actually happened")

    description: str = Field(
        description="Human-readable description of the outcome"
    )
    evidence: dict[str, Any] = Field(
        default_factory=dict,
        description="Observable evidence supporting this outcome assessment",
    )

    observed_at: datetime

    model_config = {"extra": "forbid"}
