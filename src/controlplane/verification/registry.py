"""Verifier Registry — maps verifier names to capabilities and implementations.

The registry provides:
- Registration of verifiers (name → capability + implementation)
- Lookup by name
- Listing all registered capabilities

The registry does NOT:
- Decide which verifier to use (DECIDE's job)
- Filter by allowed_verifiers (DECIDE's job)
- Interpret Policy or Context
- Maintain state between invocations
"""

from __future__ import annotations

from controlplane.decision.verifier import VerifierCapability
from controlplane.verification.base import BaseVerifier


class VerifierRegistry:
    """Registry of available verifiers.

    Provides lookup by name and listing of all capabilities.
    Does NOT make selection decisions.
    """

    def __init__(self) -> None:
        self._verifiers: dict[str, BaseVerifier] = {}
        self._capabilities: dict[str, VerifierCapability] = {}

    def register(self, verifier: BaseVerifier) -> None:
        """Register a verifier. Last registration wins on duplicate."""
        self._verifiers[verifier.verifier_id] = verifier
        self._capabilities[verifier.verifier_id] = VerifierCapability(
            name=verifier.verifier_id,
            uncertainty_types=verifier.supported_uncertainty_types,
            expected_latency_ms=0.0,
            expected_cost_usd=0.0,
        )

    def get_verifier(self, name: str) -> BaseVerifier | None:
        """Look up a verifier by name. Returns None if not found."""
        return self._verifiers.get(name)

    def get_capability(self, name: str) -> VerifierCapability | None:
        """Look up a verifier's capability by name. Returns None if not found."""
        return self._capabilities.get(name)

    def list_capabilities(self) -> list[VerifierCapability]:
        """List all registered verifier capabilities."""
        return list(self._capabilities.values())

    def list_verifier_ids(self) -> list[str]:
        """List all registered verifier IDs."""
        return list(self._verifiers.keys())

    def __contains__(self, name: str) -> bool:
        return name in self._verifiers

    def __len__(self) -> int:
        return len(self._verifiers)
