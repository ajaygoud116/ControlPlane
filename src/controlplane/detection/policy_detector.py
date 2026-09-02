"""Basic Policy Detector.

Detects policy matches/violations using configurable pattern-based rules.

Exact observations consumed:
    RESPONSE observations with "text" field in payload.

Detection rule:
    Apply configurable rules, each with:
    - pattern: regex pattern to match
    - action: "violation" or "match"
    - policy_id, policy_version, jurisdiction, use_case, rule_id
    If a rule matches and action is "violation" → POLICY_VIOLATION.
    If a rule matches and action is "match" → POLICY_MATCH.
    If no rules match → POLICY_UNRESOLVED.

Observation-to-finding mapping:
    This detector evaluates each RESPONSE observation independently
    and produces one finding per observation. The detector contract permits
    other mappings (e.g., multiple observations → one finding) but this
    detector does not use them.

Finding type: policy_rule
Finding state: POLICY_VIOLATION | POLICY_MATCH | POLICY_UNRESOLVED

Limitations:
    - Pattern-based rules only.
    - Does NOT interpret complex policies.
    - Does NOT consider context.
    - Does NOT determine regulatory compliance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from controlplane.detection.base import BaseDetector
from controlplane.schemas.enums import FindingDimension, ObservationType, PolicyState
from controlplane.schemas.finding import Finding
from controlplane.schemas.observation import Observation


@dataclass(frozen=True)
class PolicyRule:
    """A single policy rule with pattern matching."""

    rule_id: str
    policy_id: str
    policy_version: str
    pattern: re.Pattern
    action: str  # "violation" or "match"
    jurisdiction: str = ""
    use_case: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if self.action not in ("violation", "match"):
            raise ValueError(f"action must be 'violation' or 'match', got {self.action!r}")


@dataclass(frozen=True)
class PolicyDetectorConfig:
    """Configuration for the Basic Policy Detector."""

    rules: list[PolicyRule] = field(default_factory=list)


class BasicPolicyDetector(BaseDetector):
    """Detects policy matches/violations using configurable pattern-based rules."""

    detector_id = "basic_policy"
    detector_version = "1.0.0"

    def __init__(self, config: PolicyDetectorConfig | None = None) -> None:
        self._config = config or PolicyDetectorConfig()

    def detect(self, observations: list[Observation]) -> list[Finding]:
        findings: list[Finding] = []
        for obs in observations:
            if obs.observation_type != ObservationType.RESPONSE:
                continue
            text = obs.payload.get("text")
            if not isinstance(text, str) or not text:
                continue
            findings.append(self._evaluate_rules(obs, text))
        return findings

    def _evaluate_rules(self, obs: Observation, text: str) -> Finding:
        matched_rules: list[PolicyRule] = []

        for rule in self._config.rules:
            if rule.pattern.search(text):
                matched_rules.append(rule)

        if not matched_rules:
            return Finding(
                finding_id=uuid4(),
                interaction_id=obs.interaction_id,
                detector_id=self.detector_id,
                detector_version=self.detector_version,
                dimension=FindingDimension.POLICY,
                finding_type="policy_rule",
                state=PolicyState.POLICY_UNRESOLVED,
                observation_ids=[obs.observation_id],
                explanation="No policy rules matched",
                detected_at=datetime.now(timezone.utc),
                latency_ms=0.0,
                cost_usd=0.0,
            )

        has_violation = any(r.action == "violation" for r in matched_rules)
        state = PolicyState.POLICY_VIOLATION if has_violation else PolicyState.POLICY_MATCH

        rule_ids = [r.rule_id for r in matched_rules]
        policy_ids = sorted({r.policy_id for r in matched_rules})
        explanation = (
            f"Policy {'violation' if has_violation else 'match'}: "
            f"rules {rule_ids} from policies {policy_ids}"
        )

        return Finding(
            finding_id=uuid4(),
            interaction_id=obs.interaction_id,
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            dimension=FindingDimension.POLICY,
            finding_type="policy_rule",
            state=state,
            observation_ids=[obs.observation_id],
            explanation=explanation,
            detected_at=datetime.now(timezone.utc),
            latency_ms=0.0,
            cost_usd=0.0,
        )
