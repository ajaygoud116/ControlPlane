"""Deterministic decision engine.

Consumes findings, context, and policy. Produces a Decision.
No LLM. No numeric scores. No risk averaging. Pure condition matching.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from controlplane.decision.assurance import derive_current_assurance, evaluate_assurance
from controlplane.decision.hard_constraints import evaluate_hard_constraints
from controlplane.decision.risk_registry import RiskRegistry
from controlplane.decision.verifier import VerifierCapability
from controlplane.schemas.context import Context
from controlplane.schemas.decision import Decision
from controlplane.schemas.enums import (
    DecisionAction,
    PerformanceState,
    RuntimeState,
    UncertaintyType,
)
from controlplane.schemas.finding import Finding
from controlplane.schemas.policy import Policy

# Default registry instance for fail-closed checks.
# Created once at module load time. Stateless after initialization.
_DEFAULT_REGISTRY = RiskRegistry()


def decide(
    findings: list[Finding],
    context: Context,
    policy: Policy,
    *,
    verifiers: list[VerifierCapability] | None = None,
) -> Decision:
    """Deterministic decision based on findings, context, and policy.

    Algorithm:
    1. Evaluate hard constraints (absolute overrides)
    2. If no hard constraint: derive required assurance, evaluate predicates
    3. If assurance not satisfied: attempt verifier selection within budget
    4. Construct Decision with all fields populated

    Args:
        findings: Findings from detectors for this interaction.
        context: Situational information for this interaction.
        policy: Configurable rules for this decision.
        verifiers: Available verifier capabilities. None = no verification possible.

    Returns:
        Decision with action, reason codes, and selected verifier (if any).
    """
    now = datetime.now(timezone.utc)
    verifiers = verifiers or []

    # --- 1. Hard constraints (absolute override) ---
    hc_decision, hc_reasons = evaluate_hard_constraints(findings, policy)
    required_assurance = _derive_required_assurance(context, policy)

    if hc_decision is not None:
        if hc_decision in (DecisionAction.BLOCK, DecisionAction.ESCALATE):
            return _build_decision(
                findings=findings,
                policy=policy,
                decision=hc_decision,
                reason_codes=hc_reasons,
                selected_verifier=None,
                required_assurance=required_assurance,
                now=now,
            )

        if hc_decision == DecisionAction.VERIFY:
            remaining_ms, remaining_usd = _calculate_budget(findings, context, policy)
            hc_gaps = _identify_unresolved(findings)
            verifier = _select_verifier(
                hc_gaps, verifiers, remaining_ms, remaining_usd,
                allowed_verifiers=policy.allowed_verifiers,
            )
            if verifier is not None:
                return _build_decision(
                    findings=findings,
                    policy=policy,
                    decision=DecisionAction.VERIFY,
                    reason_codes=hc_reasons,
                    selected_verifier=verifier.name,
                    required_assurance=required_assurance,
                    now=now,
                )
            return _build_decision(
                findings=findings,
                policy=policy,
                decision=_apply_failure_mode(policy),
                reason_codes=hc_reasons + ["verification_not_feasible"],
                selected_verifier=None,
                required_assurance=required_assurance,
                now=now,
            )

    # --- 2. Derive required assurance ---
    required_assurance = _derive_required_assurance(context, policy)

    # --- 2b. Fail-closed: check for unrecognized finding states ---
    # Any finding whose (dimension, state) is not in the RiskRegistry
    # must trigger ESCALATE. This prevents unknown risks from silently
    # passing through to ALLOW.
    if findings:
        unrecognized = [
            f for f in findings
            if not _DEFAULT_REGISTRY.recognizes(f.dimension.value, f.state.value)
        ]
        if unrecognized:
            return _build_decision(
                findings=findings,
                policy=policy,
                decision=DecisionAction.ESCALATE,
                reason_codes=["unknown_finding_state"] + [
                    f"{f.dimension.value}:{f.state.value}" for f in unrecognized
                ],
                selected_verifier=None,
                required_assurance=required_assurance,
                now=now,
            )

    # --- 2c. Clean check: all findings are absence/clean states ---
    # When findings exist but ALL are absence states (NO_PII_DETECTED,
    # POLICY_UNRESOLVED, RESPONSIBILITY_CLEAN, etc.), the system has
    # checked and found nothing.
    #
    # For basic_detection (LOW consequence): absence is sufficient → ALLOW.
    # For evidence_review/verified_evidence (MEDIUM/HIGH): absence is NOT
    # sufficient — these require actual evidence. The existing predicates
    # (_check_evidence_review, _check_verified_evidence) handle this correctly.
    from controlplane.decision.assurance import _ABSENCE_STATES
    if findings and required_assurance == "basic_detection":
        all_absence = all(
            (f.state.value if hasattr(f.state, "value") else str(f.state))
            in _ABSENCE_STATES
            for f in findings
        )
        if all_absence:
            return _build_decision(
                findings=findings,
                policy=policy,
                decision=DecisionAction.ALLOW,
                reason_codes=["all_findings_clean"],
                selected_verifier=None,
                required_assurance=required_assurance,
                now=now,
            )

    # --- 3. Evaluate assurance ---
    if evaluate_assurance(findings, required_assurance):
        return _build_decision(
            findings=findings,
            policy=policy,
            decision=DecisionAction.ALLOW,
            reason_codes=[f"{required_assurance}_satisfied"],
            selected_verifier=None,
            required_assurance=required_assurance,
            now=now,
        )

    # --- 4. Assurance not satisfied — attempt verification ---
    remaining_ms, remaining_usd = _calculate_budget(findings, context, policy)
    gaps = _identify_unresolved(findings)
    verifier = _select_verifier(
        gaps, verifiers, remaining_ms, remaining_usd,
        allowed_verifiers=policy.allowed_verifiers,
    )

    if verifier is not None:
        return _build_decision(
            findings=findings,
            policy=policy,
            decision=DecisionAction.VERIFY,
            reason_codes=[f"{required_assurance}_not_met"] + [g[1].value for g in gaps],
            selected_verifier=verifier.name,
            required_assurance=required_assurance,
            now=now,
        )

    # --- 5. No verifier available or budget exhausted ---
    return _build_decision(
        findings=findings,
        policy=policy,
        decision=_apply_failure_mode(policy),
        reason_codes=[f"{required_assurance}_not_met", "verification_not_feasible"]
        + [g[1].value for g in gaps],
        selected_verifier=None,
        required_assurance=required_assurance,
        now=now,
    )


def _derive_required_assurance(context: Context, policy: Policy) -> str:
    """Map context consequence to required assurance level via policy."""
    mapping = {
        "low": policy.assurance_requirements.low_consequence,
        "medium": policy.assurance_requirements.medium_consequence,
        "high": policy.assurance_requirements.high_consequence,
    }
    return mapping.get(context.consequence.value, "basic_detection")


def _calculate_budget(
    findings: list[Finding], context: Context, policy: Policy
) -> tuple[float, float]:
    """Calculate remaining verification budget after detection costs."""
    detector_latency = sum(f.latency_ms for f in findings)
    remaining_latency = context.latency_budget_ms - detector_latency
    remaining_ms = min(policy.verification_budget_ms, max(0.0, remaining_latency))
    remaining_usd = policy.verification_budget_usd

    has_runtime_anomaly = any(
        f.dimension.value == "runtime" and f.state == RuntimeState.RUNTIME_ANOMALY
        for f in findings
    )
    if has_runtime_anomaly:
        remaining_ms *= 0.5
        remaining_usd *= 0.5

    return remaining_ms, remaining_usd


def _identify_unresolved(
    findings: list[Finding],
) -> list[tuple[Finding, UncertaintyType]]:
    """Identify findings that need verification and their uncertainty types."""
    gaps: list[tuple[Finding, UncertaintyType]] = []
    for f in findings:
        if f.dimension.value != "performance":
            continue
        if f.state == PerformanceState.INSUFFICIENT_EVIDENCE:
            gaps.append((f, UncertaintyType.FACTUAL_SUPPORT))
        elif f.state == PerformanceState.CONTRADICTED:
            gaps.append((f, UncertaintyType.FACTUAL_SUPPORT))
        elif f.state == PerformanceState.CONFLICTED:
            gaps.append((f, UncertaintyType.SOURCE_CONFLICT))
        elif f.state == PerformanceState.UNVERIFIABLE:
            gaps.append((f, UncertaintyType.FACTUAL_SUPPORT))
    return gaps


def _select_verifier(
    gaps: list[tuple[Finding, UncertaintyType]],
    verifiers: list[VerifierCapability],
    remaining_ms: float,
    remaining_usd: float,
    *,
    allowed_verifiers: list[str] | None = None,
) -> VerifierCapability | None:
    """Select the first capable, authorized verifier that fits within budget.

    Selection pipeline:
    1. unresolved condition -> uncertainty type
    2. filter to policy.allowed_verifiers (if non-empty)
    3. capability match (uncertainty type in verifier.uncertainty_types)
    4. latency feasibility
    5. cost feasibility
    """
    if not gaps or not verifiers:
        return None

    if allowed_verifiers is not None and len(allowed_verifiers) > 0:
        authorized = [vc for vc in verifiers if vc.name in allowed_verifiers]
    else:
        authorized = list(verifiers)

    for _gap_finding, uncertainty_type in gaps:
        for vc in authorized:
            if uncertainty_type in vc.uncertainty_types:
                if vc.expected_latency_ms <= remaining_ms and vc.expected_cost_usd <= remaining_usd:
                    return vc
    return None


def _apply_failure_mode(policy: Policy) -> DecisionAction:
    """Map policy failure mode to a decision action."""
    return DecisionAction(policy.failure_mode.value)


def _build_decision(
    *,
    findings: list[Finding],
    policy: Policy,
    decision: DecisionAction,
    reason_codes: list[str],
    selected_verifier: str | None,
    required_assurance: str,
    now: datetime,
) -> Decision:
    """Construct a Decision object with all fields populated."""
    interaction_id = findings[0].interaction_id if findings else uuid4()
    current_assurance = derive_current_assurance(findings)

    return Decision(
        decision_id=uuid4(),
        interaction_id=interaction_id,
        decision_version="1.0.0",
        decision=decision,
        reason_codes=reason_codes,
        finding_ids=[f.finding_id for f in findings],
        policy_id=policy.policy_id,
        policy_version=policy.version,
        required_assurance=required_assurance,
        current_assurance=current_assurance,
        selected_verifier=selected_verifier,
        decided_at=now,
    )
