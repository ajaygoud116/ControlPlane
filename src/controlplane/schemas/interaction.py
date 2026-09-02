"""Interaction schema — canonical aggregation object for a single AI interaction."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from controlplane.schemas.context import Context
from controlplane.schemas.decision import Decision
from controlplane.schemas.finding import Finding
from controlplane.schemas.intervention import Intervention
from controlplane.schemas.observation import Observation
from controlplane.schemas.outcome import Outcome


class Interaction(BaseModel):
    """Canonical aggregation object for a single AI interaction.

    Interaction captures the complete lifecycle of one AI request/response pair,
    including all observations, findings, decisions, and outcomes produced during
    ControlPlane processing.

    Lifecycle: Created when AI I/O arrives. Populated by detectors, decision engine,
    and intervention executor. Persisted as part of audit record.
    """

    interaction_id: UUID = Field(default_factory=uuid4)
    request_text: str
    response_text: str
    model: str | None = None
    provider: str | None = None
    context: Context

    observations: list[Observation] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    decisions: list[Decision] = Field(default_factory=list)

    final_decision_id: UUID | None = Field(
        default=None,
        description="Points to the terminal decision (populated after decision engine completes)",
    )

    intervention: Intervention | None = None
    outcome: Outcome | None = None

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"extra": "forbid"}
