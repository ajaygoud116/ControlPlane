"""RiskRegistry — fail-closed recognition of finding states.

The RiskRegistry answers one question: is this finding state recognized?

It does NOT:
- Determine the final action (BLOCK, ESCALATE, etc.)
- Assign risk scores
- Replace the decision engine

It does:
- Map (dimension, state) → recognized risk classification
- Return UNKNOWN for unrecognized combinations
- Enable fail-closed behavior in the decision engine

Architecture:

    Finding → RiskRegistry.lookup() → Recognized | Unknown
                                          ↓              ↓
                                    Existing       ESCALATE
                                    Decision       (fail-closed)
                                    Engine

The registry is the narrow safety boundary that prevents unknown
findings from silently passing through to ALLOW.
"""

from __future__ import annotations

from dataclasses import dataclass

from controlplane.schemas.enums import (
    CostState,
    FindingDimension,
    PerformanceState,
    PIIState,
    PolicyState,
    ResponsibilityState,
    RuntimeState,
)


@dataclass(frozen=True)
class RiskClassification:
    """Result of a risk registry lookup.

    Attributes:
        recognized: Whether this (dimension, state) combination is known.
        category: Human-readable risk category (e.g. 'pii', 'security').
        decision_relevant: Whether this state should influence the decision.
                          Observational states (e.g. RESPONSIBILITY_CLEAN)
                          are recognized but not decision-relevant.
    """

    recognized: bool
    category: str
    decision_relevant: bool


# The single source of truth for recognized finding states.
# Derived from: enums.py, hard_constraints.py, assurance.py, decide.py
# Each entry: (dimension_value, state_value) → RiskClassification
_KNOWN_RISKS: dict[tuple[str, str], RiskClassification] = {}

# Performance states
for _state in PerformanceState:
    _KNOWN_RISKS[("performance", _state.value)] = RiskClassification(
        recognized=True,
        category="performance",
        decision_relevant=_state != PerformanceState.SUPPORTED,
    )

# PII states
for _state in PIIState:
    _KNOWN_RISKS[("pii", _state.value)] = RiskClassification(
        recognized=True,
        category="pii",
        decision_relevant=_state == PIIState.PII_DETECTED,
    )

# Policy states
for _state in PolicyState:
    _KNOWN_RISKS[("policy", _state.value)] = RiskClassification(
        recognized=True,
        category="policy",
        decision_relevant=_state == PolicyState.POLICY_VIOLATION,
    )

# Runtime states
for _state in RuntimeState:
    _KNOWN_RISKS[("runtime", _state.value)] = RiskClassification(
        recognized=True,
        category="runtime",
        decision_relevant=_state == RuntimeState.RUNTIME_ANOMALY,
    )

# Cost states
for _state in CostState:
    _KNOWN_RISKS[("cost", _state.value)] = RiskClassification(
        recognized=True,
        category="cost",
        decision_relevant=_state not in (
            CostState.COST_WITHIN_BUDGET,
            CostState.COST_UNAVAILABLE,
        ),
    )

# Responsibility states
for _state in ResponsibilityState:
    _KNOWN_RISKS[("responsibility", _state.value)] = RiskClassification(
        recognized=True,
        category="responsibility",
        decision_relevant=_state != ResponsibilityState.RESPONSIBILITY_CLEAN,
    )

# Sentinel for unknown combinations
_UNKNOWN = RiskClassification(
    recognized=False,
    category="unknown",
    decision_relevant=True,  # Unknown findings are always decision-relevant
)


class RiskRegistry:
    """Registry of recognized finding states.

    The registry is built once at initialization and does not change.
    It maps (dimension, state) → RiskClassification.

    Usage::

        registry = RiskRegistry()
        result = registry.lookup("pii", "pii_detected")
        if not result.recognized:
            # fail-closed: ESCALATE
    """

    def __init__(self) -> None:
        self._risks = dict(_KNOWN_RISKS)

    def lookup(self, dimension: str, state: str) -> RiskClassification:
        """Look up a finding's risk classification.

        Args:
            dimension: The finding dimension (e.g. "pii", "responsibility").
            state: The finding state (e.g. "pii_detected", "secret_detected").

        Returns:
            RiskClassification with recognized=True if known, or
            recognized=False if the combination is unknown.
        """
        return self._risks.get((dimension, state), _UNKNOWN)

    def recognizes(self, dimension: str, state: str) -> bool:
        """Check if a (dimension, state) combination is recognized.

        Args:
            dimension: The finding dimension.
            state: The finding state.

        Returns:
            True if recognized, False if unknown.
        """
        return (dimension, state) in self._risks

    @property
    def known_count(self) -> int:
        """Number of recognized (dimension, state) combinations."""
        return len(self._risks)
