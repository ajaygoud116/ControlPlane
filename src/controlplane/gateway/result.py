"""Gateway result — extends ControlPlaneResult with gateway-specific measurements.

The GatewayResult adds latency timing and model failure information
to the existing ControlPlaneResult. It does NOT replace ControlPlaneResult.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from controlplane.runtime.result import ControlPlaneResult


@dataclass
class LatencyBreakdown:
    """Latency measurements from the gateway."""

    model_latency_ms: float = 0.0
    controlplane_latency_ms: float = 0.0
    total_latency_ms: float = 0.0


@dataclass
class GatewayResult:
    """Result of a gateway-controlled model interaction.

    Extends ControlPlaneResult with:
    - latency breakdown (model vs ControlPlane vs total)
    - model failure information
    - original model response (before intervention)

    The caller receives:
    - released_response: what to deliver (None if blocked/escalated)
    - blocked: whether the response was blocked
    - escalated: whether the response was escalated
    - model_failed: whether the model itself failed
    - model_error: error message if model failed
    """

    # Core ControlPlane results (delegated from ControlPlaneResult)
    control_plane_result: ControlPlaneResult

    # Gateway-specific measurements
    latency: LatencyBreakdown = field(default_factory=LatencyBreakdown)

    # Model failure information
    model_failed: bool = False
    model_error: str | None = None

    # Original model response (before any intervention)
    original_response: str | None = None

    @property
    def released_response(self) -> str | None:
        """Response text to deliver to the caller."""
        if self.model_failed:
            return None
        return self.control_plane_result.released_response

    @property
    def blocked(self) -> bool:
        """Whether the response was blocked."""
        return self.control_plane_result.blocked

    @property
    def escalated(self) -> bool:
        """Whether the response was escalated."""
        return self.control_plane_result.escalated

    @property
    def decision(self):
        """The terminal decision."""
        return self.control_plane_result.decision

    @property
    def interaction(self):
        """The interaction object."""
        return self.control_plane_result.interaction

    @property
    def audit_record(self):
        """The audit record."""
        return self.control_plane_result.audit_record

    @property
    def audit_persisted(self) -> bool:
        """Whether audit was persisted."""
        return self.control_plane_result.audit_persisted

    @property
    def audit_persist_error(self) -> str | None:
        """Audit persistence error if any."""
        return self.control_plane_result.audit_persist_error
