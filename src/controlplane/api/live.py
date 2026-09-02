"""Live model endpoints — real model → ControlPlane flow.

Provides endpoints for:
- POST /live/run — run a prompt through a real model + ControlPlane
- GET /live/status — check if a live model is available

The model adapter is injected at startup. If no API key is configured,
the endpoint returns an explicit unavailability signal.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from controlplane.gateway.adapter import ModelAdapter, ModelResponse
from controlplane.gateway.gateway import ControlPlaneGateway
from controlplane.gateway.result import GatewayResult
from controlplane.runtime.runtime import ControlPlaneRuntime
from controlplane.schemas.context import Context
from controlplane.schemas.enums import (
    Consequence,
    DataSensitivity,
    InterventionAction,
)
from controlplane.policy_registry import POLICY_REGISTRY, get_default_policy
from controlplane.schemas.policy import Policy

logger = logging.getLogger(__name__)

router = APIRouter()

# Module-level state set by configure_live_router()
_gateway: ControlPlaneGateway | None = None
_live_available: bool = False
_model_name: str = "none"
_model_provider: str = "none"


def _get_policy(policy_name: str | None) -> Policy:
    """Get policy by name from the shared registry.

    Falls back to the default (Balanced) policy if name is None or not found.
    """
    if policy_name:
        policy = POLICY_REGISTRY.get(policy_name)
        if policy is not None:
            return policy
    return get_default_policy()


def configure_live_router(
    runtime: ControlPlaneRuntime,
    model: ModelAdapter | None = None,
) -> None:
    """Configure the live router with a model adapter.

    Called once at startup from main.py.
    """
    global _gateway, _live_available, _model_name, _model_provider

    if model is not None:
        _gateway = ControlPlaneGateway(runtime=runtime, model=model)
        _live_available = True
        # Try to get model name from a probe call or config
        try:
            test_resp = model("hi")
            _model_name = test_resp.model
            _model_provider = test_resp.provider
        except Exception:
            _model_name = "configured"
            _model_provider = "live"
    else:
        _live_available = False
        _model_name = "none"
        _model_provider = "none"


class LiveRunRequest(BaseModel):
    prompt: str
    model: str | None = None
    consequence: str | None = None  # "low" | "medium" | "high"
    policy_id: str | None = None  # Select from available policies


class LiveRunResponse(BaseModel):
    request_text: str
    model_name: str
    model_provider: str
    model_output: str
    findings: list[dict[str, Any]]
    decisions: list[dict[str, Any]]
    decision: str
    intervention: str
    intervention_detail: dict[str, Any] | None
    final_response: str
    telemetry: dict[str, Any]
    interaction_id: str
    audit_id: str | None
    live: bool
    policy_id: str
    consequence: str


@router.get("/live/status")
async def live_status() -> dict[str, Any]:
    """Check if a live model is available."""
    from controlplane.policy_registry import list_policy_names
    return {
        "available": _live_available,
        "model": _model_name,
        "provider": _model_provider,
        "policies": list_policy_names(),
    }


@router.post("/live/run", response_model=LiveRunResponse)
async def live_run(request: LiveRunRequest) -> LiveRunResponse:
    """Run a prompt through the real model + ControlPlane pipeline.

    Flow:
        user prompt → model → ControlPlane → final response
    """
    if not _live_available or _gateway is None:
        raise HTTPException(
            status_code=503,
            detail="Live model not available. Set OPENAI_API_KEY environment variable.",
        )

    # Build context with configurable consequence
    consequence_str = (request.consequence or "low").lower()
    consequence_map = {
        "low": Consequence.LOW,
        "medium": Consequence.MEDIUM,
        "high": Consequence.HIGH,
    }
    consequence = consequence_map.get(consequence_str, Consequence.LOW)

    context = Context(
        context_id=uuid4(),
        use_case="live",
        consequence=consequence,
        reversibility="reversible",
        downstream_action="none",
        data_sensitivity=DataSensitivity.INTERNAL,
        latency_budget_ms=30000.0,
    )

    # Build policy - use registered policy if specified, otherwise default
    policy = _get_policy(request.policy_id)

    # Invoke gateway: model → ControlPlane
    t_start = time.perf_counter()
    gateway_result: GatewayResult = _gateway.invoke(
        request_text=request.prompt,
        context=context,
        policy=policy,
    )
    t_end = time.perf_counter()

    cp_result = gateway_result.control_plane_result
    interaction = cp_result.interaction

    # Extract terminal decision
    terminal_decision = interaction.decisions[-1] if interaction.decisions else cp_result.decision
    decision_value = terminal_decision.decision.value

    # Determine intervention
    intervention_action = "allow"
    intervention_detail: dict[str, Any] | None = None
    if interaction.intervention:
        intervention_action = interaction.intervention.action.value
        if interaction.intervention.modification_detail:
            intervention_detail = {
                "type": interaction.intervention.modification_type.value if interaction.intervention.modification_type else None,
                "detail": interaction.intervention.modification_detail,
            }

    # Determine final response
    if cp_result.released_response:
        final_response = cp_result.released_response
    elif cp_result.blocked:
        final_response = "Response blocked by ControlPlane policy."
    elif cp_result.escalated:
        final_response = "Response held for review."
    else:
        final_response = interaction.response_text

    # Serialize findings
    findings_data = []
    for f in interaction.findings:
        findings_data.append({
            "finding_id": str(f.finding_id),
            "dimension": f.dimension.value,
            "state": f.state.value if hasattr(f.state, "value") else str(f.state),
            "detector_id": f.detector_id,
            "explanation": f.explanation,
            "evidence": {
                "claim_text": f.evidence.claim_text,
                "source_ids": f.evidence.source_ids,
                "counter_evidence": f.evidence.counter_evidence,
            } if f.evidence else None,
            "measurement": {
                "input_tokens": f.measurement.input_tokens,
                "output_tokens": f.measurement.output_tokens,
                "latency_ms": f.measurement.latency_ms,
                "estimated_cost_usd": f.measurement.estimated_cost_usd,
            } if f.measurement else None,
        })

    # Serialize decisions
    decisions_data = []
    for d in interaction.decisions:
        decisions_data.append({
            "decision_id": str(d.decision_id),
            "decision": d.decision.value,
            "reason_codes": d.reason_codes,
            "required_assurance": d.required_assurance,
            "current_assurance": d.current_assurance,
            "selected_verifier": d.selected_verifier,
        })

    # Telemetry — extract from MODEL_RUNTIME observation
    telemetry = {
        "latency_ms": None,
        "input_tokens": None,
        "output_tokens": None,
        "cost_usd": None,
    }

    model_name = interaction.model or "unknown"
    model_provider_name = interaction.provider or "unknown"

    for obs in interaction.observations:
        if obs.observation_type.value == "model_runtime" and isinstance(obs.payload, dict):
            payload = obs.payload
            telemetry["latency_ms"] = payload.get("latency_ms")
            telemetry["input_tokens"] = payload.get("input_tokens")
            telemetry["output_tokens"] = payload.get("output_tokens")
            telemetry["cost_usd"] = payload.get("estimated_cost_usd")
            if payload.get("model"):
                model_name = payload["model"]
            if payload.get("provider"):
                model_provider_name = payload["provider"]
            break

    # Fallback to gateway latency
    if telemetry["latency_ms"] is None:
        telemetry["latency_ms"] = round(gateway_result.latency.model_latency_ms, 1)

    return LiveRunResponse(
        request_text=request.prompt,
        model_name=model_name,
        model_provider=model_provider_name,
        model_output=interaction.response_text,
        findings=findings_data,
        decisions=decisions_data,
        decision=decision_value,
        intervention=intervention_action,
        intervention_detail=intervention_detail,
        final_response=final_response,
        telemetry=telemetry,
        interaction_id=str(interaction.interaction_id),
        audit_id=str(cp_result.audit_record.audit_id) if cp_result.audit_record else None,
        live=True,
        policy_id=str(policy.policy_id),
        consequence=consequence.value,
    )
