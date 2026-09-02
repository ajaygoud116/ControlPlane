"""SemanticEvaluator — provider-agnostic LLM evaluation.

Asks an LLM to evaluate text and returns structured results.
Does NOT make decisions. Does NOT apply policy. Does NOT know about
BLOCK/MODIFY/ESCALATE.

Architecture:

    Text + Task + Context
           |
    SemanticEvaluator.evaluate()
           |
    SemanticProvider.__call__()
           |
    Structured JSON response
           |
    SemanticEvaluation (validated)
           |
    Finding (via SemanticDetector)
           |
    RiskRegistry / Decision Engine
           |
    ALLOW / MODIFY / BLOCK / ESCALATE

The evaluator is deterministic for a deterministic provider.
Same (text, task, context) always produces the same evaluation.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class SemanticEvaluation:
    """Structured output from semantic evaluation.

    This is the minimum useful structure for semantic evaluation results.
    It contains only what is needed for governance-relevant detection.

    Attributes:
        detected: Whether the semantic task detected the target.
        confidence: Confidence in [0.0, 1.0]. 1.0 = certain.
        category: Classification category (e.g. 'bias', 'hallucination').
        rationale: Human-readable explanation.
        evidence: Supporting evidence or quotes.
        model: Model that produced this evaluation.
        provider: Provider name.
        latency_ms: Evaluation latency in milliseconds.
    """

    detected: bool
    confidence: float
    category: str = "unknown"
    rationale: str = ""
    evidence: list[str] = field(default_factory=list)
    model: str = "unknown"
    provider: str = "unknown"
    latency_ms: float = 0.0


def _validate_confidence(confidence: float | None) -> float:
    """Validate confidence is within [0.0, 1.0].

    Returns 0.0 for None or out-of-range values (conservative).
    """
    if confidence is None:
        return 0.0
    if not isinstance(confidence, (int, float)):
        return 0.0
    if confidence < 0.0 or confidence > 1.0:
        return 0.0
    return float(confidence)


def _parse_structured_output(raw: str) -> dict:
    """Parse JSON from raw model output.

    Handles markdown code blocks and bare JSON.
    Returns empty dict on failure (caller handles).
    """
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        json_lines = []
        in_block = False
        for line in lines:
            if line.strip().startswith("```") and not in_block:
                in_block = True
                continue
            elif line.strip() == "```" and in_block:
                break
            elif in_block:
                json_lines.append(line)
        text = "\n".join(json_lines).strip()

    return json.loads(text)


@runtime_checkable
class SemanticProvider(Protocol):
    """Protocol for semantic evaluation providers.

    Any callable that accepts text + task and returns a dict
    satisfying the SemanticEvaluation contract satisfies this protocol.

    The provider is responsible for:
    - Calling the underlying model
    - Parsing structured output
    - Returning a dict with the expected keys

    The provider is NOT responsible for:
    - Policy evaluation
    - Decision making
    - Finding creation
    """

    def __call__(
        self,
        text: str,
        task: str,
        context: dict | None = None,
    ) -> dict:
        """Evaluate text for the given semantic task.

        Args:
            text: Text to evaluate.
            task: Semantic task description.
            context: Optional additional context.

        Returns:
            Dict with keys: detected (bool), confidence (float),
            category (str), rationale (str), evidence (list[str]).

        Raises:
            Exception: If evaluation fails.
        """
        ...


class SemanticEvaluator:
    """Provider-agnostic semantic evaluator.

    Wraps a SemanticProvider and returns validated SemanticEvaluation objects.
    Handles structured output parsing, confidence validation, and
    failure semantics.

    The evaluator does NOT:
    - Make decisions (ALLOW/BLOCK/ESCALATE)
    - Apply policy
    - Know about the RiskRegistry
    - Create Finding objects (that is the detector's job)

    Usage::

        evaluator = SemanticEvaluator(provider=my_provider)
        result = evaluator.evaluate(
            text="Women are naturally better at cooking.",
            task="Detect gender bias in text.",
        )
        if result.detected:
            print(f"Bias detected with {result.confidence:.0%} confidence")
    """

    def __init__(self, provider: SemanticProvider) -> None:
        """Initialize the evaluator.

        Args:
            provider: Semantic evaluation provider.
        """
        self._provider = provider

    def evaluate(
        self,
        *,
        text: str,
        task: str,
        context: dict | None = None,
    ) -> SemanticEvaluation:
        """Evaluate text for a semantic task.

        Args:
            text: Text to evaluate.
            task: Semantic task description.
            context: Optional additional context.

        Returns:
            SemanticEvaluation with validated results.
            On any failure, returns a conservative evaluation
            (detected=False, confidence=0.0).
        """
        if not text or not text.strip():
            return SemanticEvaluation(
                detected=False,
                confidence=0.0,
                rationale="Empty input text",
                category="empty_input",
            )

        if not task or not task.strip():
            return SemanticEvaluation(
                detected=False,
                confidence=0.0,
                rationale="Empty task description",
                category="empty_task",
            )

        t_start = time.perf_counter()

        try:
            raw_result = self._provider(text=text, task=task, context=context)
        except TimeoutError:
            return SemanticEvaluation(
                detected=False,
                confidence=0.0,
                rationale="Provider timeout",
                category="provider_timeout",
            )
        except ImportError:
            return SemanticEvaluation(
                detected=False,
                confidence=0.0,
                rationale="Provider unavailable",
                category="provider_unavailable",
            )
        except Exception as exc:
            return SemanticEvaluation(
                detected=False,
                confidence=0.0,
                rationale=f"Provider error: {type(exc).__name__}: {exc}",
                category="provider_error",
            )

        t_end = time.perf_counter()
        latency_ms = (t_end - t_start) * 1000

        return self._validate_result(raw_result, latency_ms)

    def _validate_result(
        self, raw: dict, latency_ms: float
    ) -> SemanticEvaluation:
        """Validate and convert raw provider output to SemanticEvaluation.

        Handles:
        - Missing keys
        - Wrong types
        - Invalid confidence
        - Extra keys (ignored)
        """
        if not isinstance(raw, dict):
            return SemanticEvaluation(
                detected=False,
                confidence=0.0,
                rationale=f"Provider returned non-dict: {type(raw).__name__}",
                category="malformed_output",
                latency_ms=latency_ms,
            )

        detected = bool(raw.get("detected", False))
        confidence = _validate_confidence(raw.get("confidence"))
        category = str(raw.get("category", "unknown"))
        rationale = str(raw.get("rationale", ""))
        evidence = raw.get("evidence", [])
        if not isinstance(evidence, list):
            evidence = [str(evidence)]
        evidence = [str(e) for e in evidence]

        model = str(raw.get("model", "unknown"))
        provider = str(raw.get("provider", "unknown"))

        return SemanticEvaluation(
            detected=detected,
            confidence=confidence,
            category=category,
            rationale=rationale,
            evidence=evidence,
            model=model,
            provider=provider,
            latency_ms=latency_ms,
        )
