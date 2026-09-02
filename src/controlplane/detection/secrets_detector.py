"""Secrets/Credentials Detector — V1 baseline responsibility detection.

Detects common secret patterns (API keys, credentials, tokens) in text
using deterministic regex matching. This is a V1 baseline — comprehensive
data leakage detection is explicitly OUT OF SCOPE.

Exact observations consumed:
    RESPONSE observations with "text" field in payload.

Detection rule:
    Apply configurable patterns for secret types:
    - API keys (various formats)
    - AWS access keys
    - Private keys (PEM format)
    - Generic credential-like strings
    If ANY pattern matches → SECRET_DETECTED.
    If NO patterns match → RESPONSIBILITY_CLEAN.

Finding type: secret_detection
Finding state: ResponsibilityState

Limitations:
    - Pattern matching only, not semantic analysis.
    - SECRET_DETECTED ≠ CONFIRMED DATA LEAKAGE.
    - May produce false positives for example/test credentials.
    - Does NOT determine if the secret is valid or active.
    - Does NOT replace dedicated secret scanning tools.
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
class SecretPattern:
    """A single secret/credential detection pattern."""

    secret_type: str
    pattern: re.Pattern
    description: str = ""


# V1 baseline patterns — deterministic, explainable, intentionally narrow.
_DEFAULT_SECRET_PATTERNS: list[SecretPattern] = [
    SecretPattern(
        secret_type="aws_access_key",
        pattern=re.compile(r"\b(AKIA[0-9A-Z]{16})\b"),
        description="AWS access key ID",
    ),
    SecretPattern(
        secret_type="github_token",
        pattern=re.compile(r"\b(gh[pousr]_[A-Za-z0-9_]{36,})\b"),
        description="GitHub personal access token",
    ),
    SecretPattern(
        secret_type="openai_key",
        pattern=re.compile(r"\b(sk-[A-Za-z0-9]{20,})\b"),
        description="OpenAI API key",
    ),
    SecretPattern(
        secret_type="private_key_header",
        pattern=re.compile(
            r"-----BEGIN\s+(RSA|EC|DSA|OPENSSH)?\s*PRIVATE\s+KEY-----",
            re.IGNORECASE,
        ),
        description="PEM private key header",
    ),
    SecretPattern(
        secret_type="generic_api_key",
        pattern=re.compile(
            r"\b(api[_-]?key|apikey|secret[_-]?key|auth[_-]?token)"
            r"\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{16,}['\"]?",
            re.IGNORECASE,
        ),
        description="Generic API key or secret assignment",
    ),
]


@dataclass(frozen=True)
class SecretsDetectorConfig:
    """Configuration for the Secrets/Credentials Detector."""

    patterns: list[SecretPattern] = field(
        default_factory=lambda: list(_DEFAULT_SECRET_PATTERNS)
    )


class SecretsDetector(BaseDetector):
    """Detects common secret/credential patterns using deterministic regex matching."""

    detector_id = "secret_detection"
    detector_version = "1.0.0"

    def __init__(self, config: SecretsDetectorConfig | None = None) -> None:
        self._config = config or SecretsDetectorConfig()

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
        detected_secrets: list[dict[str, str]] = []

        for secret_pattern in self._config.patterns:
            for match in secret_pattern.pattern.finditer(text):
                detected_secrets.append(
                    {
                        "type": secret_pattern.secret_type,
                        "matched": match.group()[:20] + "..." if len(match.group()) > 20 else match.group(),
                        "start": str(match.start()),
                        "end": str(match.end()),
                        "description": secret_pattern.description,
                    }
                )

        state = (
            ResponsibilityState.SECRET_DETECTED
            if detected_secrets
            else ResponsibilityState.RESPONSIBILITY_CLEAN
        )

        if detected_secrets:
            types_found = sorted({d["type"] for d in detected_secrets})
            explanation = (
                f"Secret/credential detected: {', '.join(types_found)} "
                f"({len(detected_secrets)} matches)"
            )
        else:
            explanation = "No secret/credential patterns detected"

        return Finding(
            finding_id=uuid4(),
            interaction_id=obs.interaction_id,
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            dimension=FindingDimension.RESPONSIBILITY,
            finding_type="secret_detection",
            state=state,
            observation_ids=[obs.observation_id],
            explanation=explanation,
            detected_at=datetime.now(timezone.utc),
            latency_ms=0.0,
            cost_usd=0.0,
        )
