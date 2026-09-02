"""Intervention schema — what ControlPlane actually does."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from controlplane.schemas.enums import InterventionAction, ModificationType


class Intervention(BaseModel):
    """What ControlPlane actually does to the AI response or action.

    Decision determines the action. Intervention records what was done.
    They are NOT the same thing — a decision to BLOCK may be recorded
    as an intervention with action=BLOCK.
    """

    intervention_id: UUID
    interaction_id: UUID
    decision_id: UUID = Field(description="Decision that led to this intervention")

    action: InterventionAction = Field(description="What was done")

    modification_type: ModificationType | None = Field(
        default=None,
        description="If action is MODIFY, what kind of modification was applied",
    )
    modification_detail: str | None = Field(
        default=None,
        description="Description of the modification applied",
    )

    blocked_reason: str | None = Field(
        default=None,
        description="If action is BLOCK, why the interaction was blocked",
    )
    escalation_reason: str | None = Field(
        default=None,
        description="If action is ESCALATE, why escalation was needed",
    )

    applied_at: datetime

    model_config = {"extra": "forbid"}
