"""Verifier capability model — describes what verifiers can resolve."""

from __future__ import annotations

from dataclasses import dataclass, field

from controlplane.schemas.enums import UncertaintyType


@dataclass(frozen=True)
class VerifierCapability:
    """Describes a verifier's resolution capability and cost profile.

    This is NOT a verifier implementation. It is a capability descriptor
    that the decision engine uses for verifier selection.
    """

    name: str
    uncertainty_types: list[UncertaintyType] = field(default_factory=list)
    expected_latency_ms: float = 0.0
    expected_cost_usd: float = 0.0
