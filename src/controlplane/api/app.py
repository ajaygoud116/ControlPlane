"""ControlPlane API — comprehensive backend for UI integration.

Extends the existing /check endpoint with:
- GET /interactions — list all interactions
- GET /interactions/{id} — full interaction detail
- GET /findings — all findings across interactions
- GET /policies — available policies
- POST /policies/evaluate — evaluate finding against policy
- GET /models — available model adapters
- GET /detectors — available detectors
- GET /metrics — aggregated metrics
- GET /audit — audit trail
- POST /demo/run — execute a demo scenario
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from controlplane.api.schemas import CheckRequest, CheckResponse
from controlplane.runtime.runtime import ControlPlaneRuntime
from controlplane.runtime.result import ControlPlaneResult
from controlplane.persistence.audit_store import AuditStore
from controlplane.monitoring.monitor import MonitoringService
from controlplane.demo.simulated_model import SimulatedModel
from controlplane.demo.scenarios import ALL_SCENARIOS, Scenario

logger = logging.getLogger(__name__)


# ── Policy Registry ──────────────────────────────────────────────
# Import from the shared single source of truth.
# All endpoints (/demo/run, /check/text, /live/run, traffic interceptor)
# resolve policies through this module.
from controlplane.policy_registry import POLICY_REGISTRY as _POLICY_REGISTRY
from controlplane.schemas.policy import Policy


def _resolve_policy(name: str) -> Policy:
    """Resolve a policy name to a Policy object.

    Raises HTTPException if the policy name is not recognized.
    """
    policy = _POLICY_REGISTRY.get(name)
    if policy is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown policy: {name!r}. Available: {sorted(_POLICY_REGISTRY.keys())}",
        )
    return policy


def _resolve_context(
    scenario_context,
    consequence: str | None = None,
):
    """Apply user-selected consequence override to the scenario's context.

    If consequence is provided, creates a new Context with the overridden value.
    Otherwise returns the scenario's original context unchanged.
    """
    if consequence is None:
        return scenario_context

    from controlplane.schemas.context import Context
    from controlplane.schemas.enums import Consequence

    return Context(
        context_id=scenario_context.context_id,
        use_case=scenario_context.use_case,
        consequence=Consequence(consequence.lower()),
        reversibility=scenario_context.reversibility,
        downstream_action=scenario_context.downstream_action,
        data_sensitivity=scenario_context.data_sensitivity,
        latency_budget_ms=scenario_context.latency_budget_ms,
        jurisdiction=scenario_context.jurisdiction,
    )


def _serialize_finding(f: Any) -> dict:
    """Serialize a Finding to a dict for API response."""
    return {
        "finding_id": str(f.finding_id),
        "interaction_id": str(f.interaction_id),
        "detector_id": f.detector_id,
        "detector_version": f.detector_version,
        "dimension": f.dimension.value,
        "finding_type": f.finding_type,
        "state": f.state.value if hasattr(f.state, "value") else str(f.state),
        "observation_ids": [str(oid) for oid in f.observation_ids] if f.observation_ids else [],
        "explanation": f.explanation,
        "latency_ms": f.latency_ms,
        "cost_usd": f.cost_usd,
        "detected_at": f.detected_at.isoformat() if f.detected_at else None,
        "evidence": {
            "claim_text": f.evidence.claim_text,
            "source_ids": f.evidence.source_ids,
            "source_quality": f.evidence.source_quality,
            "counter_evidence": f.evidence.counter_evidence,
            "quality_assessment": f.evidence.quality_assessment,
        },
        "measurement": {
            "input_tokens": f.measurement.input_tokens,
            "output_tokens": f.measurement.output_tokens,
            "model_calls": f.measurement.model_calls,
            "tool_calls": f.measurement.tool_calls,
            "latency_ms": f.measurement.latency_ms,
            "estimated_cost_usd": f.measurement.estimated_cost_usd,
        },
        "ambiguity": {
            "reasons": f.ambiguity.reasons,
            "conflicting_sources": f.ambiguity.conflicting_sources,
            "evidence_gaps": f.ambiguity.evidence_gaps,
        },
    }


def _serialize_decision(d: Any) -> dict:
    """Serialize a Decision to a dict."""
    return {
        "decision_id": str(d.decision_id),
        "interaction_id": str(d.interaction_id),
        "decision_version": d.decision_version,
        "decision": d.decision.value,
        "reason_codes": d.reason_codes,
        "finding_ids": [str(fid) for fid in d.finding_ids],
        "policy_id": str(d.policy_id),
        "policy_version": d.policy_version,
        "required_assurance": d.required_assurance,
        "current_assurance": d.current_assurance,
        "selected_verifier": d.selected_verifier,
        "decided_at": d.decided_at.isoformat() if d.decided_at else None,
    }


def _serialize_interaction_summary(record: Any) -> dict:
    """Serialize an AuditRecord to an interaction summary."""
    interaction = record.interaction
    terminal_decision = None
    for d in reversed(record.decisions):
        terminal_decision = d
        break

    return {
        "interaction_id": str(interaction.interaction_id),
        "request_text": interaction.request_text[:200],
        "response_text": interaction.response_text[:200],
        "model": interaction.model,
        "provider": interaction.provider,
        "decision": terminal_decision.decision.value if terminal_decision else "unknown",
        "findings_count": len(record.findings),
        "dimensions": list({f.dimension.value for f in record.findings}),
        "intervention_action": record.intervention.action.value if record.intervention else None,
        "created_at": interaction.created_at.isoformat() if interaction.created_at else None,
        "policy_id": str(record.policy_id),
        "policy_version": record.policy_version,
    }


def _serialize_interaction_detail(record: Any) -> dict:
    """Serialize an AuditRecord to full interaction detail."""
    interaction = record.interaction
    terminal_decision = None
    for d in reversed(record.decisions):
        terminal_decision = d
        break

    return {
        "interaction_id": str(interaction.interaction_id),
        "request_text": interaction.request_text,
        "response_text": interaction.response_text,
        "model": interaction.model,
        "provider": interaction.provider,
        "created_at": interaction.created_at.isoformat() if interaction.created_at else None,
        "blocked": terminal_decision.decision.value == "block" if terminal_decision else False,
        "escalated": terminal_decision.decision.value == "escalate" if terminal_decision else False,
        "observations": [
            {
                "observation_id": str(o.observation_id),
                "observation_type": o.observation_type.value,
                "source": o.source,
                "timestamp": o.timestamp.isoformat() if o.timestamp else None,
                "duration_ms": o.duration_ms,
                "payload": o.payload,
            }
            for o in record.observations
        ],
        "findings": [_serialize_finding(f) for f in record.findings],
        "decisions": [_serialize_decision(d) for d in record.decisions],
        "final_decision": _serialize_decision(terminal_decision) if terminal_decision else None,
        "intervention": {
            "intervention_id": str(record.intervention.intervention_id),
            "action": record.intervention.action.value,
            "modification_type": record.intervention.modification_type.value if record.intervention.modification_type else None,
            "modification_detail": record.intervention.modification_detail,
            "blocked_reason": record.intervention.blocked_reason,
            "escalation_reason": record.intervention.escalation_reason,
            "applied_at": record.intervention.applied_at.isoformat() if record.intervention.applied_at else None,
        } if record.intervention else None,
        "outcome": {
            "outcome_id": str(record.outcome.outcome_id),
            "outcome_type": record.outcome.outcome_type.value if hasattr(record.outcome.outcome_type, 'value') else str(record.outcome.outcome_type),
            "description": record.outcome.description,
            "observed_at": record.outcome.observed_at.isoformat() if record.outcome.observed_at else None,
        } if record.outcome else None,
        "verification_events": record.verification_events,
        "policy_id": str(record.policy_id),
        "policy_version": record.policy_version,
        "frozen_v1_version": record.frozen_v1_version,
        "audit_id": str(record.audit_id),
    }


def _serialize_audit_record(record: Any) -> dict:
    """Serialize an AuditRecord for audit trail."""
    return {
        "audit_id": str(record.audit_id),
        "interaction_id": str(record.interaction.interaction_id),
        "created_at": record.created_at.isoformat() if record.created_at else None,
        "model": record.interaction.model,
        "provider": record.interaction.provider,
        "findings_count": len(record.findings),
        "dimensions": list({f.dimension.value for f in record.findings}),
        "decisions": [
            {"decision": d.decision.value, "reason_codes": d.reason_codes}
            for d in record.decisions
        ],
        "intervention_action": record.intervention.action.value if record.intervention else None,
        "intervention_reason": (
            record.intervention.blocked_reason or record.intervention.escalation_reason
            if record.intervention else None
        ),
        "released_response": record.released_response,
        "policy_id": str(record.policy_id),
        "policy_version": record.policy_version,
    }


def create_full_app(
    runtime: ControlPlaneRuntime,
    audit_store: AuditStore | None = None,
    traffic_interceptor=None,
) -> FastAPI:
    """Create the full ControlPlane API application.

    Args:
        runtime: Configured ControlPlaneRuntime instance.
        audit_store: Optional AuditStore for persistence.
        traffic_interceptor: Optional TrafficInterceptor for real-time observation.

    Returns:
        FastAPI application with all endpoints.
    """
    app = FastAPI(
        title="ControlPlane API",
        description="AI Runtime Governance Control Plane",
        version="0.2.0",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    monitoring = MonitoringService(audit_store) if audit_store else None
    interceptor = traffic_interceptor

    # ------------------------------------------------------------------
    # Core endpoints (from check.py)
    # ------------------------------------------------------------------

    @app.post("/check", response_model=CheckResponse)
    async def check(request: CheckRequest) -> CheckResponse:
        """Process an AI interaction through ControlPlane."""
        try:
            from controlplane.schemas.context import Context
            from controlplane.schemas.policy import Policy

            context = Context(**request.context)
            policy = Policy(**request.policy)

            claims = None
            if request.claims is not None:
                from controlplane.detection.performance_types import Claim
                claims = [Claim(**c) for c in request.claims]

            evidence = None
            if request.evidence is not None:
                from controlplane.detection.performance_types import Evidence
                evidence = [Evidence(**e) for e in request.evidence]

            result: ControlPlaneResult = runtime.check(
                request_text=request.request_text,
                response_text=request.response_text,
                context=context,
                policy=policy,
                model=request.model,
                provider=request.provider,
                metadata=request.metadata,
                claims=claims,
                evidence=evidence,
                auto_extract_claims=claims is None,
            )

            findings_data = [_serialize_finding(f) for f in result.interaction.findings]
            decision_history = [_serialize_decision(d) for d in result.interaction.decisions]

            # Use the terminal decision (last in history), not the initial decision.
            terminal_decision = result.interaction.decisions[-1].decision.value if result.interaction.decisions else result.decision.decision.value

            intervention_data = None
            if result.interaction.intervention:
                intervention_data = {
                    "intervention_id": str(result.interaction.intervention.intervention_id),
                    "action": result.interaction.intervention.action.value,
                    "modification_type": result.interaction.intervention.modification_type.value if result.interaction.intervention.modification_type else None,
                }

            outcome_data = None
            if result.interaction.outcome:
                outcome_data = {
                    "outcome_id": str(result.interaction.outcome.outcome_id),
                    "outcome_type": result.interaction.outcome.outcome_type,
                    "description": result.interaction.outcome.description,
                }

            return CheckResponse(
                interaction_id=str(result.interaction.interaction_id),
                decision=terminal_decision,
                released_response=result.released_response,
                blocked=result.blocked,
                escalated=result.escalated,
                findings=findings_data,
                decision_history=decision_history,
                intervention=intervention_data,
                outcome=outcome_data,
                audit_persisted=result.audit_persisted,
                audit_persist_error=result.audit_persist_error,
                errors=[],
            )

        except Exception as exc:
            logger.exception("Error processing /check request")
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    @app.get("/interactions")
    async def list_interactions(
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        use_case: str | None = None,
        dimension: str | None = None,
        decision: str | None = None,
        model: str | None = None,
    ) -> list[dict]:
        """List all interactions from audit store."""
        if monitoring is None:
            return []
        return monitoring.list_interactions(
            limit=limit, offset=offset, use_case=use_case,
            dimension=dimension, decision=decision, model=model,
        )

    @app.get("/interactions/{interaction_id}")
    async def get_interaction(interaction_id: str) -> dict:
        """Get full interaction detail."""
        if monitoring is None:
            raise HTTPException(status_code=503, detail="Audit store not configured")
        try:
            uid = uuid.UUID(interaction_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid interaction ID")
        result = monitoring.get_interaction(uid)
        if result is None:
            raise HTTPException(status_code=404, detail="Interaction not found")
        return result

    # ------------------------------------------------------------------
    # Findings
    # ------------------------------------------------------------------

    @app.get("/findings")
    async def list_findings(
        limit: int = Query(100, ge=1, le=500),
        offset: int = Query(0, ge=0),
        dimension: str | None = None,
        state: str | None = None,
        detector_id: str | None = None,
    ) -> list[dict]:
        """List all findings across all interactions."""
        if monitoring is None:
            return []
        records = monitoring._load_all_records()
        all_findings = []
        for record in records:
            for f in record.findings:
                finding_dict = _serialize_finding(f)
                finding_dict["interaction_id"] = str(record.interaction.interaction_id)
                all_findings.append(finding_dict)

        if dimension:
            all_findings = [f for f in all_findings if f["dimension"] == dimension]
        if state:
            all_findings = [f for f in all_findings if f["state"] == state]
        if detector_id:
            all_findings = [f for f in all_findings if f["detector_id"] == detector_id]

        return all_findings[offset:offset + limit]

    # ------------------------------------------------------------------
    # Policies
    # ------------------------------------------------------------------

    @app.get("/policies")
    async def list_policies() -> list[dict]:
        """List available policy configurations.

        These are the ACTUAL policies that runtime.check() will use
        when a user selects them. The policy registry is the single
        source of truth.
        """
        result = []
        for name, policy in _POLICY_REGISTRY.items():
            result.append({
                "policy_id": str(policy.policy_id),
                "name": name,
                "version": policy.version,
                "scope": policy.scope.value,
                "description": {
                    "Balanced": "Standard policy balancing safety and throughput",
                    "Strict": "Conservative policy for high-risk deployments",
                    "Lenient": "Permissive policy for low-risk applications",
                }.get(name, "Policy configuration"),
                "assurance_requirements": {
                    "low_consequence": policy.assurance_requirements.low_consequence,
                    "medium_consequence": policy.assurance_requirements.medium_consequence,
                    "high_consequence": policy.assurance_requirements.high_consequence,
                },
                "hard_constraints": {
                    "blocked_patterns": policy.hard_constraints.blocked_patterns,
                    "required_verifications": policy.hard_constraints.required_verifications,
                    "escalation_triggers": policy.hard_constraints.escalation_triggers,
                },
                "allowed_verifiers": policy.allowed_verifiers,
                "failure_mode": policy.failure_mode.value,
            })
        return result

    @app.post("/policies/evaluate")
    async def evaluate_policy(payload: dict) -> dict:
        """Evaluate a finding against a policy configuration."""
        try:
            from controlplane.schemas.context import Context
            from controlplane.schemas.policy import Policy
            from controlplane.schemas.finding import Finding
            from controlplane.decision.decide import decide

            finding_data = payload.get("finding", {})
            policy_data = payload.get("policy", {})

            finding = Finding(**finding_data)

            policy_fields = {k: v for k, v in policy_data.items() if k in Policy.model_fields}
            policy = Policy(**policy_fields)

            context = Context(
                context_id=uuid.uuid4(),
                use_case="evaluation",
                consequence="medium",
                reversibility="reversible",
                downstream_action="none",
                data_sensitivity="internal",
                latency_budget_ms=5000.0,
            )

            decision = decide(
                findings=[finding],
                context=context,
                policy=policy,
                verifiers=None,
            )

            return {
                "decision": decision.decision.value,
                "reason_codes": decision.reason_codes,
                "required_assurance": decision.required_assurance,
                "current_assurance": decision.current_assurance,
            }
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    # ------------------------------------------------------------------
    # Models
    # ------------------------------------------------------------------

    @app.get("/models")
    async def list_models() -> list[dict]:
        """List available model adapters."""
        from controlplane.gateway.openai_adapter import OPENAI_AVAILABLE
        from controlplane.gateway.anthropic_adapter import ANTHROPIC_AVAILABLE

        models = [
            {
                "name": "SimulatedModel",
                "provider": "controlplane",
                "status": "online",
                "type": "simulated",
                "description": "Deterministic model for testing and demonstration",
            },
            {
                "name": "OpenAI Adapter",
                "provider": "openai",
                "status": "configured" if OPENAI_AVAILABLE else "not_installed",
                "type": "real",
                "description": "OpenAI Chat Completions API" + (" (package installed)" if OPENAI_AVAILABLE else " (install openai package)"),
            },
            {
                "name": "Anthropic Adapter",
                "provider": "anthropic",
                "status": "configured" if ANTHROPIC_AVAILABLE else "not_installed",
                "type": "real",
                "description": "Anthropic Messages API" + (" (package installed)" if ANTHROPIC_AVAILABLE else " (install anthropic package)"),
            },
        ]
        return models

    # ------------------------------------------------------------------
    # Detectors
    # ------------------------------------------------------------------

    @app.get("/detectors")
    async def list_detectors() -> list[dict]:
        """List detectors that are actually wired into the runtime.

        Detectors are only listed if the runtime has an active instance.
        Detectors that exist as files but are NOT wired into the runtime
        are excluded — this endpoint must not claim capabilities the
        runtime does not actually have.
        """
        active_detectors = []

        # T0 detectors (always present — instantiated by default)
        t0_detectors = [
            ("pii_entity", "PII Detection", "responsibility", "regex", "1.0.0",
             "Detects email, phone, SSN, and credit card patterns", 4),
            ("secret_detection", "Secret Detection", "responsibility", "regex", "1.0.0",
             "Detects API keys, AWS keys, GitHub tokens, PEM keys", 5),
            ("unsafe_content", "Unsafe Content", "responsibility", "regex", "1.0.0",
             "Detects violence, self-harm, illegal activity, hate speech", 4),
            ("basic_policy", "Policy Rules", "policy", "regex", "1.0.0",
             "Configurable pattern-based policy rule matching", 0),
            ("runtime_telemetry", "Runtime Telemetry", "runtime", "threshold", "1.0.0",
             "Runtime anomaly detection against configured thresholds", 0),
        ]
        for det_id, name, dim, method, ver, desc, patterns in t0_detectors:
            active_detectors.append({
                "detector_id": det_id,
                "name": name,
                "dimension": dim,
                "method": method,
                "version": ver,
                "status": "active",
                "description": desc,
                "patterns": patterns,
            })

        # Cost detector (if configured)
        if runtime._cost_detector is not None:
            active_detectors.append({
                "detector_id": "cost_budget",
                "name": "Cost Detection",
                "dimension": "cost",
                "method": "threshold",
                "version": "1.0.0",
                "status": "active",
                "description": "Token consumption and monetary cost vs budget thresholds",
                "patterns": 0,
            })

        # Secrets detector (if configured)
        if runtime._secrets_detector is not None:
            active_detectors.append({
                "detector_id": "secret_detection",
                "name": "Secret Detection",
                "dimension": "responsibility",
                "method": "regex",
                "version": "1.0.0",
                "status": "active",
                "description": "Detects API keys, AWS keys, GitHub tokens, PEM keys",
                "patterns": 5,
            })

        # Unsafe content detector (if configured)
        if runtime._unsafe_content_detector is not None:
            active_detectors.append({
                "detector_id": "unsafe_content",
                "name": "Unsafe Content",
                "dimension": "responsibility",
                "method": "regex",
                "version": "1.0.0",
                "status": "active",
                "description": "Detects violence, self-harm, illegal activity, hate speech",
                "patterns": 4,
            })

        # Performance detector (T1 — claim extraction + evidence comparison)
        active_detectors.append({
            "detector_id": "performance_evidence",
            "name": "Performance/Evidence",
            "dimension": "performance",
            "method": "deterministic",
            "version": "1.0.0",
            "status": "active",
            "description": "Evidence-grounded claim verification",
            "patterns": 0,
        })

        return active_detectors

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    @app.get("/metrics")
    async def get_metrics() -> dict:
        """Get aggregated metrics."""
        if monitoring is None:
            return {
                "total_interactions": 0,
                "findings_by_dimension": {},
                "decisions": {},
                "latency": {},
            }
        return monitoring.get_summary()

    # ------------------------------------------------------------------
    # Session Reset
    # ------------------------------------------------------------------

    @app.post("/session/reset")
    async def reset_session() -> dict:
        """Reset the current session to a clean state.

        Clears all audit records, findings, metrics, and traffic events.
        Scenarios and policies remain intact (static configuration).
        """
        if audit_store is not None:
            audit_store.reset()
        if interceptor is not None:
            interceptor.clear_events()
        logger.info("Session reset: all execution state cleared")
        return {"status": "ok", "message": "Session reset to clean state"}

    # ------------------------------------------------------------------
    # Audit
    # ------------------------------------------------------------------

    @app.get("/audit")
    async def list_audit(
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
    ) -> list[dict]:
        """List audit trail records."""
        if monitoring is None:
            return []
        records = monitoring._load_all_records()
        return [_serialize_audit_record(r) for r in records[offset:offset + limit]]

    # ------------------------------------------------------------------
    # Demo scenarios
    # ------------------------------------------------------------------

    @app.get("/demo/scenarios")
    async def list_demo_scenarios() -> list[dict]:
        """List available demo scenarios."""
        return [
            {
                "name": s.name,
                "label": s.label,
                "tag": s.tag,
                "description": s.description,
                "dimensions": s.dimensions,
                "expected_decision": s.expected_decision,
            }
            for s in ALL_SCENARIOS
        ]

    # Scenario name aliases — map alternate names to canonical scenario names
    _SCENARIO_ALIASES: dict[str, str] = {
        "unsafe_content": "unsafe",
    }

    @app.post("/demo/run")
    async def run_demo_scenario(payload: dict) -> dict:
        """Run a demo scenario and return the result.

        The scenario determines WHAT the simulated model says.
        The selected policy determines WHAT governance permits.
        The selected consequence determines HOW severe the situation is treated.

        The scenario MUST NOT secretly determine the governance outcome.
        """
        scenario_name = payload.get("scenario", "clean")
        policy_name = payload.get("policy", "Balanced")
        consequence = payload.get("consequence", None)

        # Resolve aliases to canonical scenario names
        scenario_name = _SCENARIO_ALIASES.get(scenario_name, scenario_name)

        scenario = next((s for s in ALL_SCENARIOS if s.name == scenario_name), None)
        if scenario is None:
            raise HTTPException(status_code=400, detail=f"Unknown scenario: {scenario_name}")

        # Resolve the user's selected policy (not the scenario's hardcoded policy)
        policy = _resolve_policy(policy_name)

        # Apply user's consequence override to the scenario's context
        context = _resolve_context(scenario.context, consequence)

        model = SimulatedModel()
        try:
            output = model.generate(scenario.model_scenario)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        from controlplane.detection.performance_types import Claim, Evidence

        claims = [Claim(**c) for c in output.claims] if output.claims else None
        evidence = [Evidence(**e) for e in output.evidence] if output.evidence else None

        result: ControlPlaneResult = runtime.check(
            request_text=output.request_text,
            response_text=output.response_text,
            context=context,
            policy=policy,
            model=output.model,
            provider=output.provider,
            metadata=output.metadata,
            claims=claims,
            evidence=evidence,
            auto_extract_claims=claims is None,
        )

        findings_data = [_serialize_finding(f) for f in result.interaction.findings]
        decision_history = [_serialize_decision(d) for d in result.interaction.decisions]

        # Use the terminal decision (last in history), not the initial decision.
        terminal_decision = result.interaction.decisions[-1].decision.value if result.interaction.decisions else result.decision.decision.value

        intervention_data = None
        if result.interaction.intervention:
            intervention_data = {
                "intervention_id": str(result.interaction.intervention.intervention_id),
                "action": result.interaction.intervention.action.value,
                "modification_type": result.interaction.intervention.modification_type.value if result.interaction.intervention.modification_type else None,
                "modification_detail": result.interaction.intervention.modification_detail,
                "blocked_reason": result.interaction.intervention.blocked_reason,
                "escalation_reason": result.interaction.intervention.escalation_reason,
            }

        outcome_data = None
        if result.interaction.outcome:
            outcome_data = {
                "outcome_type": result.interaction.outcome.outcome_type,
                "description": result.interaction.outcome.description,
            }

        return {
            "interaction_id": str(result.interaction.interaction_id),
            "scenario": scenario_name,
            "request_text": output.request_text,
            "response_text": output.response_text,
            "model": output.model,
            "provider": output.provider,
            "decision": terminal_decision,
            "released_response": result.released_response,
            "blocked": result.blocked,
            "escalated": result.escalated,
            "findings": findings_data,
            "decision_history": decision_history,
            "intervention": intervention_data,
            "outcome": outcome_data,
            "audit_persisted": result.audit_persisted,
            "policy_snapshot": policy.model_dump(mode="json"),
            "context": {
                "consequence": context.consequence.value,
                "use_case": context.use_case,
                "data_sensitivity": context.data_sensitivity.value,
                "latency_budget_ms": context.latency_budget_ms,
            },
            "applied_policy_name": policy_name,
        }

    @app.post("/demo/compare-policy")
    async def compare_policy(payload: dict) -> dict:
        """Compare the same model output under multiple governance policies.

        Generates ONE deterministic model output, then runs it through
        the ControlPlane runtime with each requested policy. The model
        output is IDENTICAL across all comparisons — only governance changes.

        Request:
            scenario: str — scenario name
            policies: list[str] — policy names to compare
            consequence: str | null — optional consequence override

        Response:
            model_output: { request_text, response_text, model, provider }
            findings: shared findings (same across all policies)
            comparisons: [ { policy_name, policy_snapshot, decision, intervention,
                             released_response, outcome } ]
        """
        scenario_name = payload.get("scenario", "clean")
        policy_names = payload.get("policies", ["Balanced", "Strict", "Lenient"])
        consequence = payload.get("consequence", None)

        scenario_name = _SCENARIO_ALIASES.get(scenario_name, scenario_name)
        scenario = next((s for s in ALL_SCENARIOS if s.name == scenario_name), None)
        if scenario is None:
            raise HTTPException(status_code=400, detail=f"Unknown scenario: {scenario_name}")

        # Generate model output ONCE — identical for all policies
        model = SimulatedModel()
        try:
            output = model.generate(scenario.model_scenario)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

        from controlplane.detection.performance_types import Claim, Evidence

        claims = [Claim(**c) for c in output.claims] if output.claims else None
        evidence = [Evidence(**e) for e in output.evidence] if output.evidence else None

        context = _resolve_context(scenario.context, consequence)

        comparisons = []
        for pname in policy_names:
            policy = _resolve_policy(pname)

            result: ControlPlaneResult = runtime.check(
                request_text=output.request_text,
                response_text=output.response_text,
                context=context,
                policy=policy,
                model=output.model,
                provider=output.provider,
                metadata=output.metadata,
                claims=claims,
                evidence=evidence,
                auto_extract_claims=claims is None,
            )

            terminal_decision = (
                result.interaction.decisions[-1].decision.value
                if result.interaction.decisions
                else result.decision.decision.value
            )

            intervention_data = None
            if result.interaction.intervention:
                intervention_data = {
                    "intervention_id": str(result.interaction.intervention.intervention_id),
                    "action": result.interaction.intervention.action.value,
                    "modification_type": result.interaction.intervention.modification_type.value if result.interaction.intervention.modification_type else None,
                    "modification_detail": result.interaction.intervention.modification_detail,
                    "blocked_reason": result.interaction.intervention.blocked_reason,
                    "escalation_reason": result.interaction.intervention.escalation_reason,
                }

            outcome_data = None
            if result.interaction.outcome:
                outcome_data = {
                    "outcome_type": result.interaction.outcome.outcome_type,
                    "description": result.interaction.outcome.description,
                }

            comparisons.append({
                "policy_name": pname,
                "policy_snapshot": policy.model_dump(mode="json"),
                "findings": [_serialize_finding(f) for f in result.interaction.findings],
                "decision": terminal_decision,
                "intervention": intervention_data,
                "released_response": result.released_response,
                "outcome": outcome_data,
                "blocked": result.blocked,
                "escalated": result.escalated,
            })

        return {
            "model_output": {
                "request_text": output.request_text,
                "response_text": output.response_text,
                "model": output.model,
                "provider": output.provider,
            },
            "scenario": scenario_name,
            "context": {
                "consequence": context.consequence.value,
                "use_case": context.use_case,
                "data_sensitivity": context.data_sensitivity.value,
                "latency_budget_ms": context.latency_budget_ms,
            },
            "comparisons": comparisons,
        }

    @app.post("/check/text")
    async def check_text(payload: dict) -> dict:
        """Simplified check endpoint: send text, get analysis.

        This is the primary endpoint for the Live Monitor UI.
        Accepts optional metadata (token counts, latency) for cost detection.
        """
        request_text = payload.get("request_text", "")
        response_text = payload.get("response_text", "")
        model = payload.get("model", "user_input")
        provider = payload.get("provider", "manual")
        metadata = payload.get("metadata", None)

        from controlplane.schemas.context import Context
        from controlplane.schemas.enums import Consequence

        context = Context(
            context_id=uuid.uuid4(),
            use_case="interactive",
            consequence=Consequence.MEDIUM,
            reversibility="reversible",
            downstream_action="none",
            data_sensitivity="internal",
            latency_budget_ms=5000.0,
        )
        # Use the real Balanced policy — this endpoint must NOT silently
        # bypass governance with an empty Policy object.
        policy = _resolve_policy("Balanced")

        result: ControlPlaneResult = runtime.check(
            request_text=request_text,
            response_text=response_text,
            context=context,
            policy=policy,
            model=model,
            provider=provider,
            metadata=metadata,
            auto_extract_claims=True,
        )

        findings_data = [_serialize_finding(f) for f in result.interaction.findings]
        decision_history = [_serialize_decision(d) for d in result.interaction.decisions]

        # Use the terminal decision (last in history), not the initial decision.
        terminal_decision = result.interaction.decisions[-1].decision.value if result.interaction.decisions else result.decision.decision.value

        intervention_data = None
        if result.interaction.intervention:
            intervention_data = {
                "action": result.interaction.intervention.action.value,
                "modification_type": result.interaction.intervention.modification_type.value if result.interaction.intervention.modification_type else None,
                "modification_detail": result.interaction.intervention.modification_detail,
                "blocked_reason": result.interaction.intervention.blocked_reason,
                "escalation_reason": result.interaction.intervention.escalation_reason,
            }

        return {
            "interaction_id": str(result.interaction.interaction_id),
            "request_text": request_text,
            "response_text": response_text,
            "decision": terminal_decision,
            "released_response": result.released_response,
            "blocked": result.blocked,
            "escalated": result.escalated,
            "findings": findings_data,
            "decision_history": decision_history,
            "intervention": intervention_data,
        }

    # ------------------------------------------------------------------
    # Traffic Interception (real-time observation)
    # ------------------------------------------------------------------

    @app.post("/traffic/observe")
    async def observe_traffic(payload: dict) -> dict:
        """Observe a model response through ControlPlane pipeline.

        Automatically processes the response through all detectors
        and stores the result for real-time viewing.
        """
        if interceptor is None:
            raise HTTPException(status_code=503, detail="Traffic interceptor not configured")

        try:
            request_text = payload.get("request_text", "")
            response_text = payload.get("response_text", "")
            model = payload.get("model", "unknown")
            provider = payload.get("provider", "unknown")
            metadata = payload.get("metadata", None)

            event = interceptor.observe(
                request_text=request_text,
                response_text=response_text,
                model=model,
                provider=provider,
                metadata=metadata,
            )

            return {
                "event_id": event.event_id,
                "timestamp": event.timestamp,
                "decision": event.decision,
                "findings_count": event.findings_count,
                "dimensions": event.dimensions,
                "intervention_action": event.intervention_action,
                "blocked": event.blocked,
                "escalated": event.escalated,
                "interaction_id": event.interaction_id,
            }
        except Exception as exc:
            logger.exception("Error observing traffic")
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.get("/traffic/events")
    async def list_traffic_events(
        limit: int = Query(50, ge=1, le=500),
        offset: int = Query(0, ge=0),
        decision: str | None = None,
    ) -> list[dict]:
        """List intercepted traffic events with pagination."""
        if interceptor is None:
            return []

        events = interceptor.get_events(limit=limit, offset=offset, decision=decision)

        return [
            {
                "event_id": e.event_id,
                "timestamp": e.timestamp,
                "request_text": e.request_text[:200],
                "response_text": e.response_text[:200],
                "model": e.model,
                "provider": e.provider,
                "decision": e.decision,
                "findings_count": e.findings_count,
                "dimensions": e.dimensions,
                "intervention_action": e.intervention_action,
                "blocked": e.blocked,
                "escalated": e.escalated,
                "interaction_id": e.interaction_id,
            }
            for e in events
        ]

    @app.get("/traffic/events/recent")
    async def get_recent_traffic_events(
        count: int = Query(10, ge=1, le=100),
    ) -> list[dict]:
        """Get N most recent intercepted traffic events (for real-time)."""
        if interceptor is None:
            return []

        events = interceptor.get_recent_events(count=count)

        return [
            {
                "event_id": e.event_id,
                "timestamp": e.timestamp,
                "request_text": e.request_text[:200],
                "response_text": e.response_text[:200],
                "model": e.model,
                "provider": e.provider,
                "decision": e.decision,
                "findings_count": e.findings_count,
                "dimensions": e.dimensions,
                "intervention_action": e.intervention_action,
                "blocked": e.blocked,
                "escalated": e.escalated,
                "interaction_id": e.interaction_id,
            }
            for e in events
        ]

    @app.get("/traffic/events/{event_id}")
    async def get_traffic_event(event_id: str) -> dict:
        """Get a specific traffic event by ID."""
        if interceptor is None:
            raise HTTPException(status_code=503, detail="Traffic interceptor not configured")

        event = interceptor.get_event(event_id)
        if event is None:
            raise HTTPException(status_code=404, detail="Event not found")

        return {
            "event_id": event.event_id,
            "timestamp": event.timestamp,
            "request_text": event.request_text,
            "response_text": event.response_text,
            "model": event.model,
            "provider": event.provider,
            "decision": event.decision,
            "findings_count": event.findings_count,
            "dimensions": event.dimensions,
            "intervention_action": event.intervention_action,
            "blocked": event.blocked,
            "escalated": event.escalated,
            "released_response": event.released_response,
            "metadata": event.metadata,
            "interaction_id": event.interaction_id,
        }

    @app.get("/traffic/stats")
    async def get_traffic_stats() -> dict:
        """Get aggregate traffic statistics."""
        if interceptor is None:
            return {
                "total_events": 0,
                "by_decision": {},
                "by_dimension": {},
                "avg_findings": 0,
                "blocked_count": 0,
                "escalated_count": 0,
            }

        return interceptor.get_stats()

    @app.post("/traffic/demo/start")
    async def start_demo_traffic(payload: dict) -> dict:
        """Start simulated traffic generation for demo."""
        if interceptor is None:
            raise HTTPException(status_code=503, detail="Traffic interceptor not configured")

        interval = payload.get("interval_seconds", 2.0)
        interceptor.start_demo_traffic(interval_seconds=interval)

        return {
            "status": "started",
            "interval_seconds": interval,
            "message": f"Demo traffic generation started (interval={interval}s)",
        }

    @app.post("/traffic/demo/stop")
    async def stop_demo_traffic() -> dict:
        """Stop simulated traffic generation."""
        if interceptor is None:
            raise HTTPException(status_code=503, detail="Traffic interceptor not configured")

        interceptor.stop_demo_traffic()

        return {
            "status": "stopped",
            "message": "Demo traffic generation stopped",
        }

    @app.delete("/traffic/events")
    async def clear_traffic_events() -> dict:
        """Clear all stored traffic events."""
        if interceptor is None:
            raise HTTPException(status_code=503, detail="Traffic interceptor not configured")

        interceptor.clear_events()

        return {"status": "cleared", "message": "All traffic events cleared"}

    return app
