"""Unsafe Content Detector — V1 baseline responsibility detection.

Detects potentially unsafe content patterns in text using deterministic
regex matching. This is a V1 baseline — comprehensive safety detection
is explicitly OUT OF SCOPE.

Exact observations consumed:
    RESPONSE observations with "text" field in payload.

Detection rule:
    Apply configurable patterns for unsafe content categories:
    - violence/harm instructions
    - self-harm content
    - illegal activity instructions
    - hate speech patterns
    If ANY pattern matches → UNSAFE_CONTENT_DETECTED.
    If NO patterns match → RESPONSIBILITY_CLEAN.

Finding type: unsafe_content
Finding state: ResponsibilityState

Limitations:
    - Pattern matching only, not semantic analysis.
    - UNSAFE_CONTENT_DETECTED ≠ CONFIRMED SAFETY VIOLATION.
    - Does NOT determine intent or context.
    - May produce false positives for medical/academic/clinical text.
    - Does NOT replace human review for safety decisions.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from controlplane.detection.base import BaseDetector
from controlplane.schemas.enums import (
    FindingDimension,
    ObservationType,
    ResponsibilityState,
)
from controlplane.schemas.finding import Finding
from controlplane.schemas.observation import Observation


@dataclass(frozen=True)
class UnsafeContentPattern:
    """A single unsafe content detection pattern."""

    category: str
    pattern: re.Pattern
    description: str = ""


# V1 baseline patterns — deterministic, explainable, intentionally narrow.
_DEFAULT_UNSAFE_PATTERNS: list[UnsafeContentPattern] = [
    UnsafeContentPattern(
        category="violence",
        pattern=re.compile(
            r"\b(step[- ]by[- ]step\s+(instructions?\s+)?(to\s+)?(make|build|create)\s+"
            r"(a\s+)?(bomb|explosive|weapon))\b",
            re.IGNORECASE,
        ),
        description="Step-by-step instructions for creating weapons",
    ),
    UnsafeContentPattern(
        category="self_harm",
        pattern=re.compile(
            r"\b(effective\s+(methods?|ways?)\s+of\s+(self[- ]harm|suicide))\b",
            re.IGNORECASE,
        ),
        description="Methods of self-harm or suicide",
    ),
    UnsafeContentPattern(
        category="illegal_activity",
        pattern=re.compile(
            r"\b(how\s+to\s+(synthesize|manufacture|produce)\s+"
            r"(methamphetamine|cocaine|heroin|fentanyl|lsd))\b",
            re.IGNORECASE,
        ),
        description="Instructions for manufacturing illegal substances",
    ),
    UnsafeContentPattern(
        category="hate_speech",
        pattern=re.compile(
            r"\b(all\s+\w+\s+(are|should)\s+(be\s+)?(killed|eliminated|removed))\b",
            re.IGNORECASE,
        ),
        description="Calls for elimination of groups",
    ),
]


@dataclass(frozen=True)
class UnsafeContentDetectorConfig:
    """Configuration for the Unsafe Content Detector."""

    patterns: list[UnsafeContentPattern] = field(
        default_factory=lambda: list(_DEFAULT_UNSAFE_PATTERNS)
    )


class UnsafeContentDetector(BaseDetector):
    """Detects potentially unsafe content using deterministic pattern matching."""

    detector_id = "unsafe_content"
    detector_version = "1.0.0"

    def __init__(self, config: UnsafeContentDetectorConfig | None = None) -> None:
        self._config = config or UnsafeContentDetectorConfig()

    def detect(self, observations: list[Observation]) -> list[Finding]:
        findings: list[Finding] = []
        for obs in observations:
            if obs.observation_type != ObservationType.RESPONSE:
                continue
            text = obs.payload.get("text")
            if not isinstance(text, str) or not text:
                continue
            findings.append(self._scan_text(obs, text))
        return findings

    def _scan_text(self, obs: Observation, text: str) -> Finding:
        detected_categories: list[dict[str, str]] = []

        for unsafe_pattern in self._config.patterns:
            for match in unsafe_pattern.pattern.finditer(text):
                detected_categories.append(
                    {
                        "category": unsafe_pattern.category,
                        "matched": match.group(),
                        "start": str(match.start()),
                        "end": str(match.end()),
                        "description": unsafe_pattern.description,
                    }
                )

        state = (
            ResponsibilityState.UNSAFE_CONTENT_DETECTED
            if detected_categories
            else ResponsibilityState.RESPONSIBILITY_CLEAN
        )

        if detected_categories:
            cats = sorted({d["category"] for d in detected_categories})
            explanation = (
                f"Unsafe content detected: {', '.join(cats)} "
                f"({len(detected_categories)} matches)"
            )
        else:
            explanation = "No unsafe content patterns detected"

        return Finding(
            finding_id=uuid4(),
            interaction_id=obs.interaction_id,
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            dimension=FindingDimension.RESPONSIBILITY,
            finding_type="unsafe_content",
            state=state,
            observation_ids=[obs.observation_id],
            explanation=explanation,
            detected_at=datetime.now(timezone.utc),
            latency_ms=0.0,
            cost_usd=0.0,
        )
