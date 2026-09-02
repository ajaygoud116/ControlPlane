"""Transport schemas for the /check endpoint.

Defines the stable HTTP request/response contract.
These schemas are transport-specific and do NOT duplicate domain logic.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class CheckRequest(BaseModel):
    """Request schema for POST /check.

    Maps directly to ControlPlaneRuntime.check() parameters.
    """

    request_text: str = Field(description="User's input text")
    response_text: str = Field(description="Model's output text")

    context: dict[str, Any] = Field(
        description="Context object (use_case, consequence, etc.)",
    )
    policy: dict[str, Any] = Field(
        description="Policy object (policy_id, version, allowed_interventions, etc.)",
    )

    model: str | None = Field(
        default=None,
        description="Model identifier (metadata only, not used for execution)",
    )
    provider: str | None = Field(
        default=None,
        description="Provider identifier (metadata only, not used for execution)",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Runtime telemetry (tokens, latency, cost)",
    )
    claims: list[dict[str, Any]] | None = Field(
        default=None,
        description="Structured claims for performance detection",
    )
    evidence: list[dict[str, Any]] | None = Field(
        default=None,
        description="Evidence for claim verification",
    )

    interaction_id: UUID | None = Field(
        default=None,
        description="Optional caller-assigned interaction identifier",
    )


class CheckResponse(BaseModel):
    """Response schema for POST /check.

    Contains the result of ControlPlaneRuntime.check() in a stable format.
    """

    interaction_id: str = Field(description="Interaction identifier")
    decision: str = Field(description="Terminal decision (ALLOW/BLOCK/ESCALATE)")
    released_response: str | None = Field(
        default=None,
        description="Response text released to user (None if blocked/escalated)",
    )
    blocked: bool = Field(description="True if BLOCK")
    escalated: bool = Field(description="True if ESCALATE")

    findings: list[dict[str, Any]] = Field(
        default_factory=list,
        description="All findings produced during this interaction",
    )
    decision_history: list[dict[str, Any]] = Field(
        default_factory=list,
        description="All decisions (DECIDE_0, DECIDE_1 if VERIFY path)",
    )

    intervention: dict[str, Any] | None = Field(
        default=None,
        description="Intervention applied (ALLOW/MODIFY/BLOCK/ESCALATE)",
    )
    outcome: dict[str, Any] | None = Field(
        default=None,
        description="Outcome recorded (RESPONSE_DELIVERED/ACTION_EXECUTED/HUMAN_DECISION)",
    )

    audit_persisted: bool = Field(
        description="True if audit record was durably persisted",
    )
    audit_persist_error: str | None = Field(
        default=None,
        description="Error message if persistence failed",
    )

    errors: list[str] = Field(
        default_factory=list,
        description="Errors or warnings during processing",
    )
