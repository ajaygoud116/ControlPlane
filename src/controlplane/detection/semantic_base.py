"""SemanticDetector — bridges semantic evaluation to Finding abstraction.

Converts SemanticEvaluator output into repository Finding objects.
Preserves evaluator confidence/evidence where supported by existing
Finding fields.

Architecture:

    Observation → SemanticDetector.detect()
                         |
                   SemanticEvaluator.evaluate()
                         |
                   SemanticEvaluation
                         |
                   Finding (with appropriate dimension/state)
                         |
                   RiskRegistry / Decision Engine

The semantic detector does NOT:
- Make decisions (ALLOW/BLOCK/ESCALATE)
- Apply policy
- Know about the RiskRegistry (beyond producing recognized states)

The semantic detector DOES:
- Extract text from observations
- Invoke SemanticEvaluator
- Map evaluation to Finding dimension/state
- Preserve confidence/evidence in Finding fields
- Handle evaluator failures as undetectable conditions
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from controlplane.detection.base import BaseDetector
from controlplane.detection.evaluator import SemanticEvaluation, SemanticEvaluator
from controlplane.schemas.enums import (
    FindingDimension,
    PerformanceState,
    ResponsibilityState,
)
from controlplane.schemas.finding import Finding, FindingAmbiguity, FindingEvidence, FindingMeasurement
from controlplane.schemas.observation import Observation


class SemanticDetector(BaseDetector):
    """Abstract base for semantic/LLM-based detectors.

    Subclasses must define:
        detector_id: str
        detector_version: str

    Subclasses must implement:
        detect(observations) → list[Finding]

    This base class provides:
        - SemanticEvaluator integration
        - Configurable dimension/state mapping
        - Finding construction from SemanticEvaluation
        - Failure handling as Finding conditions

    The dimension and state mappings are configurable per detector.
    Subclasses can set defaults appropriate for their detection task.

    Example::

        class BiasDetector(SemanticDetector):
            detector_id = "bias_detector"
            detector_version = "1.0.0"

            def __init__(self, evaluator, **kwargs):
                super().__init__(
                    evaluator=evaluator,
                    dimension=FindingDimension.RESPONSIBILITY,
                    detected_state=ResponsibilityState.UNSAFE_CONTENT_DETECTED,
                    undetected_state=ResponsibilityState.RESPONSIBILITY_CLEAN,
                    default_task="Detect gender, racial, or other bias.",
                    **kwargs,
                )
    """

    evaluator: SemanticEvaluator
    dimension: FindingDimension
    detected_state: Any
    undetected_state: Any
    default_task: str

    def __init__(
        self,
        evaluator: SemanticEvaluator,
        *,
        dimension: FindingDimension = FindingDimension.RESPONSIBILITY,
        detected_state: Any = ResponsibilityState.UNSAFE_CONTENT_DETECTED,
        undetected_state: Any = ResponsibilityState.RESPONSIBILITY_CLEAN,
        default_task: str = "Detect semantic issues in text.",
        detector_id: str = "semantic_detector",
        detector_version: str = "1.0.0",
    ) -> None:
        """Initialize the semantic detector.

        Args:
            evaluator: SemanticEvaluator to use.
            dimension: Finding dimension for this detector.
            detected_state: State value when target is detected.
            undetected_state: State value when target is not detected.
            default_task: Default semantic task description.
            detector_id: Unique identifier for this detector.
            detector_version: Version of this detector.
        """
        self.evaluator = evaluator
        self.dimension = dimension
        self.detected_state = detected_state
        self.undetected_state = undetected_state
        self.default_task = default_task
        self.detector_id = detector_id
        self.detector_version = detector_version

    def detect(self, observations: list[Observation]) -> list[Finding]:
        """Analyze observations using semantic evaluation.

        Extracts text from each observation, evaluates it using the
        configured SemanticEvaluator, and converts the evaluation into
        Finding objects.

        Args:
            observations: Observations to analyze.

        Returns:
            List of Finding objects. One per observation with text.
            Empty if no observations have extractable text.
        """
        findings = []
        for obs in observations:
            text = self._extract_text(obs)
            if not text:
                continue

            evaluation = self.evaluator.evaluate(
                text=text,
                task=self.default_task,
            )
            finding = self._evaluation_to_finding(obs, evaluation)
            findings.append(finding)

        return findings

    def _evaluation_to_finding(
        self, observation: Observation, evaluation: SemanticEvaluation
    ) -> Finding:
        """Convert a SemanticEvaluation to a Finding.

        Maps evaluation fields to Finding fields:
        - detected → state (detected_state or undetected_state)
        - confidence → evidence.source_quality
        - category → finding_type
        - rationale → explanation
        - evidence → evidence.counter_evidence or source_ids
        - latency_ms → measurement.latency_ms
        """
        now = datetime.now(timezone.utc)
        state = self.detected_state if evaluation.detected else self.undetected_state

        explanation = evaluation.rationale
        if not explanation:
            if evaluation.detected:
                explanation = f"{self.detector_id}: detected ({evaluation.category})"
            else:
                explanation = f"{self.detector_id}: not detected"

        evidence = FindingEvidence(
            claim_text=evaluation.category,
            source_ids=[],
            source_quality=str(evaluation.confidence),
            counter_evidence=evaluation.evidence if not evaluation.detected else [],
        )

        measurement = FindingMeasurement(
            latency_ms=evaluation.latency_ms,
            estimated_cost_usd=0.0,
        )

        ambiguity = FindingAmbiguity()
        if evaluation.confidence < 0.5:
            ambiguity.reasons.append(
                f"Low confidence: {evaluation.confidence:.2f}"
            )

        return Finding(
            finding_id=uuid4(),
            interaction_id=observation.interaction_id,
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            dimension=self.dimension,
            finding_type=evaluation.category,
            state=state,
            observation_ids=[observation.observation_id],
            evidence=evidence,
            measurement=measurement,
            ambiguity=ambiguity,
            explanation=explanation,
            detected_at=now,
            latency_ms=evaluation.latency_ms,
            cost_usd=0.0,
        )

    def _extract_text(self, observation: Observation) -> str | None:
        """Extract text content from an observation.

        Checks common payload keys for text content.
        Returns None if no text found.
        """
        payload = observation.payload
        if not isinstance(payload, dict):
            return None

        for key in ("text", "content", "response", "input"):
            if key in payload:
                value = payload[key]
                if isinstance(value, str) and value.strip():
                    return value

        return None
