"""Source Retrieval verifier — verifies factual claims against structured evidence.

Deterministic: same request + claim + evidence → same result.

Capabilities:
- FACTUAL_SUPPORT uncertainty type
- Filters evidence by claim evidence_keys and claim_ids
- Compares structured_values against relevant_values
- Considers authority hierarchy
- Returns SUPPORTED, CONTRADICTED, INSUFFICIENT_EVIDENCE, UNVERIFIABLE, or CONFLICTED
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

_ENTITY_ALIASES: dict[str, str] = {
    "nyc": "new york city",
    "new york city": "new york city",
    "new york": "new york city",
    "usa": "united states",
    "united states": "united states",
    "us": "united states",
    "uk": "united kingdom",
    "united kingdom": "united kingdom",
}


class SourceRetrievalVerifier(BaseVerifier):
    """Deterministic verifier for factual support claims."""

    @property
    def verifier_id(self) -> str:
        return "source_retrieval"

    @property
    def verifier_version(self) -> str:
        return "1.0.0"

    @property
    def supported_uncertainty_types(self) -> list[UncertaintyType]:
        return [UncertaintyType.FACTUAL_SUPPORT]

    def verify(
        self,
        request: VerificationRequest,
        claim: Claim,
        evidence: list[Evidence],
    ) -> VerificationResult:
        """Execute verification."""
        now = datetime.now(timezone.utc)
        start = now

        try:
            result = self._execute(request, claim, evidence)
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
    ) -> VerificationResult:
        """Core verification logic."""
        start = datetime.now(timezone.utc)

        if claim.verifiability == "unverifiable":
            return self._make_result(
                request=request,
                status=VerificationStatus.RESOLVED,
                resolution=VerificationResolution.UNVERIFIABLE,
                explanation=f"Claim explicitly marked unverifiable: {claim.claim_text}",
                start=start,
            )

        if not claim.relevant_values:
            return self._make_result(
                request=request,
                status=VerificationStatus.RESOLVED,
                resolution=VerificationResolution.UNVERIFIABLE,
                explanation="No structured values for comparison",
                start=start,
            )

        matched = self._resolve(claim, evidence)
        if not matched:
            return self._make_result(
                request=request,
                status=VerificationStatus.RESOLVED,
                resolution=VerificationResolution.INSUFFICIENT_EVIDENCE,
                explanation=f"No valid evidence for: {claim.claim_text}",
                sources_consulted=[e.evidence_id for e in evidence],
                start=start,
            )

        conflict = self._check_conflict(claim, matched)
        if conflict is not None:
            return conflict

        effective = self._filter_authority(matched)
        return self._compare(claim, effective, request, start)

    def _resolve(
        self, claim: Claim, evidence: list[Evidence]
    ) -> list[dict]:
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

    def _check_conflict(
        self, claim: Claim, matched: list[dict]
    ) -> VerificationResult | None:
        """Check for unresolvable conflicts. Returns result if conflict found."""
        if len(matched) < 2:
            return None

        groups: dict[str, list] = {}
        for m in matched:
            vk = self._vkey(claim, m["evidence"])
            if vk is not None:
                groups.setdefault(vk, []).append(m)

        if len(groups) <= 1:
            return None

        auth_groups = []
        for vk, grp in groups.items():
            au = [m for m in grp if m["evidence"].authority_class != "unknown"]
            if au:
                auth_groups.append((vk, au))

        if len(auth_groups) < 2:
            return None

        best_idx, best_auth = -1, 3
        for i, (_, ae) in enumerate(auth_groups):
            min_auth = min(
                _AUTHORITY_ORDER.get(m["evidence"].authority_class, 3) for m in ae
            )
            if min_auth < best_auth:
                best_auth, best_idx = min_auth, i

        if best_idx < 0:
            return None

        best_vk = auth_groups[best_idx][0]
        other_vks = [vk for vk, _ in auth_groups if vk != best_vk]
        if not other_vks:
            return None

        second_best = min(
            _AUTHORITY_ORDER.get(m["evidence"].authority_class, 3)
            for vk, ae in auth_groups
            if vk != best_vk
            for m in ae
        )

        if best_auth < second_best:
            return None

        start = datetime.now(timezone.utc)
        sources = [m["evidence"].evidence_id for m in matched]
        return self._make_result(
            request=None,
            status=VerificationStatus.RESOLVED,
            resolution=VerificationResolution.CONFLICTED,
            explanation=f"Conflicting evidence for: {claim.claim_text}",
            sources_consulted=sources,
            start=start,
        )

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

    def _filter_authority(self, matched: list[dict]) -> list[dict]:
        """Filter to authoritative sources if any exist."""
        if any(m["evidence"].authority_class != "unknown" for m in matched):
            return [m for m in matched if m["evidence"].authority_class != "unknown"]
        return matched

    def _scope_ok(self, claim: Claim, evidence: Evidence) -> bool:
        """Check if evidence matches claim scope."""
        cv = claim.relevant_values
        sv = evidence.structured_values
        ct = claim.claim_type
        if ct in {"factual", "entity"}:
            ce, ee = cv.get("entity", ""), sv.get("entity", "")
            ca, ea = cv.get("attribute", ""), sv.get("attribute", "")
            if ce and ee and self._ne(ce) != self._ne(ee):
                return False
            if ca and ea and self._na(ca) != self._na(ea):
                return False
            return True
        elif ct == "numeric":
            cm, em = cv.get("metric", ""), sv.get("metric", "")
            cp, ep = cv.get("period", ""), sv.get("period", "")
            if cm and em and self._na(cm) != self._na(em):
                return False
            if cp and ep and self._na(cp) != self._na(ep):
                return False
            return True
        elif ct == "temporal":
            ce, ee = cv.get("entity", ""), sv.get("entity", "")
            ca, ea = cv.get("attribute", ""), sv.get("attribute", "")
            if ce and ee and self._ne(ce) != self._ne(ee):
                return False
            if ca and ea and self._na(ca) != self._na(ea):
                return False
            return True
        return False

    def _compare(
        self,
        claim: Claim,
        matched: list[dict],
        request: VerificationRequest,
        start: datetime,
    ) -> VerificationResult:
        """Compare claim against matched evidence."""
        scoped = [m for m in matched if self._scope_ok(claim, m["evidence"])]
        sources = [m["evidence"].evidence_id for m in matched]

        if not scoped:
            return self._make_result(
                request=request,
                status=VerificationStatus.RESOLVED,
                resolution=VerificationResolution.INSUFFICIENT_EVIDENCE,
                explanation=f"Scope mismatch: {claim.claim_text}",
                sources_consulted=sources,
                start=start,
            )

        if claim.claim_type == "factual":
            return self._cmp_factual(claim, scoped, request, sources, start)
        elif claim.claim_type == "numeric":
            return self._cmp_numeric(claim, scoped, request, sources, start)
        elif claim.claim_type == "temporal":
            return self._cmp_temporal(claim, scoped, request, sources, start)
        elif claim.claim_type == "entity":
            return self._cmp_entity(claim, scoped, request, sources, start)

        return self._make_result(
            request=request,
            status=VerificationStatus.RESOLVED,
            resolution=VerificationResolution.UNVERIFIABLE,
            explanation=f"Unsupported claim type: {claim.claim_type}",
            sources_consulted=sources,
            start=start,
        )

    def _cmp_factual(
        self,
        claim: Claim,
        scoped: list[dict],
        request: VerificationRequest,
        sources: list[str],
        start: datetime,
    ) -> VerificationResult:
        """Compare factual claims."""
        cv = claim.relevant_values.get("value", "")
        if not cv:
            return self._make_result(
                request=request,
                status=VerificationStatus.RESOLVED,
                resolution=VerificationResolution.UNVERIFIABLE,
                explanation="Missing factual value",
                sources_consulted=sources,
                start=start,
            )

        cn = self._norm(cv)
        for m in scoped:
            ev = m["evidence"]
            ev_val = self._norm(ev.structured_values.get("value", ""))
            if ev_val and cn == ev_val:
                return self._make_result(
                    request=request,
                    status=VerificationStatus.RESOLVED,
                    resolution=VerificationResolution.SUPPORTED,
                    explanation=f"Supported: {claim.claim_text}",
                    sources_consulted=[x["evidence"].evidence_id for x in scoped],
                    source_quality=ev.authority_class,
                    start=start,
                )

        for m in scoped:
            ev = m["evidence"]
            if ev.authority_class in {"primary", "secondary"}:
                return self._make_result(
                    request=request,
                    status=VerificationStatus.RESOLVED,
                    resolution=VerificationResolution.CONTRADICTED,
                    explanation=f"Contradicted: {claim.claim_text}",
                    sources_consulted=[x["evidence"].evidence_id for x in scoped],
                    source_quality=ev.authority_class,
                    start=start,
                )

        return self._make_result(
            request=request,
            status=VerificationStatus.RESOLVED,
            resolution=VerificationResolution.INSUFFICIENT_EVIDENCE,
            explanation=f"Insufficient: {claim.claim_text}",
            sources_consulted=sources,
            start=start,
        )

    def _cmp_numeric(
        self,
        claim: Claim,
        scoped: list[dict],
        request: VerificationRequest,
        sources: list[str],
        start: datetime,
    ) -> VerificationResult:
        """Compare numeric claims."""
        cvs = claim.relevant_values.get("value", "")
        if not cvs:
            return self._make_result(
                request=request,
                status=VerificationStatus.RESOLVED,
                resolution=VerificationResolution.UNVERIFIABLE,
                explanation="Missing numeric value",
                sources_consulted=sources,
                start=start,
            )

        try:
            cv = float(cvs)
        except (ValueError, TypeError):
            return self._make_result(
                request=request,
                status=VerificationStatus.RESOLVED,
                resolution=VerificationResolution.UNVERIFIABLE,
                explanation=f"Cannot parse numeric value: {cvs}",
                sources_consulted=sources,
                start=start,
            )

        for m in scoped:
            ev = m["evidence"]
            evs = ev.structured_values.get("value", "")
            try:
                ev_val = float(evs)
            except (ValueError, TypeError):
                continue
            if abs(cv - ev_val) <= 0.01:
                return self._make_result(
                    request=request,
                    status=VerificationStatus.RESOLVED,
                    resolution=VerificationResolution.SUPPORTED,
                    explanation=f"Supported: {claim.claim_text}",
                    sources_consulted=[x["evidence"].evidence_id for x in scoped],
                    source_quality=ev.authority_class,
                    start=start,
                )

        for m in scoped:
            ev = m["evidence"]
            if ev.authority_class in {"primary", "secondary"}:
                return self._make_result(
                    request=request,
                    status=VerificationStatus.RESOLVED,
                    resolution=VerificationResolution.CONTRADICTED,
                    explanation=f"Contradicted: {claim.claim_text}",
                    sources_consulted=[x["evidence"].evidence_id for x in scoped],
                    source_quality=ev.authority_class,
                    start=start,
                )

        return self._make_result(
            request=request,
            status=VerificationStatus.RESOLVED,
            resolution=VerificationResolution.INSUFFICIENT_EVIDENCE,
            explanation=f"Insufficient: {claim.claim_text}",
            sources_consulted=sources,
            start=start,
        )

    def _cmp_temporal(
        self,
        claim: Claim,
        scoped: list[dict],
        request: VerificationRequest,
        sources: list[str],
        start: datetime,
    ) -> VerificationResult:
        """Compare temporal claims."""
        cd = claim.relevant_values.get("date", "")
        if not cd:
            return self._make_result(
                request=request,
                status=VerificationStatus.RESOLVED,
                resolution=VerificationResolution.UNVERIFIABLE,
                explanation="Missing date",
                sources_consulted=sources,
                start=start,
            )

        for m in scoped:
            ev = m["evidence"]
            ev_date = ev.structured_values.get("date", "")
            if ev_date and cd == ev_date:
                return self._make_result(
                    request=request,
                    status=VerificationStatus.RESOLVED,
                    resolution=VerificationResolution.SUPPORTED,
                    explanation=f"Supported: {claim.claim_text}",
                    sources_consulted=[x["evidence"].evidence_id for x in scoped],
                    source_quality=ev.authority_class,
                    start=start,
                )

        for m in scoped:
            ev = m["evidence"]
            if ev.authority_class in {"primary", "secondary"}:
                return self._make_result(
                    request=request,
                    status=VerificationStatus.RESOLVED,
                    resolution=VerificationResolution.CONTRADICTED,
                    explanation=f"Contradicted: {claim.claim_text}",
                    sources_consulted=[x["evidence"].evidence_id for x in scoped],
                    source_quality=ev.authority_class,
                    start=start,
                )

        return self._make_result(
            request=request,
            status=VerificationStatus.RESOLVED,
            resolution=VerificationResolution.INSUFFICIENT_EVIDENCE,
            explanation=f"Insufficient: {claim.claim_text}",
            sources_consulted=sources,
            start=start,
        )

    def _cmp_entity(
        self,
        claim: Claim,
        scoped: list[dict],
        request: VerificationRequest,
        sources: list[str],
        start: datetime,
    ) -> VerificationResult:
        """Compare entity claims."""
        cv = claim.relevant_values.get("value", "")
        if not cv:
            return self._make_result(
                request=request,
                status=VerificationStatus.RESOLVED,
                resolution=VerificationResolution.UNVERIFIABLE,
                explanation="Missing entity value",
                sources_consulted=sources,
                start=start,
            )

        cn = self._norm(cv)
        for m in scoped:
            ev = m["evidence"]
            ev_val = self._norm(ev.structured_values.get("value", ""))
            if ev_val and cn == ev_val:
                return self._make_result(
                    request=request,
                    status=VerificationStatus.RESOLVED,
                    resolution=VerificationResolution.SUPPORTED,
                    explanation=f"Supported: {claim.claim_text}",
                    sources_consulted=[x["evidence"].evidence_id for x in scoped],
                    source_quality=ev.authority_class,
                    start=start,
                )

        for m in scoped:
            ev = m["evidence"]
            if ev.authority_class in {"primary", "secondary"}:
                return self._make_result(
                    request=request,
                    status=VerificationStatus.RESOLVED,
                    resolution=VerificationResolution.CONTRADICTED,
                    explanation=f"Contradicted: {claim.claim_text}",
                    sources_consulted=[x["evidence"].evidence_id for x in scoped],
                    source_quality=ev.authority_class,
                    start=start,
                )

        return self._make_result(
            request=request,
            status=VerificationStatus.RESOLVED,
            resolution=VerificationResolution.INSUFFICIENT_EVIDENCE,
            explanation=f"Insufficient: {claim.claim_text}",
            sources_consulted=sources,
            start=start,
        )

    def _norm(self, text: str) -> str:
        return text.lower().strip()

    def _ne(self, text: str) -> str:
        low = text.lower().strip()
        return _ENTITY_ALIASES.get(low, low)

    def _na(self, text: str) -> str:
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
