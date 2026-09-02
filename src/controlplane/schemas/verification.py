"""Verification schemas — request and result for additional verification."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field

from controlplane.schemas.enums import UncertaintyType, VerificationResolution, VerificationStatus


class VerificationRequest(BaseModel):
    """A specific uncertainty that needs to be resolved.

    A verification request must state WHAT specifically needs to be established.
    It is NOT equivalent to "check this response."
    """

    request_id: UUID
    interaction_id: UUID
    decision_id: UUID
    finding_id: UUID

    uncertainty_type: UncertaintyType = Field(
        description="What specific uncertainty is being resolved"
    )
    specific_question: str = Field(
        description="Precise question the verifier must answer"
    )

    evidence_scope: list[str] = Field(
        default_factory=list,
        description="Specific evidence sources or types to consult",
    )
    timeout_ms: Annotated[float, Field(gt=0)] = Field(
        description="Maximum time allowed for this verification"
    )
    max_cost_usd: Annotated[float, Field(ge=0)] = Field(
        description="Maximum cost allowed for this verification"
    )

    requested_at: datetime

    model_config = {"extra": "forbid"}


class VerificationEvidence(BaseModel):
    """Evidence gathered during verification."""

    sources_consulted: list[str] = Field(
        default_factory=list, description="Evidence sources that were consulted"
    )
    source_quality: str | None = Field(
        default=None, description="Assessed quality of evidence sources"
    )
    raw_evidence: dict[str, Any] = Field(
        default_factory=dict, description="Raw evidence data collected"
    )

    model_config = {"extra": "forbid"}


class VerificationResult(BaseModel):
    """Result of a verification attempt."""

    result_id: UUID
    request_id: UUID
    verifier: str = Field(description="Which verifier performed this verification")

    status: VerificationStatus = Field(
        description="Whether the verification completed successfully"
    )
    resolution: VerificationResolution = Field(
        description="What the verification determined"
    )

    evidence: VerificationEvidence = Field(default_factory=VerificationEvidence)
    explanation: str = Field(
        description="Human-readable explanation of the verification result"
    )

    latency_ms: Annotated[float, Field(ge=0)] = Field(
        description="Time the verification took"
    )
    cost_usd: Annotated[float, Field(ge=0)] = Field(
        description="Cost of performing this verification"
    )

    failure_reason: str | None = Field(
        default=None,
        description="If status is FAILED or TIMEOUT, why",
    )

    completed_at: datetime

    model_config = {"extra": "forbid"}
