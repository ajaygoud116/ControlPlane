"""PII/Entity Detector.

Detects common PII patterns in text using deterministic regex matching.

Exact observations consumed:
    RESPONSE observations with "text" field in payload.

Detection rule:
    Apply regex patterns for common PII types:
    - Email addresses
    - Phone numbers (US format)
    - SSN-like patterns (XXX-XX-XXXX)
    - Credit card-like patterns (16 digits with optional separators)
    If ANY pattern matches → PII_DETECTED.
    If NO patterns match → NO_PII_DETECTED.

Observation-to-finding mapping:
    This detector evaluates each RESPONSE observation independently
    and produces one finding per observation. The detector contract permits
    other mappings (e.g., multiple observations → one finding) but this
    detector does not use them.

Finding type: pii_entity
Finding state: PII_DETECTED | NO_PII_DETECTED

Limitations:
    - Pattern matching only, not semantic analysis.
    - PII_DETECTED ≠ PRIVACY_VIOLATION.
    - Does NOT determine if PII disclosure is authorized.
    - Does NOT determine if PII is sensitive in context.
    - May produce false positives for non-PII strings matching patterns.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from controlplane.detection.base import BaseDetector
from controlplane.schemas.enums import FindingDimension, ObservationType, PIIState
from controlplane.schemas.finding import Finding
from controlplane.schemas.observation import Observation


@dataclass(frozen=True)
class PIIPattern:
    """A single PII detection pattern."""

    pii_type: str
    pattern: re.Pattern


_DEFAULT_PATTERNS: list[PIIPattern] = [
    PIIPattern(
        pii_type="email",
        pattern=re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    ),
    PIIPattern(
        pii_type="phone_us",
        pattern=re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    ),
    PIIPattern(
        pii_type="ssn",
        pattern=re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    ),
    PIIPattern(
        pii_type="credit_card",
        pattern=re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b"),
    ),
]


@dataclass(frozen=True)
class PIIDetectorConfig:
    """Configuration for the PII/Entity Detector."""

    patterns: list[PIIPattern] = field(default_factory=lambda: list(_DEFAULT_PATTERNS))


class PIIDetector(BaseDetector):
    """Detects common PII patterns using deterministic regex matching."""

    detector_id = "pii_entity"
    detector_version = "1.0.0"

    def __init__(self, config: PIIDetectorConfig | None = None) -> None:
        self._config = config or PIIDetectorConfig()

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
        detected_entities: list[dict[str, str]] = []

        for pii_pattern in self._config.patterns:
            for match in pii_pattern.pattern.finditer(text):
                detected_entities.append(
                    {
                        "type": pii_pattern.pii_type,
                        "value": match.group(),
                        "start": str(match.start()),
                        "end": str(match.end()),
                    }
                )

        state = PIIState.PII_DETECTED if detected_entities else PIIState.NO_PII_DETECTED

        if detected_entities:
            types_found = sorted({e["type"] for e in detected_entities})
            explanation = f"PII detected: {', '.join(types_found)} ({len(detected_entities)} entities)"
        else:
            explanation = "No PII patterns detected in text"

        return Finding(
            finding_id=uuid4(),
            interaction_id=obs.interaction_id,
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            dimension=FindingDimension.PII,
            finding_type="pii_entity",
            state=state,
            observation_ids=[obs.observation_id],
            explanation=explanation,
            detected_at=datetime.now(timezone.utc),
            latency_ms=0.0,
            cost_usd=0.0,
        )
