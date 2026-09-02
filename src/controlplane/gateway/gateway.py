"""ControlPlaneGateway — model-agnostic interceptor.

Wraps an arbitrary model callable and controls release through the
existing ControlPlane pipeline. The gateway is thin — it does NOT
contain detector logic, decision logic, or intervention logic.

Architecture:

    caller -> gateway -> model -> gateway -> ControlPlaneRuntime -> result

The gateway:
1. Creates an interaction boundary
2. Records request timing
3. Invokes the underlying model
4. Measures model execution time
5. Passes output into existing ControlPlaneRuntime
6. Returns the resulting controlled output

The gateway does NOT:
- Implement detectors
- Implement decision logic
- Implement policy evaluation
- Implement verification
- Implement intervention logic
- Import specific model providers

It delegates entirely to existing production components.
"""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import uuid4

from controlplane.gateway.adapter import ModelAdapter, ModelResponse
from controlplane.gateway.result import GatewayResult, LatencyBreakdown
from controlplane.runtime.runtime import ControlPlaneRuntime
from controlplane.runtime.result import ControlPlaneResult
from controlplane.schemas.context import Context
from controlplane.schemas.enums import DecisionAction, FailureMode
from controlplane.schemas.policy import Policy

logger = logging.getLogger(__name__)


class ControlPlaneGateway:
    """Model-agnostic ControlPlane interceptor.

    Wraps a model callable and controls release through the existing
    ControlPlane pipeline. The gateway is thin — it delegates all
    detection, decision, and intervention logic to production components.

    Usage::

        gateway = ControlPlaneGateway(
            runtime=controlplane_runtime,
            model=my_model_callable,
        )
        result = gateway.invoke(
            request_text="Hello",
            context=context,
            policy=policy,
        )
        if result.released_response:
            print(result.released_response)
        else:
            print(f"Blocked: {result.blocked}, Escalated: {result.escalated}")
    """

    def __init__(
        self,
        runtime: ControlPlaneRuntime,
        model: ModelAdapter,
    ) -> None:
        """Initialize the gateway.

        Args:
            runtime: Configured ControlPlaneRuntime instance.
            model: Model callable that satisfies the ModelAdapter protocol.
        """
        self._runtime = runtime
        self._model = model

    def invoke(
        self,
        request_text: str,
        context: Context,
        policy: Policy,
        *,
        model_kwargs: dict[str, Any] | None = None,
    ) -> GatewayResult:
        """Invoke the model and ControlPlane in a single gateway call.

        This is the primary gateway method. It:
        1. Records pre-model timing
        2. Calls the model
        3. Measures model latency
        4. Calls ControlPlaneRuntime.check() with the model output
        5. Returns a GatewayResult with full timing breakdown

        Args:
            request_text: The user's input text.
            context: Situational information for this interaction.
            policy: Decision policy for this interaction.
            model_kwargs: Additional kwargs to pass to the model callable.

        Returns:
            GatewayResult with controlled output and timing breakdown.
        """
        model_kwargs = model_kwargs or {}
        latency = LatencyBreakdown()

        # Phase 1: Pre-model timing
        t_total_start = time.perf_counter()

        # Phase 2: Invoke the model
        t_model_start = time.perf_counter()
        model_response: ModelResponse | None = None
        model_failed = False
        model_error: str | None = None

        try:
            model_response = self._model(request_text, **model_kwargs)
        except Exception as exc:
            model_failed = True
            model_error = str(exc)
            logger.warning("Model execution failed: %s", exc)

        t_model_end = time.perf_counter()
        latency.model_latency_ms = (t_model_end - t_model_start) * 1000

        # Phase 3: Handle model failure
        if model_failed:
            gateway_result = self._handle_model_failure(
                request_text, context, policy, model_error, latency,
                t_total_start,
            )
            return gateway_result

        # Phase 4: Extract model output
        assert model_response is not None  # for type checker
        response_text = model_response.response_text
        metadata = self._build_metadata(model_response, latency.model_latency_ms)

        # Phase 5: Call ControlPlaneRuntime
        t_cp_start = time.perf_counter()

        # Parse claims/evidence if provided
        claims = None
        evidence = None
        if model_response.claims is not None:
            from controlplane.detection.performance_types import Claim
            claims = [Claim(**c) if isinstance(c, dict) else c for c in model_response.claims]
        if model_response.evidence is not None:
            from controlplane.detection.performance_types import Evidence
            evidence = [Evidence(**e) if isinstance(e, dict) else e for e in model_response.evidence]

        cp_result: ControlPlaneResult = self._runtime.check(
            request_text=request_text,
            response_text=response_text,
            context=context,
            policy=policy,
            model=model_response.model,
            provider=model_response.provider,
            metadata=metadata,
            claims=claims,
            evidence=evidence,
            auto_extract_claims=True,
        )

        t_cp_end = time.perf_counter()
        latency.controlplane_latency_ms = (t_cp_end - t_cp_start) * 1000

        # Phase 6: Compute total latency
        t_total_end = time.perf_counter()
        latency.total_latency_ms = (t_total_end - t_total_start) * 1000

        # Phase 7: Return gateway result
        return GatewayResult(
            control_plane_result=cp_result,
            latency=latency,
            model_failed=False,
            model_error=None,
            original_response=response_text,
        )

    def _handle_model_failure(
        self,
        request_text: str,
        context: Context,
        policy: Policy,
        model_error: str | None,
        latency: LatencyBreakdown,
        t_total_start: float,
    ) -> GatewayResult:
        """Handle a model execution failure.

        Uses the policy's failure_mode to determine the appropriate response.
        Does NOT fabricate a model response.
        """
        # Determine failure action from policy
        failure_action = policy.failure_mode

        # Create a minimal ControlPlaneResult for the failure
        # We construct a minimal interaction and decision
        from controlplane.schemas.interaction import Interaction
        from controlplane.schemas.decision import Decision
        from controlplane.schemas.enums import DecisionAction
        from datetime import datetime, timezone

        interaction = Interaction(
            request_text=request_text,
            response_text="[MODEL_EXECUTION_FAILURE]",
            model="failed",
            provider="failed",
            context=context,
        )

        # Map failure_mode to decision action
        if failure_action == FailureMode.BLOCK:
            decision_action = DecisionAction.BLOCK
        elif failure_action == FailureMode.ALLOW:
            decision_action = DecisionAction.ALLOW
        else:
            decision_action = DecisionAction.ESCALATE

        decision = Decision(
            decision_id=uuid4(),
            interaction_id=interaction.interaction_id,
            decision_version="1.0.0",
            decision=decision_action,
            reason_codes=["model_execution_failure"],
            finding_ids=[],
            policy_id=policy.policy_id,
            policy_version=policy.version,
            required_assurance="basic_detection",
            current_assurance="basic_detection",
            selected_verifier=None,
            decided_at=datetime.now(timezone.utc),
        )
        interaction.decisions.append(decision)
        interaction.final_decision_id = decision.decision_id

        # Determine release semantics
        if decision_action == DecisionAction.BLOCK:
            released_response = None
            blocked = True
            escalated = False
        elif decision_action == DecisionAction.ESCALATE:
            released_response = None
            blocked = False
            escalated = True
        else:
            # ALLOW on model failure — no response to release
            released_response = None
            blocked = False
            escalated = False

        # Create minimal AuditRecord
        from controlplane.schemas.audit_record import AuditRecord

        audit_record = AuditRecord(
            interaction_id=interaction.interaction_id,
            interaction=interaction,
            observations=[],
            findings=[],
            context=context,
            policy_id=policy.policy_id,
            policy_version=policy.version,
            decisions=interaction.decisions,
            final_decision_id=interaction.final_decision_id,
            verification_events=[],
            intervention=None,
            outcome=None,
            frozen_v1_version="0.1.0",
        )

        # Persist model failure audit record
        audit_persisted = False
        audit_persist_error: str | None = None
        if self._runtime._audit_store is not None:
            try:
                self._runtime._audit_store.save(audit_record)
                audit_persisted = True
            except Exception as exc:
                audit_persist_error = str(exc)

        # Build ControlPlaneResult
        cp_result = ControlPlaneResult(
            interaction=interaction,
            decision=decision,
            audit_record=audit_record,
            released_response=released_response,
            blocked=blocked,
            escalated=escalated,
            audit_persisted=audit_persisted,
            audit_persist_error=audit_persist_error,
        )

        # Compute total latency
        t_total_end = time.perf_counter()
        latency.total_latency_ms = (t_total_end - t_total_start) * 1000

        return GatewayResult(
            control_plane_result=cp_result,
            latency=latency,
            model_failed=True,
            model_error=model_error,
            original_response=None,
        )

    def _build_metadata(
        self, model_response: ModelResponse, model_latency_ms: float
    ) -> dict[str, Any]:
        """Build metadata dict for ControlPlane from model response.

        Combines model-provided metadata with gateway-measured latency.
        Does NOT fabricate missing data.
        """
        metadata = dict(model_response.metadata) if model_response.metadata else {}

        # Add gateway-measured latency if not already in metadata
        if "latency_ms" not in metadata:
            metadata["latency_ms"] = model_latency_ms

        # Ensure model/provider are in metadata
        if "model" not in metadata:
            metadata["model"] = model_response.model
        if "provider" not in metadata:
            metadata["provider"] = model_response.provider

        return metadata
