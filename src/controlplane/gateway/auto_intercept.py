"""Auto-intercepting gateway wrapper for automatic traffic observation.

This module wraps ControlPlaneGateway to automatically observe ALL model
responses through the TrafficInterceptor, enabling continuous real-time
observation without requiring manual /check calls.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from controlplane.gateway.adapter import ModelAdapter, ModelResponse
from controlplane.gateway.gateway import ControlPlaneGateway
from controlplane.gateway.result import GatewayResult
from controlplane.runtime.runtime import ControlPlaneRuntime
from controlplane.schemas.context import Context
from controlplane.schemas.policy import Policy
from controlplane.traffic.interceptor import TrafficInterceptor

logger = logging.getLogger(__name__)


class AutoInterceptGateway:
    """Gateway wrapper that automatically intercepts all model responses.

    Wraps ControlPlaneGateway and adds automatic observation through
    TrafficInterceptor. Every model call is automatically processed
    and stored for real-time viewing.

    Usage::

        gateway = AutoInterceptGateway(
            runtime=controlplane_runtime,
            model=my_model_callable,
            interceptor=traffic_interceptor,
        )
        result = gateway.invoke(
            request_text="Hello",
            context=context,
            policy=policy,
        )
        # Response is automatically intercepted and available in real-time view
    """

    def __init__(
        self,
        runtime: ControlPlaneRuntime,
        model: ModelAdapter,
        interceptor: TrafficInterceptor,
    ) -> None:
        """Initialize the auto-intercepting gateway.

        Args:
            runtime: Configured ControlPlaneRuntime instance.
            model: Model callable that satisfies the ModelAdapter protocol.
            interceptor: TrafficInterceptor for automatic observation.
        """
        self._gateway = ControlPlaneGateway(runtime, model)
        self._interceptor = interceptor
        self._runtime = runtime

    def invoke(
        self,
        request_text: str,
        context: Context,
        policy: Policy,
        *,
        model_kwargs: dict[str, Any] | None = None,
    ) -> GatewayResult:
        """Invoke the model with automatic traffic interception.

        Calls the underlying gateway and automatically observes the
        response through the TrafficInterceptor.

        Args:
            request_text: The user's input text.
            context: Situational information for this interaction.
            policy: Decision policy for this interaction.
            model_kwargs: Additional kwargs to pass to the model callable.

        Returns:
            GatewayResult with controlled output and timing breakdown.
        """
        # Call the underlying gateway
        result = self._gateway.invoke(
            request_text=request_text,
            context=context,
            policy=policy,
            model_kwargs=model_kwargs,
        )

        # Automatically observe the response
        try:
            metadata = {}
            if result.control_plane_result.interaction.observations:
                for obs in result.control_plane_result.interaction.observations:
                    if hasattr(obs, 'payload') and isinstance(obs.payload, dict):
                        metadata.update(obs.payload)

            self._interceptor.observe(
                request_text=request_text,
                response_text=result.original_response or "",
                model=result.control_plane_result.interaction.model or "unknown",
                provider=result.control_plane_result.interaction.provider or "unknown",
                metadata=metadata,
                context=context,
                policy=policy,
            )
        except Exception as exc:
            # Don't fail the gateway call if observation fails
            logger.warning("Auto-interception failed: %s", exc)

        return result

    def observe_text(
        self,
        request_text: str,
        response_text: str,
        *,
        model: str = "unknown",
        provider: str = "unknown",
        metadata: dict[str, Any] | None = None,
    ) -> dict:
        """Observe a pre-existing model response without calling the model.

        Use this when you already have the model response and just want
        to observe it through the pipeline.

        Args:
            request_text: User's input text.
            response_text: Model's output text.
            model: Model identifier.
            provider: Provider identifier.
            metadata: Runtime telemetry (tokens, latency, etc.).

        Returns:
            Observation result with event_id and decision.
        """
        event = self._interceptor.observe(
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
