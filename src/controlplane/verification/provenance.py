"""Verification Context — runtime provenance tracking for the verification layer.

This is NOT a frozen schema. It is a runtime component that maintains
the mapping from finding_id → (Claim, Evidence) required by verifiers.

The Finding schema does not store the full Claim/Evidence dataclass data.
The context is populated during detection and used during verification.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from controlplane.detection.performance_types import Claim, Evidence


@dataclass
class VerificationContext:
    """Runtime context for verification provenance.

    Maps finding_id → (Claim, list[Evidence]) for use by the Runner.
    Populated during detection when Claim and Evidence are in scope.
    """

    _entries: dict[UUID, tuple[Claim, list[Evidence]]] = field(default_factory=dict)

    def add(self, finding_id: UUID, claim: Claim, evidence: list[Evidence]) -> None:
        """Register a finding's claim and evidence for later verification."""
        self._entries[finding_id] = (claim, list(evidence))

    def get(self, finding_id: UUID) -> tuple[Claim, list[Evidence]] | None:
        """Retrieve claim and evidence for a finding. Returns None if not found."""
        return self._entries.get(finding_id)

    def has(self, finding_id: UUID) -> bool:
        """Check if a finding has registered context."""
        return finding_id in self._entries

    def finding_ids(self) -> list[UUID]:
        """List all registered finding IDs."""
        return list(self._entries.keys())

    def __len__(self) -> int:
        return len(self._entries)

    def __contains__(self, finding_id: UUID) -> bool:
        return finding_id in self._entries
