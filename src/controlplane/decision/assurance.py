"""Assurance predicates — deterministic evaluation of finding states against requirements.

Assurance is NOT ordinal. These are explicit named predicates with exact semantics.

Semantic model for finding states:
    CLEAN/ABSENCE: NO_PII_DETECTED, RESPONSIBILITY_CLEAN, POLICY_UNRESOLVED,
                   COST_WITHIN_BUDGET, COST_UNAVAILABLE, RUNTIME_OBSERVED
        Meaning: "I checked and found nothing" or "I could not check"
        Should NOT satisfy basic_detection — they are not evidence of risk.

    EVIDENCE: PII_DETECTED, SECRET_DETECTED, UNSAFE_CONTENT_DETECTED,
              INJECTION_DETECTED, POLICY_VIOLATION, POLICY_MATCH,
              COST_THRESHOLD_EXCEEDED, TOKEN_BUDGET_EXCEEDED,
              LATENCY_THRESHOLD_EXCEEDED, RUNTIME_ANOMALY,
              SUPPORTED, CONTRADICTED, CONFLICTED,
              INSUFFICIENT_EVIDENCE, UNVERIFIABLE
        Meaning: "I found something" or "I verified something"
        CAN satisfy basic_detection — they represent actual detection or verification.

    UNKNOWN: Any (dimension, state) not in RiskRegistry
        Meaning: "I don't know what this state means"
        Triggers fail-closed ESCALATE — never satisfies assurance.
"""

from __future__ import annotations

from controlplane.schemas.enums import PerformanceState
from controlplane.schemas.finding import Finding


# States that represent ABSENCE of risk — "I checked, nothing found."
# These must NOT satisfy basic_detection.
_ABSENCE_STATES: set[str] = {
    "no_pii_detected",
    "responsibility_clean",
    "policy_unresolved",
    "cost_within_budget",
    "cost_unavailable",
    "runtime_observed",
}


def evaluate_assurance(findings: list[Finding], required_assurance: str) -> bool:
    """Evaluate whether findings satisfy the required assurance level.

    Returns True if the assurance requirement is satisfied.
    Returns False if it is not.

    This is NOT a numeric comparison. It is explicit condition matching.
    """
    perf = [f for f in findings if f.dimension.value == "performance"]

    if required_assurance == "basic_detection":
        return _check_basic_detection(findings)
    elif required_assurance == "evidence_review":
        return _check_evidence_review(perf)
    elif required_assurance == "verified_evidence":
        return _check_verified_evidence(perf)
    return False


def derive_current_assurance(findings: list[Finding]) -> str:
    """Derive a named assurance level from finding states.

    Returns a string describing the current assurance condition.
    This is NOT a numeric score.
    """
    perf = [f for f in findings if f.dimension.value == "performance"]
    if not perf:
        return "none"
    states = {f.state for f in perf}
    if all(f.state == PerformanceState.SUPPORTED for f in perf):
        return "evidence_support_available"
    if PerformanceState.CONTRADICTED in states:
        return "evidence_conflict_present"
    if PerformanceState.CONFLICTED in states:
        return "unresolved_evidence_conflict"
    if PerformanceState.INSUFFICIENT_EVIDENCE in states:
        return "evidence_gap_present"
    if PerformanceState.UNVERIFIABLE in states:
        return "verification_mechanism_insufficient"
    return "detected"


def _check_basic_detection(findings: list[Finding]) -> bool:
    """basic_detection: at least one EVIDENCE finding exists.

    Absence/clean/unresolved states do NOT satisfy basic_detection.
    Only states that represent actual detection or verification count.

    Absence states (do NOT satisfy):
        NO_PII_DETECTED, RESPONSIBILITY_CLEAN, POLICY_UNRESOLVED,
        COST_WITHIN_BUDGET, COST_UNAVAILABLE, RUNTIME_OBSERVED

    Evidence states (DO satisfy):
        PII_DETECTED, SECRET_DETECTED, UNSAFE_CONTENT_DETECTED,
        POLICY_VIOLATION, POLICY_MATCH, COST_THRESHOLD_EXCEEDED,
        TOKEN_BUDGET_EXCEEDED, LATENCY_THRESHOLD_EXCEEDED,
        RUNTIME_ANOMALY, SUPPORTED, CONTRADICTED, CONFLICTED,
        INSUFFICIENT_EVIDENCE, UNVERIFIABLE
    """
    for f in findings:
        if f.dimension.value == "runtime":
            continue
        state_value = f.state.value if hasattr(f.state, "value") else str(f.state)
        if state_value not in _ABSENCE_STATES:
            return True
    return False


def _check_evidence_review(perf: list[Finding]) -> bool:
    """evidence_review: evidence sufficient under current scope.

    Satisfied IFF:
    - At least one Performance finding exists
    - At least one SUPPORTED
    - Zero CONTRADICTED, CONFLICTED, INSUFFICIENT_EVIDENCE
    - UNVERIFIABLE is NOT blocking
    """
    if not perf:
        return False
    has_supported = any(f.state == PerformanceState.SUPPORTED for f in perf)
    has_blocking = any(f.state in (
        PerformanceState.CONTRADICTED,
        PerformanceState.CONFLICTED,
        PerformanceState.INSUFFICIENT_EVIDENCE,
    ) for f in perf)
    return has_supported and not has_blocking


def _check_verified_evidence(perf: list[Finding]) -> bool:
    """verified_evidence: all performance claims supported under current scope.

    Satisfied IFF:
    - At least one Performance finding exists
    - Every Performance finding is SUPPORTED
    """
    if not perf:
        return False
    return all(f.state == PerformanceState.SUPPORTED for f in perf)
