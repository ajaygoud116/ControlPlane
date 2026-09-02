"""Hard-constraint evaluation — absolute rules that bypass assurance comparison.

Hard constraints operate on finding-state condition identifiers, NOT raw text patterns.
The detector detects. The policy determines consequence.
"""

from __future__ import annotations

from controlplane.schemas.enums import (
    CostState,
    DecisionAction,
    PerformanceState,
    PIIState,
    PolicyState,
    ResponsibilityState,
    RuntimeState,
)
from controlplane.schemas.finding import Finding
from controlplane.schemas.policy import Policy


# Maps condition strings to (dimension, state) checks.
# These represent finding-state conditions, NOT regex patterns.
_CONDITION_MATCHERS: dict[str, tuple[str, object]] = {
    "policy_violation": ("policy", PolicyState.POLICY_VIOLATION),
    "pii_detected": ("pii", PIIState.PII_DETECTED),
    "insufficient_evidence": ("performance", PerformanceState.INSUFFICIENT_EVIDENCE),
    "conflicted": ("performance", PerformanceState.CONFLICTED),
    "contradicted": ("performance", PerformanceState.CONTRADICTED),
    "unverifiable": ("performance", PerformanceState.UNVERIFIABLE),
    "runtime_anomaly": ("runtime", RuntimeState.RUNTIME_ANOMALY),
    "unsafe_content_detected": ("responsibility", ResponsibilityState.UNSAFE_CONTENT_DETECTED),
    "secret_detected": ("responsibility", ResponsibilityState.SECRET_DETECTED),
    "cost_threshold_exceeded": ("cost", CostState.COST_THRESHOLD_EXCEEDED),
    "token_budget_exceeded": ("cost", CostState.TOKEN_BUDGET_EXCEEDED),
    "latency_threshold_exceeded": ("cost", CostState.LATENCY_THRESHOLD_EXCEEDED),
}


def _finding_matches(finding: Finding, condition: str) -> bool:
    """Check if a finding matches a condition identifier."""
    spec = _CONDITION_MATCHERS.get(condition)
    if spec is None:
        return False
    dimension, state = spec
    return finding.dimension.value == dimension and finding.state == state


def evaluate_hard_constraints(
    findings: list[Finding], policy: Policy
) -> tuple[DecisionAction | None, list[str]]:
    """Evaluate hard constraints in precedence order.

    Returns (decision, reason_codes) if a constraint fires.
    Returns (None, []) if no constraint fires.

    Precedence: blocked_patterns > required_verifications > escalation_triggers

    Special case: When MODIFY is in allowed_interventions and PII is detected,
    the required_verifications constraint for pii_detected is skipped.
    PII is handled by redaction (MODIFY), not verification.
    """
    from controlplane.schemas.enums import InterventionAction, PIIState

    pii_modifiable = (
        InterventionAction.MODIFY in policy.allowed_interventions
        and any(f.dimension.value == "pii" and f.state == PIIState.PII_DETECTED for f in findings)
    )

    for condition in policy.hard_constraints.blocked_patterns:
        if any(_finding_matches(f, condition) for f in findings):
            return DecisionAction.BLOCK, ["hard_constraint_violation", condition]

    for condition in policy.hard_constraints.required_verifications:
        # Skip pii_detected verification when MODIFY handles PII via redaction
        if condition == "pii_detected" and pii_modifiable:
            continue
        if any(_finding_matches(f, condition) for f in findings):
            return DecisionAction.VERIFY, ["hard_constraint_required", condition]

    for condition in policy.hard_constraints.escalation_triggers:
        if any(_finding_matches(f, condition) for f in findings):
            return DecisionAction.ESCALATE, ["hard_constraint_trigger", condition]

    return None, []
