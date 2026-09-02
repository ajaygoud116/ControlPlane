"""Evidence-Grounded Performance Detector.

V1: Structured claims + structured evidence + deterministic comparison.
One Finding per Claim. No LLM. No embeddings. No extraction.

Evidence lookup:
    Claim.evidence_keys -> Evidence.evidence_id (primary)
    Claim.claim_id in Evidence.claim_ids (reverse provenance)

Comparison uses Evidence.structured_values, NOT Evidence.content.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from uuid import UUID, uuid4

from controlplane.detection.base import BaseDetector
from controlplane.detection.performance_types import Claim, Evidence
from controlplane.schemas.enums import FindingDimension, ObservationType, PerformanceState
from controlplane.schemas.finding import Finding, FindingAmbiguity, FindingEvidence, FindingMeasurement
from controlplane.schemas.observation import Observation


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


class PerformanceDetector(BaseDetector):
    detector_id = "performance_evidence"
    detector_version = "1.0.0"

    def __init__(self, claims=None, evidence=None, numeric_tolerance=0.01):
        self._claims = list(claims or [])
        self._evidence = list(evidence or [])
        self._numeric_tolerance = numeric_tolerance
        self._evidence_by_id: dict[str, Evidence] = {}
        for e in self._evidence:
            self._evidence_by_id[e.evidence_id] = e

    def detect(self, observations):
        return [self._evaluate_claim(c) for c in self._claims]

    def _evaluate_claim(self, claim):
        t = datetime.now(timezone.utc)
        if claim.verifiability == "unverifiable":
            return self._mk(claim, PerformanceState.UNVERIFIABLE,
                f"Claim explicitly marked unverifiable: {claim.claim_text}", t,
                ambiguity_reasons=["Claim explicitly marked unverifiable"])
        if claim.claim_type not in {"factual", "numeric", "temporal", "entity"}:
            return self._mk(claim, PerformanceState.UNVERIFIABLE,
                f"Unsupported claim type: {claim.claim_type}", t,
                ambiguity_reasons=[f"Type {claim.claim_type} unsupported"])
        if not claim.relevant_values:
            return self._mk(claim, PerformanceState.UNVERIFIABLE,
                "No structured values for comparison", t,
                ambiguity_reasons=["Missing relevant_values"])
        matched = self._resolve(claim)
        if not matched:
            return self._mk(claim, PerformanceState.INSUFFICIENT_EVIDENCE,
                f"No valid evidence for: {claim.claim_text}", t,
                evidence_gaps=[f"Keys: {claim.evidence_keys}"])
        conflict = self._conflict(claim, matched)
        if conflict is not None:
            return conflict
        effective = self._filter_auth(matched)
        return self._compare(claim, effective)

    def _resolve(self, claim):
        result, seen = [], set()
        for key in claim.evidence_keys:
            ev = self._evidence_by_id.get(key)
            if ev is None or ev.evidence_id in seen:
                continue
            seen.add(ev.evidence_id)
            if claim.claim_id not in ev.claim_ids:
                continue
            result.append({"evidence": ev, "claim": claim})
        return result

    def _conflict(self, claim, matched):
        if len(matched) < 2:
            return None
        groups: dict[str, list] = {}
        for m in matched:
            vk = self._vkey(claim, m["evidence"])
            if vk is not None:
                groups.setdefault(vk, []).append(m)
        if len(groups) <= 1:
            return None
        ag = []
        for vk, grp in groups.items():
            au = [m for m in grp if m["evidence"].authority_class != "unknown"]
            if au:
                ag.append((vk, au))
        if len(ag) < 2:
            return None
        bi, ba = -1, 3
        for i, (_, ae) in enumerate(ag):
            ma = min(_AUTHORITY_ORDER.get(m["evidence"].authority_class, 3) for m in ae)
            if ma < ba:
                ba, bi = ma, i
        if bi < 0:
            return None
        bv = ag[bi][0]
        oth = [vk for vk, _ in ag if vk != bv]
        if not oth:
            return None
        second_best = min(
            _AUTHORITY_ORDER.get(m["evidence"].authority_class, 3)
            for vk, ae in ag if vk != bv
            for m in ae
        )
        if ba < second_best:
            return None
        st = datetime.now(timezone.utc)
        return self._mk(claim, PerformanceState.CONFLICTED,
            f"Conflicting evidence for: {claim.claim_text}", st,
            ambiguity_reasons=[f"{len(matched)} conflicting sources"],
            evidence_source_ids=[m["evidence"].evidence_id for m in matched],
            conflict_count=len(matched))

    def _vkey(self, claim, evidence):
        sv = evidence.structured_values
        if claim.claim_type in {"factual", "entity"}:
            v = sv.get("value", "")
            return self._norm(v) if v else None
        elif claim.claim_type == "numeric":
            return sv.get("value", "") or None
        elif claim.claim_type == "temporal":
            return sv.get("date", "") or None
        return None

    def _filter_auth(self, matched):
        if any(m["evidence"].authority_class != "unknown" for m in matched):
            return [m for m in matched if m["evidence"].authority_class != "unknown"]
        return matched

    def _ne(self, text):
        low = text.lower().strip()
        return _ENTITY_ALIASES.get(low, low)

    def _na(self, text):
        return text.lower().strip()

    def _norm(self, text):
        return text.lower().strip()

    def _scope_ok(self, claim, evidence):
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

    def _compare(self, claim, matched):
        st = datetime.now(timezone.utc)
        scoped = [m for m in matched if self._scope_ok(claim, m["evidence"])]
        if not scoped:
            return self._mk(claim, PerformanceState.INSUFFICIENT_EVIDENCE,
                f"Scope mismatch: {claim.claim_text}", st,
                evidence_source_ids=[m["evidence"].evidence_id for m in matched],
                ambiguity_reasons=["No evidence matches claim scope"])
        if claim.claim_type == "factual":
            return self._cmp_factual(claim, scoped, st)
        elif claim.claim_type == "numeric":
            return self._cmp_numeric(claim, scoped, st)
        elif claim.claim_type == "temporal":
            return self._cmp_temporal(claim, scoped, st)
        elif claim.claim_type == "entity":
            return self._cmp_entity(claim, scoped, st)
        return self._mk(claim, PerformanceState.UNVERIFIABLE,
            f"Unsupported: {claim.claim_type}", st,
            ambiguity_reasons=[f"Type {claim.claim_type} unsupported"])

    def _cmp_factual(self, claim, scoped, st):
        cv = claim.relevant_values.get("value", "")
        if not cv:
            return self._mk(claim, PerformanceState.UNVERIFIABLE,
                "Missing factual value", st, ambiguity_reasons=["Missing value"])
        cn = self._norm(cv)
        for m in scoped:
            ev = m["evidence"]
            ev_val = self._norm(ev.structured_values.get("value", ""))
            if ev_val and cn == ev_val:
                return self._mk(claim, PerformanceState.SUPPORTED,
                    f"Supported: {claim.claim_text}", st,
                    evidence_source_ids=[x["evidence"].evidence_id for x in scoped],
                    source_quality=ev.authority_class)
        for m in scoped:
            ev = m["evidence"]
            if ev.authority_class in {"primary", "secondary"}:
                return self._mk(claim, PerformanceState.CONTRADICTED,
                    f"Contradicted: {claim.claim_text}", st,
                    evidence_source_ids=[x["evidence"].evidence_id for x in scoped],
                    counter_evidence=[x["evidence"].structured_values.get("value", "") for x in scoped],
                    source_quality=ev.authority_class)
        return self._mk(claim, PerformanceState.INSUFFICIENT_EVIDENCE,
            f"Insufficient: {claim.claim_text}", st,
            evidence_source_ids=[x["evidence"].evidence_id for x in scoped],
            evidence_gaps=[f"Could not verify: {cv}"])

    def _cmp_numeric(self, claim, scoped, st):
        cvs = claim.relevant_values.get("value", "")
        if not cvs:
            return self._mk(claim, PerformanceState.UNVERIFIABLE,
                "Missing numeric value", st, ambiguity_reasons=["Missing value"])
        try:
            cv = float(cvs)
        except (ValueError, TypeError):
            return self._mk(claim, PerformanceState.UNVERIFIABLE,
                f"Cannot parse: {cvs}", st, ambiguity_reasons=[f"Invalid: {cvs}"])
        direction = claim.relevant_values.get("direction", "")
        for m in scoped:
            ev = m["evidence"]
            evs = ev.structured_values.get("value", "")
            try:
                ev_val = float(evs)
            except (ValueError, TypeError):
                continue
            if abs(cv - ev_val) <= self._numeric_tolerance:
                return self._mk(claim, PerformanceState.SUPPORTED,
                    f"Supported: {claim.claim_text}", st,
                    evidence_source_ids=[x["evidence"].evidence_id for x in scoped],
                    source_quality=ev.authority_class)
            if direction:
                return self._mk(claim, PerformanceState.INSUFFICIENT_EVIDENCE,
                    f"Directional claim vs flat value: {claim.claim_text}", st,
                    evidence_source_ids=[x["evidence"].evidence_id for x in scoped],
                    ambiguity_reasons=["Directional claim vs flat value"])
            if ev.authority_class in {"primary", "secondary"}:
                return self._mk(claim, PerformanceState.CONTRADICTED,
                    f"Contradicted: {claim.claim_text}", st,
                    evidence_source_ids=[x["evidence"].evidence_id for x in scoped],
                    counter_evidence=[x["evidence"].structured_values.get("value", "") for x in scoped],
                    source_quality=ev.authority_class)
        return self._mk(claim, PerformanceState.INSUFFICIENT_EVIDENCE,
            f"Insufficient: {claim.claim_text}", st,
            evidence_source_ids=[x["evidence"].evidence_id for x in scoped],
            evidence_gaps=[f"Could not verify: {cvs}"])

    def _cmp_temporal(self, claim, scoped, st):
        cd = claim.relevant_values.get("date", "")
        if not cd:
            return self._mk(claim, PerformanceState.UNVERIFIABLE,
                "Missing date", st, ambiguity_reasons=["Missing date"])
        for m in scoped:
            ev = m["evidence"]
            ev_date = ev.structured_values.get("date", "")
            if ev_date and cd == ev_date:
                return self._mk(claim, PerformanceState.SUPPORTED,
                    f"Supported: {claim.claim_text}", st,
                    evidence_source_ids=[x["evidence"].evidence_id for x in scoped],
                    source_quality=ev.authority_class)
        for m in scoped:
            ev = m["evidence"]
            if ev.authority_class in {"primary", "secondary"}:
                return self._mk(claim, PerformanceState.CONTRADICTED,
                    f"Contradicted: {claim.claim_text}", st,
                    evidence_source_ids=[x["evidence"].evidence_id for x in scoped],
                    counter_evidence=[x["evidence"].structured_values.get("date", "") for x in scoped],
                    source_quality=ev.authority_class)
        return self._mk(claim, PerformanceState.INSUFFICIENT_EVIDENCE,
            f"Insufficient: {claim.claim_text}", st,
            evidence_source_ids=[x["evidence"].evidence_id for x in scoped],
            evidence_gaps=[f"Could not verify date: {cd}"])

    def _cmp_entity(self, claim, scoped, st):
        cv = claim.relevant_values.get("value", "")
        if not cv:
            return self._mk(claim, PerformanceState.UNVERIFIABLE,
                "Missing entity value", st, ambiguity_reasons=["Missing value"])
        cn = self._norm(cv)
        for m in scoped:
            ev = m["evidence"]
            ev_val = self._norm(ev.structured_values.get("value", ""))
            if ev_val and cn == ev_val:
                return self._mk(claim, PerformanceState.SUPPORTED,
                    f"Supported: {claim.claim_text}", st,
                    evidence_source_ids=[x["evidence"].evidence_id for x in scoped],
                    source_quality=ev.authority_class)
        for m in scoped:
            ev = m["evidence"]
            if ev.authority_class in {"primary", "secondary"}:
                return self._mk(claim, PerformanceState.CONTRADICTED,
                    f"Contradicted: {claim.claim_text}", st,
                    evidence_source_ids=[x["evidence"].evidence_id for x in scoped],
                    counter_evidence=[x["evidence"].structured_values.get("value", "") for x in scoped],
                    source_quality=ev.authority_class)
        return self._mk(claim, PerformanceState.INSUFFICIENT_EVIDENCE,
            f"Insufficient: {claim.claim_text}", st,
            evidence_source_ids=[x["evidence"].evidence_id for x in scoped],
            evidence_gaps=[f"Could not verify: {cv}"])

    def _norm(self, text):
        return text.lower().strip()

    def _mk(self, claim, state, explanation, start_time,
            evidence_source_ids=None, counter_evidence=None,
            source_quality=None, ambiguity_reasons=None,
            evidence_gaps=None, conflict_count=0):
        end = datetime.now(timezone.utc)
        latency = (end - start_time).total_seconds() * 1000
        return Finding(
            finding_id=uuid4(),
            interaction_id=claim.interaction_id,
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            dimension=FindingDimension.PERFORMANCE,
            finding_type="claim_evidence",
            state=state,
            observation_ids=[claim.response_observation_id],
            evidence=FindingEvidence(
                claim_text=claim.claim_text,
                source_ids=evidence_source_ids or [],
                source_quality=source_quality,
                counter_evidence=counter_evidence or [],
            ),
            measurement=FindingMeasurement(latency_ms=latency, estimated_cost_usd=0.0),
            ambiguity=FindingAmbiguity(
                reasons=ambiguity_reasons or [],
                conflicting_sources=conflict_count,
                evidence_gaps=evidence_gaps or [],
            ),
            explanation=explanation,
            detected_at=end,
            latency_ms=latency,
            cost_usd=0.0,
        )
