"""Policy schema — configurable, versioned rules for decision-making."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field

from controlplane.schemas.enums import FailureMode, InterventionAction, Scope


class AssuranceRequirements(BaseModel):
    """What level of assurance is required for different consequence levels."""

    low_consequence: str = Field(
        default="basic_detection",
        description="Required assurance level for low-consequence interactions",
    )
    medium_consequence: str = Field(
        default="evidence_review",
        description="Required assurance level for medium-consequence interactions",
    )
    high_consequence: str = Field(
        default="verified_evidence",
        description="Required assurance level for high-consequence interactions",
    )

    model_config = {"extra": "forbid"}


class HardConstraints(BaseModel):
    """Absolute rules that override normal decision flow."""

    blocked_patterns: list[str] = Field(
        default_factory=list,
        description="Patterns or conditions that always trigger BLOCK",
    )
    required_verifications: list[str] = Field(
        default_factory=list,
        description="Conditions that always require verification before allowing",
    )
    escalation_triggers: list[str] = Field(
        default_factory=list,
        description="Conditions that always trigger escalation",
    )

    model_config = {"extra": "forbid"}


class Policy(BaseModel):
    """Configurable, versioned policy for decision-making.

    Policy defines what is allowed, what requires verification,
    and what should be blocked. It is NOT an IAM or regulatory engine.
    """

    policy_id: UUID
    version: str = Field(description="Policy version string (e.g. '1.0.0')")
    scope: Scope = Field(description="What this policy applies to")
    use_case: str | None = Field(
        default=None,
        description="Specific use case this policy applies to (if scope is USE_CASE)",
    )
    jurisdiction: str | None = Field(
        default=None,
        description="Jurisdiction this policy applies to (if scope is JURISDICTION)",
    )

    assurance_requirements: AssuranceRequirements = Field(
        default_factory=AssuranceRequirements,
        description="Assurance requirements by consequence level",
    )
    hard_constraints: HardConstraints = Field(
        default_factory=HardConstraints,
        description="Absolute rules that cannot be overridden",
    )

    allowed_verifiers: list[str] = Field(
        default_factory=list,
        description="Verifiers permitted under this policy",
    )
    verification_budget_ms: float = Field(
        gt=0,
        default=5000.0,
        description="Maximum verification time budget in milliseconds",
    )
    verification_budget_usd: float = Field(
        ge=0,
        default=0.01,
        description="Maximum verification cost budget in USD",
    )

    allowed_interventions: list[InterventionAction] = Field(
        default_factory=lambda: [InterventionAction.ALLOW, InterventionAction.BLOCK],
        description="Interventions this policy permits",
    )
    failure_mode: FailureMode = Field(
        default=FailureMode.ESCALATE,
        description="How to behave when ControlPlane itself fails",
    )

    model_config = {"extra": "forbid"}
