"""Context schema — situational information for decision-making."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from controlplane.schemas.enums import (
    Consequence,
    DataSensitivity,
    DownstreamAction,
    Reversibility,
)


class Context(BaseModel):
    """Situational information that affects how findings should be interpreted.

    Context does NOT determine the decision. It provides situational
    information that the decision engine uses alongside findings and policy.
    """

    context_id: UUID
    use_case: str = Field(
        description="Use case identifier (e.g. 'customer_support', 'internal_knowledge', 'decision_support')"
    )
    consequence: Consequence = Field(
        description="How severe the outcome of a wrong decision would be"
    )
    reversibility: Reversibility = Field(
        description="Whether the downstream action can be undone"
    )
    downstream_action: DownstreamAction = Field(
        description="What the AI response triggers downstream"
    )
    data_sensitivity: DataSensitivity = Field(
        description="Sensitivity level of data involved in this interaction"
    )
    latency_budget_ms: float = Field(
        gt=0,
        description="Maximum acceptable end-to-end latency in milliseconds",
    )
    jurisdiction: str | None = Field(
        default=None,
        description="Applicable regulatory jurisdiction (e.g. 'US', 'EU', 'UK')",
    )

    model_config = {"extra": "forbid"}
