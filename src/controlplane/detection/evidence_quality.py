"""EvidenceQualityScorer — structured evidence quality assessment.

V2-12: Explicitly models the quality of available evidence BEFORE verification.

CRITICAL DISTINCTION:
    EvidenceQualityAssessment answers:
        "How strong is the evidence available for evaluating this claim?"

    It does NOT answer:
        "Is the claim true?"

    SOURCE AUTHORITY ≠ CLAIM RELEVANCE — both are represented independently.

Architecture:

    Claim + Evidence[] + RetrievalStatus
        ↓
    EvidenceQualityScorer.score()
        ↓
    EvidenceQualityAssessment
        ↓
    ClaimVerifier (receives quality context, does NOT let quality produce truth)

The scorer does NOT:
- Determine truth
- Make policy decisions
- Modify ClaimVerifier verdicts
- Introduce LLMs
- Access the internet

The scorer DOES:
- Assess authority of sources
- Assess relevance of evidence to claim
- Assess provenance completeness
- Assess freshness (contextual)
- Assess corroboration across independent sources
- Assess internal consistency
- Preserve retrieval failure semantics
- Operate deterministically
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

from controlplane.detection.evidence_retriever import (
    AuthorityLevel,
    RetrievedEvidence,
    RetrievalStatus,
)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceQualityAssessment:
    """Structured assessment of evidence quality for a specific claim.

    Attributes:
        overall_quality: Aggregate quality label ('high', 'moderate', 'low', 'none').
        authority_score: Strength of source authority (0.0-1.0).
        relevance_score: How relevant evidence is to the claim (0.0-1.0).
        provenance_score: Completeness of source provenance (0.0-1.0).
        freshness_score: How fresh evidence is relative to claim type (0.0-1.0).
        corroboration_score: Independent source corroboration (0.0-1.0).
        consistency_score: Agreement among authoritative sources (0.0-1.0).
        evidence_count: Number of evidence items.
        primary_source_count: Number of primary sources.
        independent_source_count: Number of independent sources (deduplicated).
        limitations: Specific limitations of the evidence.
        rationale: Human-readable explanation of the quality assessment.
    """

    overall_quality: str
    authority_score: float
    relevance_score: float
    provenance_score: float
    freshness_score: float
    corroboration_score: float
    consistency_score: float
    evidence_count: int
    primary_source_count: int
    independent_source_count: int
    limitations: list[str] = field(default_factory=list)
    rationale: str = ""


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class EvidenceQualityScorer(Protocol):
    """Protocol for evidence quality scoring strategies."""

    def score(
        self,
        subject: str,
        predicate: str,
        evidence: list[RetrievedEvidence],
        retrieval_status: RetrievalStatus,
        claim_type: str = "factual",
    ) -> EvidenceQualityAssessment:
        """Score the quality of evidence for a claim.

        Args:
            subject: The entity the claim is about.
            predicate: The attribute or relationship being claimed.
            evidence: Evidence retrieved for this claim.
            retrieval_status: Status of the retrieval operation.
            claim_type: Type of claim (factual, numeric, temporal).

        Returns:
            EvidenceQualityAssessment with structured quality dimensions.
        """
        ...


# ---------------------------------------------------------------------------
# Dynamic vs stable fact predicates
# ---------------------------------------------------------------------------

# Predicates where recency matters more
_DYNAMIC_PREDICATES: set[str] = {
    "population",
    "unemployment_rate",
    "gdp",
    "stock_price",
    "current_ranking",
    "live_statistics",
}

# Predicates where recency matters less (stable historical facts)
_STABLE_PREDICATES: set[str] = {
    "capital_of",
    "founded",
    "completed_in",
    "dedicated",
    "established",
    "height_meters",
    "location",
}


# ---------------------------------------------------------------------------
# FixtureEvidenceQualityScorer
# ---------------------------------------------------------------------------


class FixtureEvidenceQualityScorer:
    """Deterministic evidence quality scorer.

    V2-12: Scores evidence quality across six dimensions:
    1. Authority — strength of source classification
    2. Relevance — how well evidence addresses the claim
    3. Provenance — completeness of source metadata
    4. Freshness — recency relative to claim type
    5. Corroboration — independent source agreement
    6. Consistency — agreement among authoritative sources

    The scorer is deterministic: same inputs → same assessment.
    It does NOT determine truth. It does NOT make policy decisions.
    """

    def __init__(self, reference_time: datetime | None = None) -> None:
        """Initialize the scorer.

        Args:
            reference_time: Fixed reference time for determinism.
                          Uses current UTC if None.
        """
        self._reference_time = reference_time

    @property
    def reference_time(self) -> datetime:
        """Current reference time."""
        return self._reference_time or datetime.now(timezone.utc)

    def score(
        self,
        subject: str,
        predicate: str,
        evidence: list[RetrievedEvidence],
        retrieval_status: RetrievalStatus,
        claim_type: str = "factual",
    ) -> EvidenceQualityAssessment:
        """Score the quality of evidence for a claim.

        Handles all edge cases:
        - No evidence
        - Retrieval failure (FAILED, NOT_CONFIGURED)
        - NOT_FOUND
        - Single source
        - Multiple sources (conflicting or agreeing)
        - Duplicate sources
        - Missing metadata
        """
        # Edge case: retrieval failures preserve failure semantics
        if retrieval_status in (
            RetrievalStatus.FAILED,
            RetrievalStatus.NOT_CONFIGURED,
        ):
            return self._failure_assessment(retrieval_status)

        # Edge case: no evidence
        if not evidence:
            return self._no_evidence_assessment(subject, predicate)

        # Edge case: empty content
        non_empty = [e for e in evidence if e.content.strip()]
        if not non_empty:
            return self._empty_content_assessment(subject, predicate, len(evidence))

        # Score each dimension
        authority = self._score_authority(non_empty)
        relevance = self._score_relevance(non_empty)
        provenance = self._score_provenance(non_empty)
        freshness = self._score_freshness(non_empty, predicate)
        corroboration = self._score_corroboration(non_empty)
        consistency = self._score_consistency(non_empty, predicate)

        # Count sources
        primary_count = sum(
            1 for e in non_empty
            if e.authority in ("primary", AuthorityLevel.PRIMARY)
        )
        independent_count = len({e.source_id for e in non_empty})

        # Compute overall quality
        overall, limitations, rationale = self._compute_overall(
            authority, relevance, provenance, freshness,
            corroboration, consistency, primary_count,
            independent_count, len(non_empty), retrieval_status,
        )

        return EvidenceQualityAssessment(
            overall_quality=overall,
            authority_score=authority,
            relevance_score=relevance,
            provenance_score=provenance,
            freshness_score=freshness,
            corroboration_score=corroboration,
            consistency_score=consistency,
            evidence_count=len(non_empty),
            primary_source_count=primary_count,
            independent_source_count=independent_count,
            limitations=limitations,
            rationale=rationale,
        )

    # ----- Authority -----

    def _score_authority(self, evidence: list[RetrievedEvidence]) -> float:
        """Score source authority (0.0-1.0).

        PRIMARY → 1.0, SECONDARY → 0.6, UNKNOWN → 0.2.
        Average across sources, with primary sources weighted more.
        """
        if not evidence:
            return 0.0

        scores = []
        for ev in evidence:
            auth = ev.authority.lower().strip()
            if auth in ("primary", AuthorityLevel.PRIMARY):
                scores.append(1.0)
            elif auth in ("secondary", AuthorityLevel.SECONDARY):
                scores.append(0.6)
            else:
                scores.append(0.2)

        # Weight primary sources more heavily
        primary_scores = [s for s, ev in zip(scores, evidence)
                         if ev.authority.lower().strip() in ("primary", AuthorityLevel.PRIMARY)]
        other_scores = [s for s, ev in zip(scores, evidence)
                       if ev.authority.lower().strip() not in ("primary", AuthorityLevel.PRIMARY)]

        if primary_scores:
            return sum(primary_scores) / len(primary_scores)
        return sum(other_scores) / len(other_scores) if other_scores else 0.2

    # ----- Relevance -----

    def _score_relevance(self, evidence: list[RetrievedEvidence]) -> float:
        """Score evidence relevance using retrieval relevance scores (0.0-1.0).

        Uses the relevance_score populated by the ranker.
        """
        if not evidence:
            return 0.0

        scores = [ev.relevance_score for ev in evidence]
        return sum(scores) / len(scores)

    # ----- Provenance -----

    def _score_provenance(self, evidence: list[RetrievedEvidence]) -> float:
        """Score provenance completeness (0.0-1.0).

        Considers: source_id, source_uri, source_date, retrieved_at.
        Missing optional fields reduce score but don't punish heavily.
        """
        if not evidence:
            return 0.0

        scores = []
        for ev in evidence:
            score = 0.0
            # source_id is always present (required) — base 0.4
            if ev.source_id:
                score += 0.4
            # source_uri — valuable for traceability
            if ev.source_uri:
                score += 0.2
            # source_date — valuable for freshness assessment
            if ev.source_date:
                score += 0.2
            # retrieved_at — valuable for audit trail
            if ev.retrieved_at:
                score += 0.2
            scores.append(score)

        return sum(scores) / len(scores)

    # ----- Freshness -----

    def _score_freshness(
        self, evidence: list[RetrievedEvidence], predicate: str
    ) -> float:
        """Score freshness contextually (0.0-1.0).

        For dynamic predicates (population, statistics):
            Recent evidence scores higher, stale evidence scores lower.

        For stable predicates (capital_of, founded, height):
            Freshness matters less — old evidence is still valid.

        If source_date is missing, default to moderate score.
        """
        if not evidence:
            return 0.0

        is_dynamic = predicate.lower() in _DYNAMIC_PREDICATES
        is_stable = predicate.lower() in _STABLE_PREDICATES

        ref = self.reference_time
        scores = []

        for ev in evidence:
            if not ev.source_date:
                # Missing date — moderate score
                scores.append(0.5 if is_stable else 0.3)
                continue

            try:
                source_dt = datetime.fromisoformat(ev.source_date.replace("Z", "+00:00"))
                age_days = (ref - source_dt).days
            except (ValueError, TypeError):
                # Unparseable date — moderate penalty
                scores.append(0.4)
                continue

            if is_stable:
                # Stable facts: age matters little
                if age_days <= 3650:
                    scores.append(0.9)
                elif age_days <= 18250:
                    scores.append(0.8)
                elif age_days <= 36500:
                    scores.append(0.7)
                else:
                    scores.append(0.6)
            elif is_dynamic:
                # Dynamic facts: recency matters more
                if age_days <= 365:
                    scores.append(1.0)
                elif age_days <= 730:
                    scores.append(0.8)
                elif age_days <= 1830:
                    scores.append(0.5)
                else:
                    scores.append(0.2)
            else:
                # Unknown predicate type — moderate approach
                if age_days <= 3650:
                    scores.append(0.7)
                elif age_days <= 18250:
                    scores.append(0.5)
                else:
                    scores.append(0.3)

        return sum(scores) / len(scores)

    # ----- Corroboration -----

    def _score_corroboration(self, evidence: list[RetrievedEvidence]) -> float:
        """Score independent source corroboration (0.0-1.0).

        Multiple independent authoritative sources → higher score.
        Duplicate copies of the same source → no false corroboration.
        """
        if not evidence:
            return 0.0

        # Deduplicate by source_id (same source = not independent)
        unique_sources = {ev.source_id for ev in evidence}
        independent_count = len(unique_sources)

        if independent_count == 1:
            return 0.3  # Single source — baseline corroboration
        elif independent_count == 2:
            # Check if at least one is authoritative
            has_authoritative = any(
                ev.authority.lower() in ("primary", AuthorityLevel.PRIMARY, "secondary", AuthorityLevel.SECONDARY)
                for ev in evidence
            )
            return 0.6 if has_authoritative else 0.4
        elif independent_count == 3:
            has_authoritative = any(
                ev.authority.lower() in ("primary", AuthorityLevel.PRIMARY, "secondary", AuthorityLevel.SECONDARY)
                for ev in evidence
            )
            return 0.8 if has_authoritative else 0.5
        else:
            has_authoritative = any(
                ev.authority.lower() in ("primary", AuthorityLevel.PRIMARY, "secondary", AuthorityLevel.SECONDARY)
                for ev in evidence
            )
            return 0.9 if has_authoritative else 0.6

    # ----- Consistency -----

    def _score_consistency(
        self, evidence: list[RetrievedEvidence], predicate: str
    ) -> float:
        """Score agreement among authoritative sources (0.0-1.0).

        If authoritative sources agree → high consistency.
        If authoritative sources conflict → low consistency.
        If only one authoritative source → moderate consistency.
        """
        if not evidence:
            return 0.0

        # Filter to authoritative sources
        authoritative = [
            ev for ev in evidence
            if ev.authority.lower() in ("primary", AuthorityLevel.PRIMARY, "secondary", AuthorityLevel.SECONDARY)
        ]

        if not authoritative:
            return 0.3  # No authoritative sources — uncertain consistency

        if len(authoritative) == 1:
            return 0.7  # Single authoritative source — no conflict

        # Check for value disagreements in structured_values
        values_by_key: dict[str, set[str]] = {}
        for ev in authoritative:
            for k, v in ev.structured_values.items():
                if k != "entity" and v:
                    values_by_key.setdefault(k, set()).add(v.strip().lower())

        conflicts = 0
        total_keys = 0
        for values in values_by_key.values():
            total_keys += 1
            if len(values) > 1:
                conflicts += 1

        if total_keys == 0:
            return 0.5  # No structured values to compare

        # No conflicts → high consistency
        if conflicts == 0:
            return 0.9

        # Some conflicts → reduce proportionally
        conflict_ratio = conflicts / total_keys
        return max(0.1, 0.9 - (conflict_ratio * 0.8))

    # ----- Overall -----

    def _compute_overall(
        self,
        authority: float,
        relevance: float,
        provenance: float,
        freshness: float,
        corroboration: float,
        consistency: float,
        primary_count: int,
        independent_count: int,
        evidence_count: int,
        retrieval_status: RetrievalStatus,
    ) -> tuple[str, list[str], str]:
        """Compute overall quality label, limitations, and rationale."""
        limitations: list[str] = []

        # Weighted average (authority and relevance weighted more)
        weighted = (
            authority * 0.25
            + relevance * 0.25
            + provenance * 0.10
            + freshness * 0.10
            + corroboration * 0.15
            + consistency * 0.15
        )

        # Adjust for source counts
        if primary_count == 0:
            limitations.append("no_primary_sources")
            weighted *= 0.85
        if independent_count < 2:
            limitations.append("single_source_corroboration")
        if evidence_count < 2:
            limitations.append("limited_evidence_count")

        # Check for conflicts
        if consistency < 0.4:
            limitations.append("conflicting_authoritative_sources")

        # Provenance gaps
        if provenance < 0.5:
            limitations.append("incomplete_provenance")

        # Freshness concerns for dynamic facts
        if freshness < 0.3:
            limitations.append("stale_evidence_for_dynamic_claim")

        # Determine label
        if weighted >= 0.7:
            overall = "high"
        elif weighted >= 0.45:
            overall = "moderate"
        elif weighted > 0.0:
            overall = "low"
        else:
            overall = "none"

        # Build rationale
        parts = []
        parts.append(f"authority={authority:.2f}")
        parts.append(f"relevance={relevance:.2f}")
        parts.append(f"provenance={provenance:.2f}")
        parts.append(f"freshness={freshness:.2f}")
        parts.append(f"corroboration={corroboration:.2f}")
        parts.append(f"consistency={consistency:.2f}")
        parts.append(f"sources={evidence_count}({primary_count} primary)")
        rationale = (
            f"Evidence quality: {overall} "
            f"({', '.join(parts)})"
        )

        return overall, limitations, rationale

    # ----- Edge case helpers -----

    def _failure_assessment(
        self, status: RetrievalStatus
    ) -> EvidenceQualityAssessment:
        """Assessment for retrieval failures."""
        label = status.value if hasattr(status, 'value') else str(status)
        return EvidenceQualityAssessment(
            overall_quality="none",
            authority_score=0.0,
            relevance_score=0.0,
            provenance_score=0.0,
            freshness_score=0.0,
            corroboration_score=0.0,
            consistency_score=0.0,
            evidence_count=0,
            primary_source_count=0,
            independent_source_count=0,
            limitations=[f"retrieval_{label}"],
            rationale=f"Evidence retrieval {label}: no evidence available for quality assessment",
        )

    def _no_evidence_assessment(
        self, subject: str, predicate: str
    ) -> EvidenceQualityAssessment:
        """Assessment when no evidence is found."""
        return EvidenceQualityAssessment(
            overall_quality="none",
            authority_score=0.0,
            relevance_score=0.0,
            provenance_score=0.0,
            freshness_score=0.0,
            corroboration_score=0.0,
            consistency_score=0.0,
            evidence_count=0,
            primary_source_count=0,
            independent_source_count=0,
            limitations=["no_evidence_found"],
            rationale=f"No evidence found for claim: {subject} {predicate}",
        )

    def _empty_content_assessment(
        self, subject: str, predicate: str, total_count: int
    ) -> EvidenceQualityAssessment:
        """Assessment when all evidence has empty content."""
        return EvidenceQualityAssessment(
            overall_quality="none",
            authority_score=0.0,
            relevance_score=0.0,
            provenance_score=0.0,
            freshness_score=0.0,
            corroboration_score=0.0,
            consistency_score=0.0,
            evidence_count=total_count,
            primary_source_count=0,
            independent_source_count=0,
            limitations=["empty_evidence_content"],
            rationale=f"All {total_count} evidence items have empty content",
        )
