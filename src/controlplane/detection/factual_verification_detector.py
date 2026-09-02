"""FactualVerificationDetector — autonomous fact-checking from free-form text.

V2-7: Evidence-grounded verification with deterministic-first strategy.

Composes ClaimExtractor → EvidenceRetriever → ClaimVerifier → Finding.

Architecture:

    Response Observation
        ↓
    FactualVerificationDetector.detect()
        ↓
    ClaimExtractor.extract()
        ↓
    ExtractedClaim[]
        ↓
    EvidenceRetriever.retrieve() (per claim)
        ↓
    ClaimVerifier.verify() (per claim)
        ↓
    Deterministic comparison first
        ↓
    Semantic fallback if unresolved
        ↓
    Finding (Performance dimension)
        ↓
    RiskRegistry / Decision Engine

The detector does NOT:
- Make decisions (ALLOW/BLOCK/ESCALATE)
- Apply policy
- Access the RiskRegistry

The detector DOES:
- Extract claims from free-form text automatically
- Retrieve evidence from local corpus
- Verify claims against evidence (deterministic-first)
- Produce Finding objects compatible with existing governance
- Preserve claim/evidence provenance
- Handle failures conservatively
- Distinguish infrastructure failure from factual contradiction
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from controlplane.detection.base import BaseDetector
from controlplane.detection.claim_extractor import ExtractedClaim, FixtureClaimExtractor
from controlplane.detection.claim_verifier import FixtureClaimVerifier, VerificationResult
from controlplane.detection.evidence_quality import (
    EvidenceQualityAssessment,
    EvidenceQualityScorer,
    FixtureEvidenceQualityScorer,
)
from controlplane.detection.evidence_retriever import (
    EvidenceRetrievalResult,
    FixtureEvidenceRetriever,
    RetrievedEvidence,
    RetrievalStatus,
)
from controlplane.schemas.enums import FindingDimension, ObservationType, PerformanceState
from controlplane.schemas.finding import Finding, FindingAmbiguity, FindingEvidence, FindingMeasurement
from controlplane.schemas.observation import Observation


class FactualVerificationDetector(BaseDetector):
    """Autonomous factual verification detector.

    V2-7 design: deterministic-first verification with semantic fallback.
    The detector extracts claims, retrieves evidence, verifies claims
    against evidence, and produces Performance Findings.

    Usage::

        detector = FactualVerificationDetector(
            corpus_path="path/to/corpus.json",
        )
        findings = detector.detect([observation])

        # With semantic fallback:
        from controlplane.detection.evidence_semantic_reasoner import (
            FixtureEvidenceSemanticReasoner,
        )
        reasoner = FixtureEvidenceSemanticReasoner()
        verifier = FixtureClaimVerifier(semantic_reasoner=reasoner)
        detector = FactualVerificationDetector(
            corpus_path="path/to/corpus.json",
            claim_verifier=verifier,
        )
    """

    detector_id = "factual_verification"
    detector_version = "4.0.0"

    def __init__(
        self,
        corpus_path: str | Path | None = None,
        claim_extractor: FixtureClaimExtractor | None = None,
        evidence_retriever: FixtureEvidenceRetriever | None = None,
        claim_verifier: FixtureClaimVerifier | None = None,
        evidence_quality_scorer: EvidenceQualityScorer | None = None,
    ) -> None:
        """Initialize the factual verification detector.

        Args:
            corpus_path: Path to the local evidence corpus JSON.
            claim_extractor: Custom claim extractor. Uses default if None.
            evidence_retriever: Custom evidence retriever. Uses default if None.
            claim_verifier: Custom claim verifier. Uses default if None.
                           May include a semantic_reasoner for fallback.
            evidence_quality_scorer: Custom quality scorer. Uses default if None.
        """
        self._claim_extractor = claim_extractor or FixtureClaimExtractor()
        self._claim_verifier = claim_verifier or FixtureClaimVerifier()
        self._quality_scorer = evidence_quality_scorer or FixtureEvidenceQualityScorer()

        if evidence_retriever:
            self._evidence_retriever = evidence_retriever
        elif corpus_path:
            self._evidence_retriever = FixtureEvidenceRetriever(corpus_path)
        else:
            raise ValueError(
                "Either corpus_path or evidence_retriever must be provided"
            )

    def detect(self, observations: list[Observation]) -> list[Finding]:
        """Analyze observations for factual claims and verify them.

        Extracts text from observations, automatically extracts claims,
        retrieves evidence, verifies each claim, and produces Finding objects.

        Args:
            observations: Observations to analyze.

        Returns:
            List of Finding objects, one per extracted claim.
            Empty if no claims found.
        """
        findings: list[Finding] = []

        for obs in observations:
            if obs.observation_type != ObservationType.RESPONSE:
                continue

            text = self._extract_text(obs)
            if not text:
                continue

            try:
                claims = self._claim_extractor.extract(text)
            except Exception as exc:
                findings.append(self._make_failure_finding(
                    obs,
                    ExtractedClaim(
                        claim_text=text[:200],
                        claim_type="unknown",
                        subject="unknown",
                        predicate="unknown",
                        value="",
                    ),
                    f"Claim extraction failed: {exc}",
                    datetime.now(timezone.utc),
                ))
                continue

            for claim in claims:
                finding = self._verify_claim(obs, claim)
                findings.append(finding)

        return findings

    def _verify_claim(
        self, observation: Observation, claim: ExtractedClaim
    ) -> Finding:
        """Verify a single claim and produce a Finding."""
        t_start = datetime.now(timezone.utc)

        try:
            retrieval_result = self._evidence_retriever.retrieve(
                subject=claim.subject,
                predicate=claim.predicate,
                claim_type=claim.claim_type,
            )
        except Exception as exc:
            return self._make_failure_finding(
                observation, claim, f"Evidence retrieval failed: {exc}", t_start
            )

        # Handle retrieval failures explicitly
        if retrieval_result.status == RetrievalStatus.FAILED:
            return self._make_failure_finding(
                observation,
                claim,
                f"Evidence retrieval failed: {retrieval_result.error or 'unknown error'}",
                t_start,
            )

        if retrieval_result.status == RetrievalStatus.NOT_CONFIGURED:
            return self._make_failure_finding(
                observation,
                claim,
                f"Evidence source not configured: {retrieval_result.error or 'external provider unavailable'}",
                t_start,
            )

        # NOT_FOUND → proceed with empty evidence (INSUFFICIENT_EVIDENCE)
        evidence = retrieval_result.evidence

        # V2-12: Score evidence quality BEFORE verification
        quality_assessment = self._quality_scorer.score(
            subject=claim.subject,
            predicate=claim.predicate,
            evidence=evidence,
            retrieval_status=retrieval_result.status,
            claim_type=claim.claim_type,
        )

        try:
            result = self._claim_verifier.verify(claim, evidence)
        except Exception as exc:
            return self._make_failure_finding(
                observation, claim, f"Verification failed: {exc}", t_start
            )

        return self._result_to_finding(
            observation, claim, evidence, result, t_start,
            retrieval_result, quality_assessment,
        )

    def _result_to_finding(
        self,
        observation: Observation,
        claim: ExtractedClaim,
        evidence: list[RetrievedEvidence],
        result: VerificationResult,
        t_start: datetime,
        retrieval_result: EvidenceRetrievalResult | None = None,
        quality_assessment: EvidenceQualityAssessment | None = None,
    ) -> Finding:
        """Convert a verification result to a Finding."""
        t_end = datetime.now(timezone.utc)
        latency_ms = (t_end - t_start).total_seconds() * 1000

        state = self._verdict_to_state(result.verdict)

        # Build counter_evidence for contradicted/conflicting verdicts
        counter_evidence = []
        if result.verdict in ("contradicted", "conflicting_evidence"):
            counter_evidence = result.evidence_used

        # V2-12: Use quality assessment for source_quality if available
        source_quality_str = str(result.confidence)
        quality_assessment_dict = None
        if quality_assessment:
            quality_assessment_dict = {
                "overall_quality": quality_assessment.overall_quality,
                "authority_score": quality_assessment.authority_score,
                "relevance_score": quality_assessment.relevance_score,
                "provenance_score": quality_assessment.provenance_score,
                "freshness_score": quality_assessment.freshness_score,
                "corroboration_score": quality_assessment.corroboration_score,
                "consistency_score": quality_assessment.consistency_score,
                "evidence_count": quality_assessment.evidence_count,
                "primary_source_count": quality_assessment.primary_source_count,
                "independent_source_count": quality_assessment.independent_source_count,
                "limitations": quality_assessment.limitations,
            }

        evidence_obj = FindingEvidence(
            claim_text=claim.claim_text,
            source_ids=result.source_ids,
            source_quality=source_quality_str,
            counter_evidence=counter_evidence,
            quality_assessment=quality_assessment_dict,
        )

        measurement = FindingMeasurement(
            latency_ms=latency_ms,
            estimated_cost_usd=0.0,
        )

        ambiguity = FindingAmbiguity()
        if result.confidence < 0.5:
            ambiguity.reasons.append(f"Low confidence: {result.confidence:.2f}")
        if result.verdict == "insufficient_evidence":
            ambiguity.reasons.append("Insufficient evidence to verify claim")
        if result.verdict == "unverifiable":
            ambiguity.reasons.append("Verification process failed")
        if result.verdict == "conflicting_evidence":
            ambiguity.reasons.append("Conflicting evidence from multiple sources")
        if result.ambiguity:
            ambiguity.reasons.append(result.ambiguity)

        # V2-12: Include quality limitations in ambiguity
        if quality_assessment and quality_assessment.limitations:
            for lim in quality_assessment.limitations:
                ambiguity.reasons.append(f"Quality: {lim}")

        # Include retrieval status in ambiguity if not found
        if retrieval_result and retrieval_result.status == RetrievalStatus.NOT_FOUND:
            ambiguity.reasons.append("No evidence found in any source")

        # Build explanation with verification method
        explanation = result.rationale
        if result.verification_method:
            explanation = f"[method={result.verification_method}] {explanation}"
        if retrieval_result:
            explanation = f"[retrieval={retrieval_result.retrieval_method}] {explanation}"
        # V2-12: Append quality rationale
        if quality_assessment and quality_assessment.rationale:
            explanation = f"{explanation} | {quality_assessment.rationale}"

        return Finding(
            finding_id=uuid4(),
            interaction_id=observation.interaction_id,
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            dimension=FindingDimension.PERFORMANCE,
            finding_type=f"claim_{claim.claim_type}",
            state=state,
            observation_ids=[observation.observation_id],
            evidence=evidence_obj,
            measurement=measurement,
            ambiguity=ambiguity,
            explanation=explanation,
            detected_at=t_end,
            latency_ms=latency_ms,
            cost_usd=0.0,
        )

    def _make_failure_finding(
        self,
        observation: Observation,
        claim: ExtractedClaim,
        reason: str,
        t_start: datetime,
    ) -> Finding:
        """Create a Finding for a verification failure.

        CRITICAL: Infrastructure failure != factual contradiction.
        Failures produce UNVERIFIABLE, not CONTRADICTED.
        """
        t_end = datetime.now(timezone.utc)
        latency_ms = (t_end - t_start).total_seconds() * 1000

        return Finding(
            finding_id=uuid4(),
            interaction_id=observation.interaction_id,
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            dimension=FindingDimension.PERFORMANCE,
            finding_type=f"claim_{claim.claim_type}",
            state=PerformanceState.UNVERIFIABLE,
            observation_ids=[observation.observation_id],
            evidence=FindingEvidence(
                claim_text=claim.claim_text,
                source_ids=[],
                source_quality="0.0",
                counter_evidence=[],
            ),
            measurement=FindingMeasurement(
                latency_ms=latency_ms,
                estimated_cost_usd=0.0,
            ),
            ambiguity=FindingAmbiguity(
                reasons=[f"Verification failure: {reason}"],
            ),
            explanation=f"Verification could not be completed: {reason}",
            detected_at=t_end,
            latency_ms=latency_ms,
            cost_usd=0.0,
        )

    def _verdict_to_state(self, verdict: str) -> PerformanceState:
        """Map a verification verdict to a PerformanceState."""
        mapping = {
            "supported": PerformanceState.SUPPORTED,
            "contradicted": PerformanceState.CONTRADICTED,
            "insufficient_evidence": PerformanceState.INSUFFICIENT_EVIDENCE,
            "conflicting_evidence": PerformanceState.CONFLICTED,
            "verification_failed": PerformanceState.UNVERIFIABLE,
            "unverifiable": PerformanceState.UNVERIFIABLE,
        }
        return mapping.get(verdict, PerformanceState.UNVERIFIABLE)

    def _extract_text(self, observation: Observation) -> str | None:
        """Extract text content from an observation."""
        payload = observation.payload
        if not isinstance(payload, dict):
            return None
        for key in ("text", "content", "response", "input"):
            if key in payload:
                value = payload[key]
                if isinstance(value, str) and value.strip():
                    return value
        return None
