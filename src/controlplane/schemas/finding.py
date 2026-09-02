"""Finding schema — structured detector output."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from controlplane.schemas.enums import (
    CostState,
    FindingDimension,
    PerformanceState,
    PIIState,
    PolicyState,
    ResponsibilityState,
    RuntimeState,
)

_DIMENSION_STATE_MAP: dict[FindingDimension, type] = {
    FindingDimension.PERFORMANCE: PerformanceState,
    FindingDimension.PII: PIIState,
    FindingDimension.POLICY: PolicyState,
    FindingDimension.RUNTIME: RuntimeState,
    FindingDimension.COST: CostState,
    FindingDimension.RESPONSIBILITY: ResponsibilityState,
}


class FindingEvidence(BaseModel):
    """Evidence supporting or contradicting the finding."""

    claim_text: str | None = Field(
        default=None, description="The claim or content that was evaluated"
    )
    source_ids: list[str] = Field(
        default_factory=list, description="Identifiers of evidence sources consulted"
    )
    source_quality: str | None = Field(
        default=None, description="Assessed quality of available evidence"
    )
    counter_evidence: list[str] = Field(
        default_factory=list, description="Any evidence contradicting the claim"
    )
    quality_assessment: dict | None = Field(
        default=None,
        description="V2-12 structured evidence quality assessment "
        "(authority, relevance, provenance, freshness, corroboration, consistency)",
    )

    model_config = {"extra": "forbid"}


class FindingMeasurement(BaseModel):
    """Quantitative measurements produced by the detector."""

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    model_calls: int | None = Field(default=None, ge=0)
    tool_calls: int | None = Field(default=None, ge=0)
    latency_ms: Annotated[float, Field(ge=0)] | None = None
    estimated_cost_usd: Annotated[float, Field(ge=0)] | None = None

    model_config = {"extra": "forbid"}


class FindingAmbiguity(BaseModel):
    """Why this finding is not definitive."""

    reasons: list[str] = Field(
        default_factory=list,
        description="Specific reasons the finding is ambiguous or uncertain",
    )
    conflicting_sources: int = Field(
        default=0, ge=0, description="Number of conflicting evidence sources"
    )
    evidence_gaps: list[str] = Field(
        default_factory=list, description="Specific evidence that was missing"
    )

    model_config = {"extra": "forbid"}


class Finding(BaseModel):
    """Structured output from a detector.

    A finding reports what was observed and what property the detector identified.
    It does NOT determine what should be done about it.

    INVARIANT: dimension and state must be consistent.
      PERFORMANCE -> PerformanceState
      PII -> PIIState
      POLICY -> PolicyState
      RUNTIME -> RuntimeState
    """

    finding_id: UUID
    interaction_id: UUID
    detector_id: str = Field(description="Unique identifier of the detector that produced this")
    detector_version: str = Field(description="Version of the detector")
    dimension: FindingDimension
    finding_type: str = Field(
        description="Specific type within the dimension (e.g. 'claim_accuracy', 'email_detected')"
    )

    state: PerformanceState | PIIState | PolicyState | RuntimeState | CostState | ResponsibilityState = Field(
        description="Detector conclusion about this observation"
    )

    observation_ids: list[UUID] = Field(
        description="Observations this finding is based on"
    )
    evidence: FindingEvidence = Field(default_factory=FindingEvidence)
    measurement: FindingMeasurement = Field(default_factory=FindingMeasurement)
    ambiguity: FindingAmbiguity = Field(default_factory=FindingAmbiguity)

    explanation: str = Field(
        description="Human-readable explanation of what the detector found"
    )
    detected_at: datetime
    latency_ms: Annotated[float, Field(ge=0)] = Field(
        description="Time the detector took to produce this finding"
    )
    cost_usd: Annotated[float, Field(ge=0)] = Field(
        description="Cost of running the detector for this finding"
    )

    @model_validator(mode="after")
    def _validate_dimension_state_consistency(self) -> Finding:
        expected_type = _DIMENSION_STATE_MAP[self.dimension]
        if not isinstance(self.state, expected_type):
            raise ValueError(
                f"dimension={self.dimension.value!r} requires "
                f"{expected_type.__name__}, got {type(self.state).__name__}"
            )
        return self

    model_config = {"extra": "forbid"}
