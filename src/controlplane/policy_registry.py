"""Shared Policy Registry — single source of truth for all policy definitions.

All endpoints (/demo/run, /check/text, /live/run, traffic interceptor)
resolve policies through this registry. There must NOT be two independent
policy systems.

This module is owned by the controlplane package (not by api/ or any
specific endpoint). Any module that needs a policy resolves it here.
"""

from __future__ import annotations

from uuid import uuid5, NAMESPACE_DNS

from controlplane.schemas.enums import (
    FailureMode,
    InterventionAction,
    Scope,
)
from controlplane.schemas.policy import (
    AssuranceRequirements,
    HardConstraints,
    Policy,
)


def _build_policy_registry() -> dict[str, Policy]:
    """Build the canonical policy registry.

    Returns a dict mapping human-readable names to fully-typed Policy objects.
    These are the ONLY policies that the runtime will accept.
    """
    balanced = Policy(
        policy_id=uuid5(NAMESPACE_DNS, "balanced.v1"),
        version="1.0.0",
        scope=Scope.GLOBAL,
        assurance_requirements=AssuranceRequirements(
            low_consequence="basic_detection",
            medium_consequence="evidence_review",
            high_consequence="verified_evidence",
        ),
        hard_constraints=HardConstraints(
            blocked_patterns=["unsafe_content_detected", "secret_detected"],
            required_verifications=["pii_detected"],
            escalation_triggers=["conflicted", "unverifiable", "token_budget_exceeded", "cost_threshold_exceeded"],
        ),
        allowed_verifiers=["source_retrieval", "source_conflict_resolution"],
        allowed_interventions=[
            InterventionAction.ALLOW,
            InterventionAction.MODIFY,
            InterventionAction.BLOCK,
        ],
        failure_mode=FailureMode.ESCALATE,
    )

    strict = Policy(
        policy_id=uuid5(NAMESPACE_DNS, "strict.v1"),
        version="1.0.0",
        scope=Scope.GLOBAL,
        assurance_requirements=AssuranceRequirements(
            low_consequence="evidence_review",
            medium_consequence="verified_evidence",
            high_consequence="verified_evidence",
        ),
        hard_constraints=HardConstraints(
            blocked_patterns=[
                "unsafe_content_detected",
                "secret_detected",
                "pii_detected",
                "conflicted",
            ],
            required_verifications=[],
            escalation_triggers=["unverifiable", "insufficient_evidence"],
        ),
        allowed_verifiers=["source_retrieval", "source_conflict_resolution"],
        allowed_interventions=[
            InterventionAction.ALLOW,
            InterventionAction.BLOCK,
        ],
        failure_mode=FailureMode.BLOCK,
    )

    lenient = Policy(
        policy_id=uuid5(NAMESPACE_DNS, "lenient.v1"),
        version="1.0.0",
        scope=Scope.GLOBAL,
        assurance_requirements=AssuranceRequirements(
            low_consequence="basic_detection",
            medium_consequence="basic_detection",
            high_consequence="evidence_review",
        ),
        hard_constraints=HardConstraints(
            blocked_patterns=["unsafe_content_detected"],
            required_verifications=[],
            escalation_triggers=[],
        ),
        allowed_verifiers=["source_retrieval"],
        allowed_interventions=[
            InterventionAction.ALLOW,
            InterventionAction.MODIFY,
            InterventionAction.BLOCK,
        ],
        failure_mode=FailureMode.ALLOW,
    )

    return {
        "Balanced": balanced,
        "Strict": strict,
        "Lenient": lenient,
    }


POLICY_REGISTRY: dict[str, Policy] = _build_policy_registry()


def get_policy(name: str) -> Policy | None:
    """Look up a policy by name. Returns None if not found."""
    return POLICY_REGISTRY.get(name)


def get_default_policy() -> Policy:
    """Return the default (Balanced) policy.

    Used by /check/text, traffic interceptor, and any endpoint that
    needs a safe default governance configuration.
    """
    return POLICY_REGISTRY["Balanced"]


def list_policy_names() -> list[str]:
    """List all registered policy names."""
    return list(POLICY_REGISTRY.keys())
