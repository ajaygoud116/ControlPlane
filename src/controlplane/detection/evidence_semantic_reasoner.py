"""EvidenceSemanticReasoner — semantic fallback for claim verification.

When deterministic verification cannot resolve a claim-evidence relationship,
the semantic reasoner interprets the claim against the retrieved evidence.

CRITICAL DESIGN PRINCIPLE:
    The reasoner does NOT determine truth.
    The reasoner interprets the relationship between claim and evidence.
    The source of truth is evidence — not the evaluator.

Architecture:

    Claim + Evidence[] + Context
        ↓
    EvidenceSemanticReasoner.reason()
        ↓
    SemanticVerdict

The reasoner does NOT:
- Determine factual truth
- Access external knowledge
- Make policy decisions

The reasoner DOES:
- Compare claim against supplied evidence
- Determine if evidence supports, contradicts, or fails to resolve claim
- Preserve provenance and rationale
- Return conservative verdict when evidence is insufficient
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SemanticVerdict:
    """Verdict from evidence-grounded semantic reasoning.

    Attributes:
        verdict: One of 'supported', 'contradicted',
                 'insufficient_evidence', 'conflicting_evidence'.
        confidence: Confidence in [0.0, 1.0]. NOT probability of truth.
        rationale: Human-readable explanation grounded in evidence.
        source_ids: IDs of sources used.
        evidence_used: Evidence content that informed the verdict.
        verification_method: 'deterministic', 'semantic', or 'unresolved'.
        ambiguity: Free-text description of ambiguity, if any.
    """

    verdict: str
    confidence: float
    rationale: str
    source_ids: list[str] = field(default_factory=list)
    evidence_used: list[str] = field(default_factory=list)
    verification_method: str = "semantic"
    ambiguity: str = ""


@runtime_checkable
class EvidenceSemanticReasoner(Protocol):
    """Protocol for evidence-grounded semantic reasoning providers.

    A reasoner receives a claim, evidence, and context, and returns
    a SemanticVerdict. The verdict MUST be grounded in the supplied
    evidence — not in pretrained knowledge.
    """

    def reason(
        self,
        claim: str,
        evidence: list[str],
        context: dict | None = None,
    ) -> SemanticVerdict:
        """Interpret a claim against supplied evidence.

        Args:
            claim: The claim to evaluate.
            evidence: Evidence content strings to reason over.
            context: Additional context for reasoning.

        Returns:
            SemanticVerdict grounded in the evidence.
        """
        ...


class FixtureEvidenceSemanticReasoner:
    """Offline deterministic semantic reasoner for testing.

    Uses predefined fixture cases to simulate semantic reasoning.
    Matches claim-evidence pairs against known patterns and returns
    deterministic, reproducible verdicts.

    This is NOT an LLM. It is a deterministic fixture that demonstrates
    the evidence-grounded verification architecture offline.

    The reasoner does NOT:
- Use any LLM or AI model
- Access external APIs
- Make truth claims

    The reasoner DOES:
- Match claim-evidence pairs against known patterns
- Return deterministic verdicts
- Preserve provenance
- Handle unknown cases conservatively
    """

    def __init__(self, fixture_cases: list[dict] | None = None) -> None:
        """Initialize with optional custom fixture cases.

        Args:
            fixture_cases: List of dicts with keys:
                'keywords': list of keywords in claim
                'evidence_keywords': list of keywords in evidence
                'verdict': expected verdict
                'confidence': expected confidence
                'rationale': expected rationale
                'ambiguity': optional ambiguity string
        """
        self._cases = fixture_cases or self._default_cases()
        self._call_count = 0

    @property
    def call_count(self) -> int:
        """Number of times reason() has been called."""
        return self._call_count

    def reason(
        self,
        claim: str,
        evidence: list[str],
        context: dict | None = None,
    ) -> SemanticVerdict:
        """Interpret a claim against supplied evidence.

        Uses fixture matching to determine the semantic relationship
        between claim and evidence.
        """
        self._call_count += 1

        if not evidence:
            return SemanticVerdict(
                verdict="insufficient_evidence",
                confidence=0.0,
                rationale="No evidence provided for semantic reasoning",
                source_ids=[],
                evidence_used=[],
                verification_method="semantic",
                ambiguity="No evidence available for reasoning",
            )

        claim_lower = claim.lower()
        evidence_text = " ".join(evidence).lower()

        for case in self._cases:
            claim_matches = all(
                kw.lower() in claim_lower for kw in case.get("keywords", [])
            )
            evidence_matches = all(
                kw.lower() in evidence_text
                for kw in case.get("evidence_keywords", [])
            )

            if claim_matches and evidence_matches:
                return SemanticVerdict(
                    verdict=case["verdict"],
                    confidence=case["confidence"],
                    rationale=case["rationale"],
                    source_ids=[],
                    evidence_used=evidence,
                    verification_method="semantic",
                    ambiguity=case.get("ambiguity", ""),
                )

        return SemanticVerdict(
            verdict="insufficient_evidence",
            confidence=0.2,
            rationale="No matching fixture case for claim-evidence pair",
            source_ids=[],
            evidence_used=evidence,
            verification_method="semantic",
            ambiguity="Claim-evidence pair not covered by fixture cases",
        )

    @staticmethod
    def _default_cases() -> list[dict]:
        """Return the default V2-7 fixture cases."""
        return [
            {
                "keywords": ["eliminates", "risk"],
                "evidence_keywords": ["reduced", "risk"],
                "verdict": "contradicted",
                "confidence": 0.85,
                "rationale": (
                    "Claim asserts elimination of risk, but evidence shows "
                    "only a reduction. The absolute claim exceeds the evidence."
                ),
                "ambiguity": "Overclaim: 'eliminates' vs 'reduced'",
            },
            {
                "keywords": ["operating", "costs"],
                "evidence_keywords": ["operating", "expenses", "fell"],
                "verdict": "supported",
                "confidence": 0.80,
                "rationale": (
                    "Claim states operating costs were reduced. Evidence confirms "
                    "operating expenses fell by 8% year over year."
                ),
            },
            {
                "keywords": ["eliminates", "risk"],
                "evidence_keywords": ["reduced", "observed", "risk"],
                "verdict": "contradicted",
                "confidence": 0.85,
                "rationale": (
                    "Claim states the intervention eliminates risk. Evidence shows "
                    "only a 32% reduction in observed risk. The absolute claim "
                    "exceeds the evidence."
                ),
                "ambiguity": "Overclaim: 'eliminates' vs 'reduced by 32%'",
            },
            {
                "keywords": ["record", "profitability"],
                "evidence_keywords": ["net", "income", "increased"],
                "verdict": "insufficient_evidence",
                "confidence": 0.3,
                "rationale": (
                    "Claim asserts record profitability. Evidence shows net income "
                    "increased 4%, but does not establish this is a record."
                ),
                "ambiguity": "Evidence does not confirm or deny the 'record' claim",
            },
            {
                "keywords": ["survival"],
                "evidence_keywords": ["progression-free", "survival"],
                "verdict": "contradicted",
                "confidence": 0.85,
                "rationale": (
                    "Claim asserts substantial improvement in survival. Evidence "
                    "shows improvement only in progression-free survival, not "
                    "overall survival. The claim overstates the evidence."
                ),
                "ambiguity": "Overclaim: 'survival' vs 'progression-free survival'",
            },
            {
                "keywords": ["tokyo", "population"],
                "evidence_keywords": ["tokyo", "population", "13.5"],
                "verdict": "conflicting_evidence",
                "confidence": 0.5,
                "rationale": (
                    "Multiple authoritative sources report different population "
                    "figures for Tokyo (14 million vs 13.5 million). Sources may "
                    "refer to different dates or definitions."
                ),
                "ambiguity": "Source disagreement on population figure",
            },
            {
                "keywords": ["tokyo", "population"],
                "evidence_keywords": ["tokyo", "population", "14"],
                "verdict": "supported",
                "confidence": 0.75,
                "rationale": (
                    "Claim matches evidence from source reporting Tokyo population "
                    "as 14 million."
                ),
            },
        ]
