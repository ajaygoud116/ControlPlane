"""AuditRecord schema — immutable snapshot of a completed interaction for audit."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from controlplane.schemas.context import Context
from controlplane.schemas.decision import Decision
from controlplane.schemas.finding import Finding
from controlplane.schemas.intervention import Intervention
from controlplane.schemas.interaction import Interaction
from controlplane.schemas.observation import Observation
from controlplane.schemas.outcome import Outcome


class AuditRecord(BaseModel):
    """Immutable snapshot of a completed interaction for audit purposes.

    AuditRecord captures the final state of an interaction after all processing
    is complete. It is designed to be persisted and provides a complete audit trail
    for debugging, compliance, and evaluation.

    This schema is frozen (immutable) to represent the persisted snapshot.
    """

    audit_id: UUID = Field(default_factory=uuid4)
    interaction_id: UUID

    interaction: Interaction = Field(description="Snapshot of the completed interaction")
    observations: list[Observation] = Field(
        default_factory=list,
        description="All observations created during this interaction",
    )
    findings: list[Finding] = Field(
        default_factory=list,
        description="All findings produced during this interaction",
    )
    context: Context = Field(description="Context as applied to this interaction")

    policy_id: UUID = Field(description="Policy that was applied to this interaction")
    policy_version: str = Field(description="Version of the policy that was applied")
    policy_snapshot: dict[str, Any] | None = Field(
        default=None,
        description="Full policy configuration snapshot at decision time. "
        "Enables audit reconstruction even if policy changes later.",
    )

    decisions: list[Decision] = Field(
        default_factory=list,
        description="All decisions, including pre/post-verification",
    )
    final_decision_id: UUID = Field(description="Terminal decision ID")

    verification_events: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Verification events from verify_and_redecide audit_log",
    )

    intervention: Intervention | None = None
    outcome: Outcome | None = None

    released_response: str | None = Field(
        default=None,
        description="The response text actually released to the user after intervention. "
        "None for BLOCK/ESCALATE. Original for ALLOW. Modified for MODIFY.",
    )

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    frozen_v1_version: str = Field(
        description="ControlPlane version that produced this audit record",
    )

    model_config = {"extra": "forbid", "frozen": True}
