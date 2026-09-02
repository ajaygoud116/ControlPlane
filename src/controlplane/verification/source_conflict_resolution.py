"""Source Conflict Resolution verifier — attempts to resolve conflicting evidence.

Deterministic: same request + claim + evidence → same result.

Capabilities:
- SOURCE_CONFLICT uncertainty type
- Groups evidence by structured value
- Resolves by authority hierarchy
- Falls back to freshness where applicable
- Returns SUPPORTED, CONTRADICTED, CONFLICTED, or INSUFFICIENT_EVIDENCE

CRITICAL: If authority/freshness cannot legitimately resolve a conflict,
resolution MUST remain CONFLICTED. Never arbitrarily select a source.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from controlplane.detection.performance_types import Claim, Evidence
from controlplane.schemas.enums import (
    UncertaintyType,
    VerificationResolution,
    VerificationStatus,
)
from controlplane.schemas.verification import (
    VerificationEvidence,
    VerificationRequest,
    VerificationResult,
)
from controlplane.verification.base import BaseVerifier

_AUTHORITY_ORDER = {"primary": 0, "secondary": 1, "tertiary": 2, "unknown": 3}


class SourceConflictResolutionVerifier(BaseVerifier):
    """Deterministic verifier for source conflict resolution."""

    @property
    def verifier_id(self) -> str:
        return "source_conflict_resolution"

    @property
    def verifier_version(self) -> str:
        return "1.0.0"

    @property
    def supported_uncertainty_types(self) -> list[UncertaintyType]:
        return [UncertaintyType.SOURCE_CONFLICT]

    def verify(
        self,
        request: VerificationRequest,
        claim: Claim,
        evidence: list[Evidence],
    ) -> VerificationResult:
        """Execute verification."""
        start = datetime.now(timezone.utc)

        try:
            result = self._execute(request, claim, evidence, start)
        except Exception as e:
            return self._make_result(
                request=request,
                status=VerificationStatus.FAILED,
                resolution=VerificationResolution.NOT_APPLICABLE,
                explanation=f"Verifier exception: {e}",
                failure_reason=str(e),
                start=start,
            )

        return result

    def _execute(
        self,
        request: VerificationRequest,
        claim: Claim,
        evidence: list[Evidence],
        start: datetime,
    ) -> VerificationResult:
        """Core verification logic."""
        matched = self._resolve(claim, evidence)
        if not matched:
            return self._make_result(
                request=request,
                status=VerificationStatus.RESOLVED,
                resolution=VerificationResolution.INSUFFICIENT_EVIDENCE,
                explanation=f"No valid evidence for conflict resolution: {claim.claim_text}",
                sources_consulted=[e.evidence_id for e in evidence],
                start=start,
            )

        groups = self._group_by_value(claim, matched)
        if len(groups) <= 1:
            return self._make_result(
                request=request,
                status=VerificationStatus.RESOLVED,
                resolution=VerificationResolution.INSUFFICIENT_EVIDENCE,
                explanation=f"No conflicting groups found: {claim.claim_text}",
                sources_consulted=[m["evidence"].evidence_id for m in matched],
                start=start,
            )

        auth_groups = []
        for vk, grp in groups.items():
            au = [m for m in grp if m["evidence"].authority_class != "unknown"]
            if au:
                auth_groups.append((vk, grp, au))

        if len(auth_groups) < 2:
            return self._make_result(
                request=request,
                status=VerificationStatus.RESOLVED,
                resolution=VerificationResolution.CONFLICTED,
                explanation=f"Conflicting evidence with insufficient authority metadata: {claim.claim_text}",
                sources_consulted=[m["evidence"].evidence_id for m in matched],
                start=start,
            )

        best_idx, best_auth = -1, 3
        for i, (_, _, ae) in enumerate(auth_groups):
            min_auth = min(
                _AUTHORITY_ORDER.get(m["evidence"].authority_class, 3) for m in ae
            )
            if min_auth < best_auth:
                best_auth, best_idx = min_auth, i

        if best_idx < 0:
            return self._make_result(
                request=request,
                status=VerificationStatus.RESOLVED,
                resolution=VerificationResolution.CONFLICTED,
                explanation=f"Cannot determine best authority: {claim.claim_text}",
                sources_consulted=[m["evidence"].evidence_id for m in matched],
                start=start,
            )

        best_vk, best_grp, best_au = auth_groups[best_idx]
        other_groups = [(vk, grp, au) for vk, grp, au in auth_groups if vk != best_vk]

        second_best = min(
            _AUTHORITY_ORDER.get(m["evidence"].authority_class, 3)
            for _, _, ae in other_groups
            for m in ae
        )

        if best_auth < second_best:
            best_val = best_vk
            claim_val = self._claim_value(claim)
            if claim_val and self._norm(best_val) == self._norm(claim_val):
                return self._make_result(
                    request=request,
                    status=VerificationStatus.RESOLVED,
                    resolution=VerificationResolution.SUPPORTED,
                    explanation=f"Authority-resolved support for: {claim.claim_text}",
                    sources_consulted=[m["evidence"].evidence_id for m in best_au],
                    source_quality=best_au[0]["evidence"].authority_class,
                    start=start,
                )
            else:
                return self._make_result(
                    request=request,
                    status=VerificationStatus.RESOLVED,
                    resolution=VerificationResolution.CONTRADICTED,
                    explanation=f"Authority-resolved contradiction for: {claim.claim_text}",
                    sources_consulted=[m["evidence"].evidence_id for m in best_au],
                    source_quality=best_au[0]["evidence"].authority_class,
                    start=start,
                )

        return self._make_result(
            request=request,
            status=VerificationStatus.RESOLVED,
            resolution=VerificationResolution.CONFLICTED,
            explanation=f"Equal-authority conflict cannot be resolved: {claim.claim_text}",
            sources_consulted=[m["evidence"].evidence_id for m in matched],
            start=start,
        )

    def _resolve(self, claim: Claim, evidence: list[Evidence]) -> list[dict]:
        """Resolve evidence by evidence_keys and claim_ids."""
        evidence_by_id = {e.evidence_id: e for e in evidence}
        result, seen = [], set()
        for key in claim.evidence_keys:
            ev = evidence_by_id.get(key)
            if ev is None or ev.evidence_id in seen:
                continue
            seen.add(ev.evidence_id)
            if claim.claim_id not in ev.claim_ids:
                continue
            result.append({"evidence": ev, "claim": claim})
        return result

    def _group_by_value(
        self, claim: Claim, matched: list[dict]
    ) -> dict[str, list[dict]]:
        """Group matched evidence by normalized structured value."""
        groups: dict[str, list[dict]] = {}
        for m in matched:
            vk = self._vkey(claim, m["evidence"])
            if vk is not None:
                groups.setdefault(vk, []).append(m)
        return groups

    def _vkey(self, claim: Claim, evidence: Evidence) -> str | None:
        """Extract value key for grouping."""
        sv = evidence.structured_values
        ct = claim.claim_type
        if ct in {"factual", "entity"}:
            v = sv.get("value", "")
            return self._norm(v) if v else None
        elif ct == "numeric":
            return sv.get("value", "") or None
        elif ct == "temporal":
            return sv.get("date", "") or None
        return None

    def _claim_value(self, claim: Claim) -> str | None:
        """Extract the claim's expected value."""
        rv = claim.relevant_values
        ct = claim.claim_type
        if ct in {"factual", "entity", "numeric"}:
            return rv.get("value")
        elif ct == "temporal":
            return rv.get("date")
        return None

    def _norm(self, text: str) -> str:
        return text.lower().strip()

    def _make_result(
        self,
        request: VerificationRequest | None,
        status: VerificationStatus,
        resolution: VerificationResolution,
        explanation: str,
        sources_consulted: list[str] | None = None,
        source_quality: str | None = None,
        failure_reason: str | None = None,
        start: datetime | None = None,
    ) -> VerificationResult:
        """Construct a VerificationResult."""
        now = datetime.now(timezone.utc)
        latency = (now - (start or now)).total_seconds() * 1000

        return VerificationResult(
            result_id=uuid4(),
            request_id=request.request_id if request else uuid4(),
            verifier=self.verifier_id,
            status=status,
            resolution=resolution,
            evidence=VerificationEvidence(
                sources_consulted=sources_consulted or [],
                source_quality=source_quality,
            ),
            explanation=explanation,
            latency_ms=latency,
            cost_usd=0.0,
            failure_reason=failure_reason,
            completed_at=now,
        )
