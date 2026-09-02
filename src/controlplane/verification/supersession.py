"""Finding Supersession — Result → Derived Finding mapping and active set projection.

THIS IS THE MOST IMPORTANT PHASE 6 SEMANTIC.

A successful verification result creates a NEW derived Finding.
It NEVER mutates the original Finding.

The active decision set is projected:
  active_after = active_before - {target_finding} + {derived_finding}

Historical/audit records preserve ALL findings.
The active set contains current non-superseded findings supplied to DECIDE.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from controlplane.schemas.enums import (
    FindingDimension,
    PerformanceState,
    VerificationResolution,
    VerificationStatus,
)
from controlplane.schemas.finding import Finding, FindingAmbiguity, FindingEvidence, FindingMeasurement
from controlplane.schemas.verification import VerificationResult


# Resolution → Finding state mapping
_RESOLUTION_TO_STATE: dict[VerificationResolution, PerformanceState] = {
    VerificationResolution.SUPPORTED: PerformanceState.SUPPORTED,
    VerificationResolution.CONTRADICTED: PerformanceState.CONTRADICTED,
    VerificationResolution.CONFLICTED: PerformanceState.CONFLICTED,
    VerificationResolution.INSUFFICIENT_EVIDENCE: PerformanceState.INSUFFICIENT_EVIDENCE,
    VerificationResolution.UNVERIFIABLE: PerformanceState.UNVERIFIABLE,
}

# Explanation prefix by resolution
_RESOLUTION_PREFIX: dict[VerificationResolution, str] = {
    VerificationResolution.SUPPORTED: "Verified: ",
    VerificationResolution.CONTRADICTED: "Verified contradiction: ",
    VerificationResolution.CONFLICTED: "Verified conflict: ",
    VerificationResolution.INSUFFICIENT_EVIDENCE: "Verification insufficient: ",
    VerificationResolution.UNVERIFIABLE: "Verified unverifiable: ",
}


def derive_finding(
    original_finding: Finding,
    result: VerificationResult,
) -> Finding:
    """Create a derived Finding from a VerificationResult.

    The derived Finding:
    - Has a NEW finding_id
    - References the same interaction_id
    - Has dimension=PERFORMANCE
    - Has finding_type="verification"
    - Has detector_id=verifier name
    - Has state mapped from result.resolution
    - NEVER mutates the original Finding

    Args:
        original_finding: The finding that was verified (immutable).
        result: The verification result.

    Returns:
        A NEW Finding representing the verification outcome.
    """
    if result.status in (VerificationStatus.FAILED, VerificationStatus.TIMEOUT):
        raise ValueError(
            f"Cannot derive finding from {result.status} result"
        )

    state = _RESOLUTION_TO_STATE.get(result.resolution)
    if state is None:
        raise ValueError(f"Unknown resolution: {result.resolution}")

    prefix = _RESOLUTION_PREFIX.get(result.resolution, "")
    now = datetime.now(timezone.utc)

    return Finding(
        finding_id=uuid4(),
        interaction_id=original_finding.interaction_id,
        detector_id=result.verifier,
        detector_version="1.0.0",
        dimension=FindingDimension.PERFORMANCE,
        finding_type="verification",
        state=state,
        observation_ids=[],
        evidence=FindingEvidence(
            claim_text=original_finding.evidence.claim_text,
            source_ids=result.evidence.sources_consulted,
            source_quality=result.evidence.source_quality,
            counter_evidence=[],
        ),
        measurement=FindingMeasurement(
            latency_ms=result.latency_ms,
            estimated_cost_usd=result.cost_usd,
        ),
        ambiguity=FindingAmbiguity(),
        explanation=f"{prefix}{result.explanation}",
        detected_at=result.completed_at or now,
        latency_ms=result.latency_ms,
        cost_usd=result.cost_usd,
    )


def supersede_active_findings(
    active_findings: list[Finding],
    target_finding_id: uuid4,
    derived_finding: Finding,
) -> list[Finding]:
    """Project the active finding set after verification.

    active_after = active_before - {target_finding} + {derived_finding}

    The original finding is NOT deleted from history.
    It is removed from the ACTIVE decision set.

    Args:
        active_findings: Current active findings list.
        target_finding_id: ID of the finding being superseded.
        derived_finding: The new derived finding from verification.

    Returns:
        New list with target removed and derived added.
    """
    result = [f for f in active_findings if f.finding_id != target_finding_id]
    result.append(derived_finding)
    return result


def is_terminal_verification_result(result: VerificationResult) -> bool:
    """Check if a verification result is terminal (no further verification needed).

    A result is terminal if:
    - status is FAILED or TIMEOUT (operational failure)
    - resolution is SUPPORTED, CONTRADICTED, or UNVERIFIABLE (substantive conclusion)

    A result is NOT terminal if:
    - resolution is INSUFFICIENT_EVIDENCE or CONFLICTED (could potentially be retried,
      but V1 max_depth=1 prevents this)
    """
    if result.status in (VerificationStatus.FAILED, VerificationStatus.TIMEOUT):
        return True
    if result.resolution in (
        VerificationResolution.SUPPORTED,
        VerificationResolution.CONTRADICTED,
        VerificationResolution.UNVERIFIABLE,
    ):
        return True
    return False
