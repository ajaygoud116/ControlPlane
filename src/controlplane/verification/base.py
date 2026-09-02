"""Verifier abstraction — common interface for all V1 verifiers.

The verifier receives a VerificationRequest, Claim, and Evidence.
It returns a VerificationResult.

The verifier MUST NOT know about Policy, Context, DECIDE, or intervention.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from controlplane.detection.performance_types import Claim, Evidence
from controlplane.schemas.enums import UncertaintyType
from controlplane.schemas.verification import VerificationRequest, VerificationResult


class BaseVerifier(ABC):
    """Abstract base class for all verifiers.

    Each verifier must declare:
    - verifier_id: stable unique identifier
    - verifier_version: version string
    - supported_uncertainty_types: list of UncertaintyType it can resolve

    Each verifier must implement:
    - verify(request, claim, evidence) -> VerificationResult
    """

    @property
    @abstractmethod
    def verifier_id(self) -> str:
        """Stable unique identifier for this verifier."""

    @property
    @abstractmethod
    def verifier_version(self) -> str:
        """Version of this verifier."""

    @property
    @abstractmethod
    def supported_uncertainty_types(self) -> list[UncertaintyType]:
        """Uncertainty types this verifier can resolve."""

    @abstractmethod
    def verify(
        self,
        request: VerificationRequest,
        claim: Claim,
        evidence: list[Evidence],
    ) -> VerificationResult:
        """Execute verification and return a result.

        Args:
            request: The verification request.
            claim: The specific claim being verified.
            evidence: Structured evidence available for comparison.

        Returns:
            VerificationResult with valid status+resolution combination.

        Raises:
            Exceptions must NOT escape. The Runner catches them.
        """
