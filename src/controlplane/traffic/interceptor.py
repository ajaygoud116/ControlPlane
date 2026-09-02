"""TrafficInterceptor — automatic capture and processing of AI model responses.

This service intercepts ALL model responses and processes them through
the full ControlPlane pipeline, storing results for real-time viewing.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from controlplane.runtime.runtime import ControlPlaneRuntime
from controlplane.runtime.result import ControlPlaneResult
from controlplane.schemas.context import Context
from controlplane.schemas.enums import (
    Consequence,
    DataSensitivity,
    DecisionAction,
    InterventionAction,
)
from controlplane.schemas.policy import Policy

logger = logging.getLogger(__name__)


@dataclass
class InterceptionEvent:
    """A single intercepted traffic event with full analysis result."""
    event_id: str
    timestamp: str
    request_text: str
    response_text: str
    model: str
    provider: str
    decision: str
    findings_count: int
    dimensions: list[str]
    intervention_action: str | None
    blocked: bool
    escalated: bool
    released_response: str | None
    metadata: dict[str, Any]
    interaction_id: str


class TrafficInterceptor:
    """Intercepts AI model responses and processes through ControlPlane.

    Provides:
    - observe(): Process a single response through pipeline
    - get_events(): Retrieve intercepted events (paginated)
    - get_recent_events(): Get N most recent events (for real-time)
    - generate_demo_traffic(): Generate simulated traffic for demo

    Events are stored in-memory (circular buffer, max 1000 events).
    """

    def __init__(
        self,
        runtime: ControlPlaneRuntime,
        *,
        max_events: int = 1000,
    ) -> None:
        """Initialize the TrafficInterceptor.

        Args:
            runtime: Configured ControlPlaneRuntime instance.
            max_events: Maximum events to retain in memory.
        """
        self._runtime = runtime
        self._max_events = max_events
        self._events: deque[InterceptionEvent] = deque(maxlen=max_events)
        self._lock = threading.Lock()

    def clear_events(self) -> None:
        """Clear all stored interception events."""
        with self._lock:
            self._events.clear()
        self._demo_generator_running = False
        self._demo_stop_event = threading.Event()

    def observe(
        self,
        request_text: str,
        response_text: str,
        *,
        model: str = "unknown",
        provider: str = "unknown",
        metadata: dict[str, Any] | None = None,
        context: Context | None = None,
        policy: Policy | None = None,
    ) -> InterceptionEvent:
        """Observe a model response through the ControlPlane pipeline.

        Processes the response through all detectors, decision engine,
        and intervention logic. Stores the result for real-time viewing.

        Args:
            request_text: User's input text.
            response_text: Model's output text.
            model: Model identifier.
            provider: Provider identifier.
            metadata: Runtime telemetry (tokens, latency, etc.).
            context: Optional Context override. Uses default if None.
            policy: Optional Policy override. Uses default if None.

        Returns:
            InterceptionEvent with full analysis result.
        """
        # Use default context/policy if not provided
        if context is None:
            context = Context(
                context_id=uuid4(),
                use_case="intercepted",
                consequence=Consequence.MEDIUM,
                reversibility="reversible",
                downstream_action="none",
                data_sensitivity=DataSensitivity.INTERNAL,
                latency_budget_ms=5000.0,
            )
        if policy is None:
            from controlplane.policy_registry import get_default_policy
            policy = get_default_policy()

        # Process through ControlPlane pipeline
        result: ControlPlaneResult = self._runtime.check(
            request_text=request_text,
            response_text=response_text,
            context=context,
            policy=policy,
            model=model,
            provider=provider,
            metadata=metadata,
            auto_extract_claims=True,
        )

        # Extract findings summary
        findings = result.interaction.findings
        dimensions = list({f.dimension.value for f in findings})

        # Determine intervention action
        intervention_action = None
        if result.interaction.intervention:
            intervention_action = result.interaction.intervention.action.value

        # Create event
        event = InterceptionEvent(
            event_id=str(uuid4()),
            timestamp=datetime.now(timezone.utc).isoformat(),
            request_text=request_text,
            response_text=response_text,
            model=model,
            provider=provider,
            decision=result.decision.decision.value,
            findings_count=len(findings),
            dimensions=dimensions,
            intervention_action=intervention_action,
            blocked=result.blocked,
            escalated=result.escalated,
            released_response=result.released_response,
            metadata=metadata or {},
            interaction_id=str(result.interaction.interaction_id),
        )

        # Store event
        with self._lock:
            self._events.appendleft(event)

        logger.info(
            "Observed response: model=%s decision=%s findings=%d dimensions=%s",
            model, event.decision, event.findings_count, dimensions,
        )

        return event

    def get_events(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        decision: str | None = None,
    ) -> list[InterceptionEvent]:
        """Retrieve intercepted events with pagination.

        Args:
            limit: Maximum events to return.
            offset: Number of events to skip.
            decision: Optional filter by decision type.

        Returns:
            List of InterceptionEvent objects.
        """
        with self._lock:
            events = list(self._events)

        if decision:
            events = [e for e in events if e.decision == decision]

        return events[offset:offset + limit]

    def get_recent_events(self, count: int = 10) -> list[InterceptionEvent]:
        """Get the N most recent intercepted events.

        Args:
            count: Number of recent events to return.

        Returns:
            List of InterceptionEvent objects, newest first.
        """
        with self._lock:
            return list(self._events)[:count]

    def get_event(self, event_id: str) -> InterceptionEvent | None:
        """Get a specific event by ID.

        Args:
            event_id: The event identifier.

        Returns:
            InterceptionEvent if found, None otherwise.
        """
        with self._lock:
            for event in self._events:
                if event.event_id == event_id:
                    return event
        return None

    def get_stats(self) -> dict[str, Any]:
        """Get aggregate statistics about intercepted traffic.

        Returns:
            Dictionary with traffic statistics.
        """
        with self._lock:
            events = list(self._events)

        if not events:
            return {
                "total_events": 0,
                "by_decision": {},
                "by_dimension": {},
                "avg_findings": 0,
                "blocked_count": 0,
                "escalated_count": 0,
            }

        by_decision: dict[str, int] = {}
        by_dimension: dict[str, int] = {}
        total_findings = 0
        blocked_count = 0
        escalated_count = 0

        for event in events:
            by_decision[event.decision] = by_decision.get(event.decision, 0) + 1
            for dim in event.dimensions:
                by_dimension[dim] = by_dimension.get(dim, 0) + 1
            total_findings += event.findings_count
            if event.blocked:
                blocked_count += 1
            if event.escalated:
                escalated_count += 1

        return {
            "total_events": len(events),
            "by_decision": by_decision,
            "by_dimension": by_dimension,
            "avg_findings": total_findings / len(events),
            "blocked_count": blocked_count,
            "escalated_count": escalated_count,
        }

    def clear_events(self) -> None:
        """Clear all stored events."""
        with self._lock:
            self._events.clear()

    def start_demo_traffic(self, interval_seconds: float = 2.0) -> None:
        """Start generating simulated traffic for demo.

        Generates traffic using the SimulatedModel with various scenarios
        at the specified interval.

        Args:
            interval_seconds: Time between generated events.
        """
        if self._demo_generator_running:
            logger.warning("Demo traffic generator already running")
            return

        self._demo_stop_event.clear()
        self._demo_generator_running = True

        def _generate():
            from controlplane.demo.simulated_model import SimulatedModel

            model = SimulatedModel()
            scenarios = model.list_scenarios()
            scenario_index = 0

            while not self._demo_stop_event.is_set():
                try:
                    scenario_name = scenarios[scenario_index % len(scenarios)]
                    output = model.generate(scenario_name)

                    # Build metadata with model info
                    metadata = dict(output.metadata)
                    metadata["model"] = output.model
                    metadata["provider"] = output.provider

                    self.observe(
                        request_text=output.request_text,
                        response_text=output.response_text,
                        model=output.model,
                        provider=output.provider,
                        metadata=metadata,
                    )

                    scenario_index += 1
                except Exception as exc:
                    logger.error("Demo traffic generation error: %s", exc)

                # Wait for interval or stop signal
                self._demo_stop_event.wait(timeout=interval_seconds)

        thread = threading.Thread(target=_generate, daemon=True)
        thread.start()
        logger.info("Started demo traffic generator (interval=%.1fs)", interval_seconds)

    def stop_demo_traffic(self) -> None:
        """Stop the demo traffic generator."""
        if not self._demo_generator_running:
            return

        self._demo_stop_event.set()
        self._demo_generator_running = False
        logger.info("Stopped demo traffic generator")

    @property
    def is_demo_running(self) -> bool:
        """Check if demo traffic generator is running."""
        return self._demo_generator_running
