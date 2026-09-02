"""ClaimVerifier — verifies claims against retrieved evidence.

Provider-independent abstraction for claim verification.
V2-7: Deterministic-first strategy with semantic fallback.

Architecture:

    ExtractedClaim + RetrievedEvidence[]
        ↓
    FixtureClaimVerifier.verify()
        ↓
    Deterministic comparison
        ↓
    If unresolved:
        ↓
    EvidenceSemanticReasoner.reason()
        ↓
    VerificationResult
        ↓
    Finding (Performance dimension)

The verifier does NOT:
- Extract claims
- Retrieve evidence
- Make decisions
- Use LLMs as truth sources

The verifier DOES:
- Attempt deterministic verification first
- Fall back to semantic reasoning only when deterministic fails
- Distinguish SUPPORTED/CONTRADICTED/INSUFFICIENT_EVIDENCE/CONFLICTED/UNVERIFIABLE
- Preserve evidence provenance
- Record verification method
- Handle conflicting sources explicitly
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from controlplane.detection.claim_extractor import ExtractedClaim
from controlplane.detection.evidence_retriever import RetrievedEvidence


@dataclass(frozen=True)
class VerificationResult:
    """Result of verifying a claim against evidence.

    Attributes:
        verdict: The verification outcome — one of 'supported',
                 'contradicted', 'insufficient_evidence', 'conflicting_evidence',
                 'unverifiable'.
        confidence: Confidence in the verdict (0.0-1.0).
                    NOT probability of truth. Reflects evidence strength,
                    source quality, and method certainty.
        rationale: Human-readable explanation grounded in evidence.
        source_ids: IDs of sources used for verification.
        evidence_used: The evidence content that informed the verdict.
        verification_method: How the verdict was obtained — one of
                             'deterministic', 'semantic', 'unresolved'.
        ambiguity: Free-text description of ambiguity, if any.
        evidence_quality: Quality assessment of evidence used
                          (e.g., 'authoritative', 'partial', 'none').
    """

    verdict: str
    confidence: float
    rationale: str
    source_ids: list[str] = field(default_factory=list)
    evidence_used: list[str] = field(default_factory=list)
    verification_method: str = "deterministic"
    ambiguity: str = ""
    evidence_quality: str = "none"


# Numeric tolerance for comparison (percentage)
_NUMERIC_TOLERANCE = 0.15  # 15% tolerance


def _normalize_entity(text: str) -> str:
    """Normalize entity names for comparison."""
    aliases = {
        "nyc": "new york city",
        "new york city": "new york city",
        "new york": "new york city",
        "usa": "united states",
        "united states": "united states",
        "us": "united states",
        "uk": "united kingdom",
        "united kingdom": "united kingdom",
    }
    low = text.lower().strip()
    return aliases.get(low, low)


def _parse_numeric_value(text: str) -> float | None:
    """Parse a numeric value from text."""
    text = text.strip().replace(",", "")
    try:
        return float(text)
    except (ValueError, TypeError):
        return None


class FixtureClaimVerifier:
    """Deterministic-first claim verifier with semantic fallback.

    V2-7 design: attempts deterministic verification first.
    If deterministic verification is insufficient, delegates to
    an EvidenceSemanticReasoner for semantic fallback.

    The verifier is deterministic for deterministic cases.
    Same claim + evidence → same result.
    It does NOT use an LLM. It does NOT make policy decisions.
    """

    def __init__(
        self,
        semantic_reasoner: object | None = None,
    ) -> None:
        """Initialize the verifier.

        Args:
            semantic_reasoner: Optional EvidenceSemanticReasoner instance.
                             When provided, used as fallback for claims
                             that cannot be resolved deterministically.
        """
        self._semantic_reasoner = semantic_reasoner

    def verify(
        self,
        claim: ExtractedClaim,
        evidence: list[RetrievedEvidence],
    ) -> VerificationResult:
        """Verify a claim against retrieved evidence.

        Strategy:
        1. Attempt deterministic verification
        2. If deterministic resolves → return immediately
        3. If deterministic is insufficient → semantic fallback
        4. If no semantic reasoner → return INSUFFICIENT_EVIDENCE

        Args:
            claim: The extracted claim to verify.
            evidence: Evidence retrieved for this claim.

        Returns:
            VerificationResult with verdict, confidence, rationale,
            provenance, verification_method, and ambiguity.
        """
        if not evidence:
            return VerificationResult(
                verdict="insufficient_evidence",
                confidence=0.0,
                rationale=f"No evidence found for claim: {claim.claim_text}",
                source_ids=[],
                evidence_used=[],
                verification_method="deterministic",
                ambiguity="No evidence available for verification",
                evidence_quality="none",
            )

        source_ids = [e.source_id for e in evidence]
        evidence_contents = [e.content for e in evidence]

        # PHASE 0: Check for conflicting sources BEFORE verification
        # If authoritative sources disagree, that takes precedence
        conflicting = self._detect_source_conflict(claim, evidence)
        if conflicting:
            return conflicting

        # PHASE 1: Deterministic verification
        det_result = self._deterministic_verify(
            claim, evidence, source_ids, evidence_contents
        )

        # If deterministic resolved, return immediately
        if det_result.verdict not in ("insufficient_evidence", "unverifiable"):
            return det_result

        # PHASE 3: Semantic fallback for unresolved claims
        if self._semantic_reasoner is not None:
            return self._semantic_fallback(
                claim, evidence, source_ids, evidence_contents, det_result
            )

        # No semantic reasoner — return deterministic result
        return det_result

    def _deterministic_verify(
        self,
        claim: ExtractedClaim,
        evidence: list[RetrievedEvidence],
        source_ids: list[str],
        evidence_contents: list[str],
    ) -> VerificationResult:
        """Attempt deterministic verification."""
        if claim.claim_type == "factual":
            return self._verify_factual(claim, evidence, source_ids, evidence_contents)
        elif claim.claim_type == "numeric":
            return self._verify_numeric(claim, evidence, source_ids, evidence_contents)
        elif claim.claim_type == "temporal":
            return self._verify_temporal(claim, evidence, source_ids, evidence_contents)
        else:
            return VerificationResult(
                verdict="unverifiable",
                confidence=0.0,
                rationale=f"Unsupported claim type: {claim.claim_type}",
                source_ids=source_ids,
                evidence_used=evidence_contents,
                verification_method="deterministic",
                ambiguity=f"Claim type '{claim.claim_type}' not supported by deterministic verifier",
                evidence_quality="none",
            )

    def _semantic_fallback(
        self,
        claim: ExtractedClaim,
        evidence: list[RetrievedEvidence],
        source_ids: list[str],
        evidence_contents: list[str],
        det_result: VerificationResult,
    ) -> VerificationResult:
        """Delegate to semantic reasoner when deterministic is insufficient."""
        try:
            semantic_verdict = self._semantic_reasoner.reason(
                claim=claim.claim_text,
                evidence=evidence_contents,
                context={
                    "subject": claim.subject,
                    "predicate": claim.predicate,
                    "value": claim.value,
                    "claim_type": claim.claim_type,
                },
            )
            return VerificationResult(
                verdict=semantic_verdict.verdict,
                confidence=semantic_verdict.confidence,
                rationale=semantic_verdict.rationale,
                source_ids=source_ids,
                evidence_used=evidence_contents,
                verification_method="semantic",
                ambiguity=semantic_verdict.ambiguity,
                evidence_quality="partial",
            )
        except Exception as exc:
            return VerificationResult(
                verdict="unverifiable",
                confidence=0.0,
                rationale=f"Semantic reasoner failed: {exc}",
                source_ids=source_ids,
                evidence_used=evidence_contents,
                verification_method="unresolved",
                ambiguity=f"Infrastructure failure: {type(exc).__name__}",
                evidence_quality="partial",
            )

    def _detect_source_conflict(
        self,
        claim: ExtractedClaim,
        evidence: list[RetrievedEvidence],
    ) -> VerificationResult | None:
        """Detect conflicting evidence from multiple authoritative sources.

        Returns a CONFLICTED result if authoritative sources disagree,
        or None if no conflict detected.
        """
        if len(evidence) < 2:
            return None

        claim_entity = _normalize_entity(claim.subject)

        # Collect contradictory values from authoritative sources
        authoritative_values: list[tuple[str, str]] = []  # (value, source_id)

        for ev in evidence:
            if ev.authority not in ("primary", "secondary"):
                continue
            sv = ev.structured_values
            ev_entity = _normalize_entity(sv.get("entity", ""))
            if claim_entity != ev_entity:
                continue

            if claim.claim_type == "factual" and claim.predicate == "capital_of":
                ev_value = _normalize_entity(sv.get("capital_of", ""))
                if ev_value:
                    authoritative_values.append((ev_value, ev.source_id))

            elif claim.claim_type == "numeric":
                ev_value_text = sv.get(claim.predicate, "")
                ev_value = _parse_numeric_value(ev_value_text)
                if ev_value is not None:
                    authoritative_values.append((ev_value_text, ev.source_id))

        if len(authoritative_values) < 2:
            return None

        values = [v[0] for v in authoritative_values]
        if len(set(values)) > 1:
            source_ids = [v[1] for v in authoritative_values]
            evidence_contents = [e.content for e in evidence if e.source_id in source_ids]
            return VerificationResult(
                verdict="conflicting_evidence",
                confidence=0.5,
                rationale=(
                    f"Multiple authoritative sources disagree on "
                    f"{claim.subject} {claim.predicate}: "
                    f"{'; '.join(f'{v} (source {s})' for v, s in authoritative_values)}"
                ),
                source_ids=source_ids,
                evidence_used=evidence_contents,
                verification_method="deterministic",
                ambiguity=(
                    f"Source disagreement: {len(set(values))} different values "
                    f"from {len(authoritative_values)} authoritative sources"
                ),
                evidence_quality="conflicting",
            )

        return None

    def _verify_factual(
        self,
        claim: ExtractedClaim,
        evidence: list[RetrievedEvidence],
        source_ids: list[str],
        evidence_contents: list[str],
    ) -> VerificationResult:
        """Verify a factual claim (e.g., 'Paris is the capital of France')."""
        claim_entity = _normalize_entity(claim.subject)
        claim_value = _normalize_entity(claim.value)

        for ev in evidence:
            sv = ev.structured_values

            # Check capital_of relationship
            if claim.predicate == "capital_of":
                ev_capital = _normalize_entity(sv.get("capital_of", ""))
                ev_entity = _normalize_entity(sv.get("entity", ""))

                if claim_entity == ev_entity and claim_value == ev_capital:
                    authority_boost = 0.1 if ev.authority == "primary" else 0.0
                    return VerificationResult(
                        verdict="supported",
                        confidence=min(0.95 + authority_boost, 1.0),
                        rationale=(
                            f"Confirmed: {claim.subject} is the capital of {claim.value}. "
                            f"Source {ev.source_id} states: {ev.content[:100]}"
                        ),
                        source_ids=[ev.source_id],
                        evidence_used=[ev.content],
                        verification_method="deterministic",
                        evidence_quality="authoritative" if ev.authority == "primary" else "secondary",
                    )

            # Check if evidence contradicts the claim
            if claim.predicate == "capital_of":
                ev_capital_of = sv.get("capital_of", "")
                if ev_capital_of and _normalize_entity(ev_capital_of) != claim_value:
                    ev_entity = _normalize_entity(sv.get("entity", ""))
                    if claim_entity == ev_entity:
                        return VerificationResult(
                            verdict="contradicted",
                            confidence=0.85,
                            rationale=(
                                f"Contradicted: {claim.subject} is capital of {ev_capital_of}, "
                                f"not {claim.value}. Source: {ev.source_id}"
                            ),
                            source_ids=[ev.source_id],
                            evidence_used=[ev.content],
                            verification_method="deterministic",
                            evidence_quality="authoritative" if ev.authority == "primary" else "secondary",
                        )

        return VerificationResult(
            verdict="insufficient_evidence",
            confidence=0.3,
            rationale=(
                f"Evidence found but does not confirm or deny: "
                f"{claim.subject} {claim.predicate} {claim.value}"
            ),
            source_ids=source_ids,
            evidence_used=evidence_contents,
            verification_method="deterministic",
            ambiguity="Evidence does not directly address the claim",
            evidence_quality="partial",
        )

    def _verify_numeric(
        self,
        claim: ExtractedClaim,
        evidence: list[RetrievedEvidence],
        source_ids: list[str],
        evidence_contents: list[str],
    ) -> VerificationResult:
        """Verify a numeric claim (e.g., population, height)."""
        claim_value = _parse_numeric_value(claim.value)
        if claim_value is None:
            return VerificationResult(
                verdict="unverifiable",
                confidence=0.0,
                rationale=f"Cannot parse claim value: {claim.value}",
                source_ids=source_ids,
                evidence_used=evidence_contents,
                verification_method="deterministic",
                ambiguity="Claim value not parseable as number",
                evidence_quality="none",
            )

        claim_entity = _normalize_entity(claim.subject)

        for ev in evidence:
            sv = ev.structured_values
            ev_entity = _normalize_entity(sv.get("entity", ""))

            if claim_entity != ev_entity:
                continue

            ev_value_text = sv.get(claim.predicate, "")
            if not ev_value_text:
                continue

            ev_value = _parse_numeric_value(ev_value_text)
            if ev_value is None:
                continue

            # Compare with tolerance
            if claim_value == 0 and ev_value == 0:
                match = True
            elif claim_value == 0 or ev_value == 0:
                match = abs(claim_value - ev_value) < 1000
            else:
                ratio = abs(claim_value - ev_value) / max(abs(claim_value), abs(ev_value))
                match = ratio <= _NUMERIC_TOLERANCE

            if match:
                authority_boost = 0.1 if ev.authority == "primary" else 0.0
                return VerificationResult(
                    verdict="supported",
                    confidence=min(0.9 + authority_boost, 1.0),
                    rationale=(
                        f"Confirmed: {claim.subject} {claim.predicate} is approximately "
                        f"{claim.value}. Source {ev.source_id} reports {ev_value_text}."
                    ),
                    source_ids=[ev.source_id],
                    evidence_used=[ev.content],
                    verification_method="deterministic",
                    evidence_quality="authoritative" if ev.authority == "primary" else "secondary",
                )
            else:
                return VerificationResult(
                    verdict="contradicted",
                    confidence=0.9,
                    rationale=(
                        f"Contradicted: {claim.subject} {claim.predicate} claimed as "
                        f"{claim.value}, but source {ev.source_id} reports {ev_value_text}."
                    ),
                    source_ids=[ev.source_id],
                    evidence_used=[ev.content],
                    verification_method="deterministic",
                    evidence_quality="authoritative" if ev.authority == "primary" else "secondary",
                )

        return VerificationResult(
            verdict="insufficient_evidence",
            confidence=0.2,
            rationale=(
                f"No matching evidence for numeric claim: "
                f"{claim.subject} {claim.predicate} = {claim.value}"
            ),
            source_ids=source_ids,
            evidence_used=evidence_contents,
            verification_method="deterministic",
            ambiguity="No structured numeric evidence for this entity",
            evidence_quality="partial",
        )

    def _verify_temporal(
        self,
        claim: ExtractedClaim,
        evidence: list[RetrievedEvidence],
        source_ids: list[str],
        evidence_contents: list[str],
    ) -> VerificationResult:
        """Verify a temporal claim (e.g., completion date)."""
        claim_entity = _normalize_entity(claim.subject)
        claim_date = claim.value.strip()

        for ev in evidence:
            sv = ev.structured_values
            ev_entity = _normalize_entity(sv.get("entity", ""))

            if claim_entity != ev_entity:
                continue

            for date_key in ("completed", "founded", "dedicated", "established"):
                ev_date = sv.get(date_key, "")
                if ev_date and ev_date == claim_date:
                    authority_boost = 0.1 if ev.authority == "primary" else 0.0
                    return VerificationResult(
                        verdict="supported",
                        confidence=min(0.9 + authority_boost, 1.0),
                        rationale=(
                            f"Confirmed: {claim.subject} {date_key} in {claim_date}. "
                            f"Source: {ev.source_id}"
                        ),
                        source_ids=[ev.source_id],
                        evidence_used=[ev.content],
                        verification_method="deterministic",
                        evidence_quality="authoritative" if ev.authority == "primary" else "secondary",
                    )

        return VerificationResult(
            verdict="insufficient_evidence",
            confidence=0.2,
            rationale=(
                f"No matching evidence for temporal claim: "
                f"{claim.subject} {claim.predicate} {claim_date}"
            ),
            source_ids=source_ids,
            evidence_used=evidence_contents,
            verification_method="deterministic",
            ambiguity="No temporal evidence for this entity",
            evidence_quality="partial",
        )
