"""Verification Loop — orchestrates DECIDE → VERIFY → DECIDE with max depth = 1.

V1 termination rule:
  MAX VERIFICATION DEPTH = 1

Therefore:
  depth == 0 → verification permitted
  depth >= 1 → verification prohibited

Exact maximum workflow:
  DECIDE₀ → VERIFY₀ → DECIDE₁ → TERMINAL

If DECIDE₁ returns VERIFY again:
  DO NOT launch another verifier.
  Terminate according to existing failure/policy behavior.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from controlplane.decision.decide import decide
from controlplane.decision.verifier import VerifierCapability
from controlplane.schemas.context import Context
from controlplane.schemas.decision import Decision
from controlplane.schemas.enums import DecisionAction, UncertaintyType, VerificationStatus
from controlplane.schemas.finding import Finding
from controlplane.schemas.policy import Policy
from controlplane.schemas.verification import VerificationRequest, VerificationResult
from controlplane.verification.provenance import VerificationContext
from controlplane.verification.registry import VerifierRegistry
from controlplane.verification.runner import VerificationRunner
from controlplane.verification.supersession import derive_finding, supersede_active_findings

MAX_VERIFICATION_DEPTH = 1


def verify_and_redecide(
    active_findings: list[Finding],
    context: Context,
    policy: Policy,
    registry: VerifierRegistry,
    verification_context: VerificationContext,
    *,
    verifiers: list[VerifierCapability] | None = None,
    depth: int = 0,
) -> tuple[Decision, list[Finding], list[dict]]:
    """Execute the verification loop with max depth = 1.

    Args:
        active_findings: Current active findings.
        context: Situational context.
        policy: Decision policy.
        registry: Verifier registry.
        verification_context: Runtime provenance context.
        verifiers: Available verifier capabilities.
        depth: Current verification depth (0 = first call).

    Returns:
        Tuple of (final_decision, final_active_findings, audit_log)
        where audit_log is a list of dicts recording each step.
    """
    audit_log: list[dict] = []

    # Step 1: DECIDE
    decision = decide(
        findings=active_findings,
        context=context,
        policy=policy,
        verifiers=verifiers,
    )

    audit_log.append({
        "step": "decide",
        "depth": depth,
        "decision": decision.decision.value,
        "finding_ids": [str(f.finding_id) for f in active_findings],
    })

    # Step 2: If not VERIFY, we're done
    if decision.decision != DecisionAction.VERIFY:
        return decision, active_findings, audit_log

    # Step 3: Check max depth
    if depth >= MAX_VERIFICATION_DEPTH:
        # Terminate — do not launch another verifier
        from controlplane.decision.decide import _apply_failure_mode
        terminal_decision = Decision(
            decision_id=uuid4(),
            interaction_id=decision.interaction_id,
            decision_version=decision.decision_version,
            decision=_apply_failure_mode(policy),
            reason_codes=decision.reason_codes + ["max_verification_depth_reached"],
            finding_ids=decision.finding_ids,
            policy_id=decision.policy_id,
            policy_version=decision.policy_version,
            required_assurance=decision.required_assurance,
            current_assurance=decision.current_assurance,
            selected_verifier=None,
            decided_at=datetime.now(timezone.utc),
        )
        audit_log.append({
            "step": "terminate",
            "depth": depth,
            "reason": "max_verification_depth_reached",
        })
        return terminal_decision, active_findings, audit_log

    # Step 4: Execute verification
    verifier_name = decision.selected_verifier
    if verifier_name is None:
        return decision, active_findings, audit_log

    # Step 5: Find the target finding
    target_finding = _find_target_finding(active_findings, decision)
    if target_finding is None:
        return decision, active_findings, audit_log

    # Step 6: Resolve claim and evidence from context
    entry = verification_context.get(target_finding.finding_id)
    if entry is None:
        # Cannot resolve — follow failure mode
        audit_log.append({
            "step": "context_miss",
            "depth": depth,
            "finding_id": str(target_finding.finding_id),
        })
        return decision, active_findings, audit_log

    claim, evidence = entry

    # Step 7: Build VerificationRequest
    request = _build_request(
        decision=decision,
        finding=target_finding,
        context=context,
        policy=policy,
    )

    audit_log.append({
        "step": "request",
        "depth": depth,
        "request_id": str(request.request_id),
        "verifier": verifier_name,
        "finding_id": str(target_finding.finding_id),
    })

    # Step 8: Run verification
    runner = VerificationRunner(
        registry=registry,
        allowed_verifiers=policy.allowed_verifiers,
    )

    result = runner.run(
        request=request,
        verifier_name=verifier_name,
        claim=claim,
        evidence=evidence,
    )

    audit_log.append({
        "step": "result",
        "depth": depth,
        "result_id": str(result.result_id),
        "status": result.status.value,
        "resolution": result.resolution.value,
    })

    # Step 9: Handle failure
    if result.status in (VerificationStatus.FAILED, VerificationStatus.TIMEOUT):
        # No derived Finding — original remains active
        from controlplane.decision.decide import _apply_failure_mode
        terminal_decision = Decision(
            decision_id=uuid4(),
            interaction_id=decision.interaction_id,
            decision_version=decision.decision_version,
            decision=_apply_failure_mode(policy),
            reason_codes=decision.reason_codes + [f"verification_{result.status.value}"],
            finding_ids=decision.finding_ids,
            policy_id=decision.policy_id,
            policy_version=decision.policy_version,
            required_assurance=decision.required_assurance,
            current_assurance=decision.current_assurance,
            selected_verifier=None,
            decided_at=datetime.now(timezone.utc),
        )
        audit_log.append({
            "step": "failure",
            "depth": depth,
            "reason": result.failure_reason,
        })
        return terminal_decision, active_findings, audit_log

    # Step 10: Derive finding
    derived = derive_finding(target_finding, result)

    audit_log.append({
        "step": "derived_finding",
        "depth": depth,
        "derived_finding_id": str(derived.finding_id),
        "state": derived.state.value,
    })

    # Step 11: Supersede active findings
    new_active = supersede_active_findings(
        active_findings=active_findings,
        target_finding_id=target_finding.finding_id,
        derived_finding=derived,
    )

    audit_log.append({
        "step": "supersession",
        "depth": depth,
        "removed_finding_id": str(target_finding.finding_id),
        "added_finding_id": str(derived.finding_id),
        "new_active_count": len(new_active),
    })

    # Step 12: Re-DECIDE with depth + 1
    second_decision, final_active, second_log = verify_and_redecide(
        active_findings=new_active,
        context=context,
        policy=policy,
        registry=registry,
        verification_context=verification_context,
        verifiers=verifiers,
        depth=depth + 1,
    )

    audit_log.extend(second_log)
    return second_decision, final_active, audit_log


def _find_target_finding(
    findings: list[Finding], decision: Decision
) -> Finding | None:
    """Find the target finding for verification from the decision's finding_ids."""
    from controlplane.schemas.enums import PerformanceState
    for fid in decision.finding_ids:
        for f in findings:
            if f.finding_id == fid and f.dimension.value == "performance":
                if f.state in (
                    PerformanceState.INSUFFICIENT_EVIDENCE,
                    PerformanceState.CONTRADICTED,
                    PerformanceState.CONFLICTED,
                    PerformanceState.UNVERIFIABLE,
                ):
                    return f
    return None


def _build_request(
    decision: Decision,
    finding: Finding,
    context: Context,
    policy: Policy,
) -> VerificationRequest:
    """Build a VerificationRequest from decision and finding."""
    from controlplane.decision.decide import _identify_unresolved
    from controlplane.schemas.enums import UncertaintyType

    gaps = _identify_unresolved([finding])
    if gaps:
        uncertainty_type = gaps[0][1]
    else:
        uncertainty_type = UncertaintyType.FACTUAL_SUPPORT

    specific_question = _generate_question(finding, uncertainty_type)

    return VerificationRequest(
        request_id=uuid4(),
        interaction_id=decision.interaction_id,
        decision_id=decision.decision_id,
        finding_id=finding.finding_id,
        uncertainty_type=uncertainty_type,
        specific_question=specific_question,
        evidence_scope=finding.evidence.source_ids,
        timeout_ms=min(
            policy.verification_budget_ms,
            max(0, context.latency_budget_ms - sum(f.latency_ms for f in [finding])),
        ),
        max_cost_usd=policy.verification_budget_usd,
        requested_at=datetime.now(timezone.utc),
    )


def _generate_question(finding: Finding, uncertainty_type: UncertaintyType) -> str:
    """Generate a specific question for the verification request."""
    claim_text = finding.evidence.claim_text or "unknown claim"
    if uncertainty_type == UncertaintyType.FACTUAL_SUPPORT:
        return f"Does the available evidence support this claim: {claim_text}"
    elif uncertainty_type == UncertaintyType.SOURCE_CONFLICT:
        return f"Can conflicting sources be resolved for: {claim_text}"
    else:
        return f"Verify: {claim_text}"
