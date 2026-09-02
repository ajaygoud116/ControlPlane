"""Decision schema — deterministic decision engine output."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

from controlplane.schemas.enums import DecisionAction


class Decision(BaseModel):
    """Deterministic decision based on findings, context, and policy.

    Decision determines: ALLOW, VERIFY, BLOCK, or ESCALATE.
    It is based on comparing current assurance (from findings) against
    required assurance (from policy + context), NOT on a numerical risk score.
    """

    decision_id: UUID
    interaction_id: UUID
    decision_version: str = Field(
        description="Version of the decision logic that produced this decision"
    )
    decision: DecisionAction = Field(description="What the decision engine decided")

    reason_codes: list[str] = Field(
        description="Structured reason codes explaining why this decision was made"
    )

    finding_ids: list[UUID] = Field(
        description="Finding IDs that contributed to this decision"
    )
    policy_id: UUID = Field(description="Policy that was applied")
    policy_version: str = Field(description="Version of the policy that was applied")

    required_assurance: str = Field(
        description="Assurance level required by policy for this context"
    )
    current_assurance: str = Field(
        description="Assurance level achieved by current findings"
    )

    selected_verifier: str | None = Field(
        default=None,
        description="Verifier selected if decision is VERIFY (None otherwise)",
    )

    decided_at: datetime

    model_config = {"extra": "forbid"}
