"""Verification Runner — orchestrates verifier execution.

The Runner sits between DECIDE and the Verifier. It:
- Validates requests
- Looks up verifiers in the registry
- Performs authorization and capability checks
- Enforces timeouts
- Executes verifiers
- Normalizes results
- Tracks telemetry and provenance

The Runner does NOT:
- Decide ALLOW/BLOCK/ESCALATE
- Interpret VerificationResult as a decision
- Mutate the original Finding
- Select a different verifier if the selected one fails
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from uuid import uuid4

from controlplane.detection.performance_types import Claim, Evidence
from controlplane.schemas.enums import (
    VerificationResolution,
    VerificationStatus,
)
from controlplane.schemas.verification import (
    VerificationRequest,
    VerificationResult,
)
from controlplane.verification.base import BaseVerifier
from controlplane.verification.provenance import VerificationContext
from controlplane.verification.registry import VerifierRegistry

# Valid status + resolution combinations
_VALID_COMBOS: dict[VerificationStatus, set[VerificationResolution]] = {
    VerificationStatus.RESOLVED: {
        VerificationResolution.SUPPORTED,
        VerificationResolution.CONTRADICTED,
        VerificationResolution.CONFLICTED,
        VerificationResolution.INSUFFICIENT_EVIDENCE,
        VerificationResolution.UNVERIFIABLE,
    },
    VerificationStatus.UNRESOLVED: {
        VerificationResolution.INSUFFICIENT_EVIDENCE,
    },
    VerificationStatus.FAILED: {
        VerificationResolution.NOT_APPLICABLE,
    },
    VerificationStatus.TIMEOUT: {
        VerificationResolution.NOT_APPLICABLE,
    },
}


class VerificationRunner:
    """Orchestrates verifier execution with validation and error handling."""

    def __init__(
        self,
        registry: VerifierRegistry,
        allowed_verifiers: list[str] | None = None,
    ) -> None:
        """Initialize the Runner.

        Args:
            registry: Verifier registry for lookup.
            allowed_verifiers: Policy-authorized verifier names. None = all allowed.
        """
        self._registry = registry
        self._allowed_verifiers = allowed_verifiers

    def run(
        self,
        request: VerificationRequest,
        verifier_name: str,
        claim: Claim,
        evidence: list[Evidence],
    ) -> VerificationResult:
        """Execute a verification request.

        Args:
            request: The verification request.
            verifier_name: Name of the verifier to use (from Decision.selected_verifier).
            claim: The claim to verify.
            evidence: Available evidence.

        Returns:
            VerificationResult with valid status+resolution combination.
        """
        start = datetime.now(timezone.utc)

        # 1. Request validation
        validation_error = self._validate_request(request)
        if validation_error is not None:
            return self._failure_result(request, verifier_name, validation_error, start)

        # 2. Verifier lookup
        verifier = self._registry.get_verifier(verifier_name)
        if verifier is None:
            return self._failure_result(
                request, verifier_name, f"Verifier not found: {verifier_name}", start
            )

        # 3. Authorization check
        if self._allowed_verifiers is not None:
            if verifier_name not in self._allowed_verifiers:
                return self._failure_result(
                    request,
                    verifier_name,
                    f"Verifier not authorized: {verifier_name}",
                    start,
                )

        # 4. Capability check
        if request.uncertainty_type not in verifier.supported_uncertainty_types:
            return self._failure_result(
                request,
                verifier_name,
                f"Capability mismatch: {request.uncertainty_type} not in {verifier.supported_uncertainty_types}",
                start,
            )

        # 5. Execute with timeout
        result = self._execute_with_timeout(verifier, request, claim, evidence, start)

        # 6. Validate result
        validation_error = self._validate_result(result)
        if validation_error is not None:
            return self._failure_result(request, verifier_name, validation_error, start)

        # 7. Ensure request_id matches
        if result.request_id != request.request_id:
            return self._failure_result(
                request,
                verifier_name,
                f"Result request_id mismatch: {result.request_id} != {request.request_id}",
                start,
            )

        return result

    def _validate_request(self, request: VerificationRequest) -> str | None:
        """Validate a verification request. Returns error message or None."""
        if not request.request_id:
            return "Missing request_id"
        if not request.interaction_id:
            return "Missing interaction_id"
        if not request.decision_id:
            return "Missing decision_id"
        if not request.finding_id:
            return "Missing finding_id"
        if not request.specific_question:
            return "Missing specific_question"
        if request.timeout_ms <= 0:
            return "timeout_ms must be positive"
        if request.max_cost_usd < 0:
            return "max_cost_usd must be non-negative"
        return None

    def _validate_result(self, result: VerificationResult) -> str | None:
        """Validate a verification result. Returns error message or None."""
        valid = _VALID_COMBOS.get(result.status)
        if valid is None:
            return f"Invalid status: {result.status}"
        if result.resolution not in valid:
            return f"Invalid combination: {result.status} + {result.resolution}"
        return None

    def _execute_with_timeout(
        self,
        verifier: BaseVerifier,
        request: VerificationRequest,
        claim: Claim,
        evidence: list[Evidence],
        start: datetime,
    ) -> VerificationResult:
        """Execute verifier with timeout enforcement."""
        result_holder: list[VerificationResult | None] = [None]
        exception_holder: list[Exception | None] = [None]

        def run_verifier() -> None:
            try:
                result_holder[0] = verifier.verify(request, claim, evidence)
            except Exception as e:
                exception_holder[0] = e

        thread = threading.Thread(target=run_verifier, daemon=True)
        thread.start()
        thread.join(timeout=request.timeout_ms / 1000.0)

        if thread.is_alive():
            return self._failure_result(
                request,
                verifier.verifier_id,
                "Verifier timeout",
                start,
                status=VerificationStatus.TIMEOUT,
            )

        if exception_holder[0] is not None:
            return self._failure_result(
                request,
                verifier.verifier_id,
                f"Verifier exception: {exception_holder[0]}",
                start,
            )

        if result_holder[0] is None:
            return self._failure_result(
                request,
                verifier.verifier_id,
                "Verifier returned None",
                start,
            )

        return result_holder[0]

    def _failure_result(
        self,
        request: VerificationRequest,
        verifier_name: str,
        reason: str,
        start: datetime,
        status: VerificationStatus = VerificationStatus.FAILED,
    ) -> VerificationResult:
        """Construct a failure result."""
        now = datetime.now(timezone.utc)
        latency = (now - start).total_seconds() * 1000

        return VerificationResult(
            result_id=uuid4(),
            request_id=request.request_id,
            verifier=verifier_name,
            status=status,
            resolution=VerificationResolution.NOT_APPLICABLE,
            explanation=reason,
            latency_ms=latency,
            cost_usd=0.0,
            failure_reason=reason,
            completed_at=now,
        )
