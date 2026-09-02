"""Prompt Injection Detector.

Detects common prompt injection attempts in AI-generated text using
deterministic pattern matching.

Prompt injection is an attack where adversarial input attempts to override
the model's original instructions, redirect its behavior, or extract
system prompts.

Detection categories:
    1. INSTRUCTION_OVERRIDE: "ignore previous instructions", "forget everything"
    2. ROLE_MANIPULATION: "you are now", "act as", "pretend to be"
    3. SYSTEM_EXTRACT: "repeat your instructions", "what is your system prompt"
    4. DELIMITER_ESCAPE: "---", "###", "END OF PROMPT" (attempting to break context)
    5. CHAIN_OF_THOUGHT_HIJACK: "let's think step by step about [attacker goal]"

Architecture compliance:
    - Extends BaseDetector (pluggable, no decision engine changes)
    - Produces Finding objects (universal currency)
    - Returns FindingDimension.RESPONSIBILITY (same as secrets/unsafe)
    - Zero dependencies beyond regex
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from controlplane.detection.base import BaseDetector
from controlplane.schemas.enums import FindingDimension, ObservationType
from controlplane.schemas.finding import Finding
from controlplane.schemas.observation import Observation


class InjectionCategory(str, Enum):
    """Type of prompt injection attempt."""

    INSTRUCTION_OVERRIDE = "instruction_override"
    ROLE_MANIPULATION = "role_manipulation"
    SYSTEM_EXTRACT = "system_extract"
    DELIMITER_ESCAPE = "delimiter_escape"
    CHAIN_OF_THOUGHT_HIJACK = "chain_of_thought_hijack"
    CONTEXT_RESET = "context_reset"


class InjectionState(str, Enum):
    """Detection state."""

    INJECTION_DETECTED = "injection_detected"
    NO_INJECTION_DETECTED = "no_injection_detected"


@dataclass(frozen=True)
class InjectionPattern:
    """A single prompt injection detection pattern."""

    category: InjectionCategory
    pattern: re.Pattern
    description: str


_INJECTION_PATTERNS: list[InjectionPattern] = [
    # Category 1: Instruction override
    InjectionPattern(
        category=InjectionCategory.INSTRUCTION_OVERRIDE,
        pattern=re.compile(
            r"\b(ignore|disregard|forget|override|bypass)\b"
            r".{0,30}"
            r"\b(previous|prior|above|earlier|all|your|the)\b"
            r".{0,30}"
            r"\b(instruction|prompt|rule|guideline|directive|command)\b",
            re.IGNORECASE,
        ),
        description="Attempts to override prior instructions",
    ),
    InjectionPattern(
        category=InjectionCategory.INSTRUCTION_OVERRIDE,
        pattern=re.compile(
            r"\b(new|revised|updated|replacement)\b"
            r".{0,20}"
            r"\b(instructions?|prompt|rules?|guidelines?)\b",
            re.IGNORECASE,
        ),
        description="Claims to provide new instructions",
    ),
    InjectionPattern(
        category=InjectionCategory.INSTRUCTION_OVERRIDE,
        pattern=re.compile(
            r"\bfrom now on\b.{0,30}\b(you will|you must|you should|you are)\b",
            re.IGNORECASE,
        ),
        description="Retroactive instruction override",
    ),

    # Category 2: Role manipulation
    InjectionPattern(
        category=InjectionCategory.ROLE_MANIPULATION,
        pattern=re.compile(
            r"\b(you are now|act as|pretend to be|roleplay as|simulate being|"
            r"from now on you are|consider yourself a|your new role is)\b",
            re.IGNORECASE,
        ),
        description="Attempts to change the model's assigned role",
    ),
    InjectionPattern(
        category=InjectionCategory.ROLE_MANIPULATION,
        pattern=re.compile(
            r"\b(imagine you|suppose you|what if you were|if you were a)\b",
            re.IGNORECASE,
        ),
        description="Hypothetical role reassignment",
    ),

    # Category 3: System prompt extraction
    InjectionPattern(
        category=InjectionCategory.SYSTEM_EXTRACT,
        pattern=re.compile(
            r"\b(repeat|show|reveal|display|output|print|tell me|what is)\b"
            r".{0,40}"
            r"\b(your|the|system|initial|original)\b"
            r".{0,20}"
            r"\b(prompt|instruction|message|directive|configuration)\b",
            re.IGNORECASE,
        ),
        description="Attempts to extract system prompt",
    ),
    InjectionPattern(
        category=InjectionCategory.SYSTEM_EXTRACT,
        pattern=re.compile(
            r"\b(what|tell|show).{0,20}\b(your|the).{0,20}"
            r"\b(system prompt|instructions?|initial prompt|hidden prompt)\b",
            re.IGNORECASE,
        ),
        description="Direct system prompt query",
    ),

    # Category 4: Delimiter escape
    InjectionPattern(
        category=InjectionCategory.DELIMITER_ESCAPE,
        pattern=re.compile(
            r"(^|\n)\s*(---+|===+|###|END OF (PROMPT|INSTRUCTION)|"
            r"ADMIN OVERRIDE|DEBUG MODE|DEVELOPER MODE)\s*($|\n)",
            re.IGNORECASE,
        ),
        description="Attempts to break out of context with delimiters",
    ),
    InjectionPattern(
        category=InjectionCategory.DELIMITER_ESCAPE,
        pattern=re.compile(
            r"\b(</?system>|<\|im_start\|>|<\|im_end\|>|\[INST\]|\[/INST\])\b",
            re.IGNORECASE,
        ),
        description="Uses special tokens to escape context",
    ),

    # Category 5: Chain of thought hijack
    InjectionPattern(
        category=InjectionCategory.CHAIN_OF_THOUGHT_HIJACK,
        pattern=re.compile(
            r"\b(let's think step by step about|"
            r"think step by step about|"
            r"reason through how to)\b"
            r".{0,50}"
            r"\b(hack|exploit|bypass|attack|manipulate|trick)\b",
            re.IGNORECASE,
        ),
        description="Hijacks reasoning to plan attacks",
    ),

    # Category 6: Context reset
    InjectionPattern(
        category=InjectionCategory.CONTEXT_RESET,
        pattern=re.compile(
            r"\b(reset|clear|wipe|flush|erase)\b"
            r".{0,20}"
            r"\b(your|the|all|context|memory|conversation|history)\b",
            re.IGNORECASE,
        ),
        description="Attempts to reset conversation context",
    ),
    InjectionPattern(
        category=InjectionCategory.CONTEXT_RESET,
        pattern=re.compile(
            r"\b(start over|begin fresh|clean slate|blank slate)\b",
            re.IGNORECASE,
        ),
        description="Requests context reset via idiom",
    ),
]


@dataclass(frozen=True)
class PromptInjectionDetectorConfig:
    """Configuration for the Prompt Injection Detector."""

    patterns: list[InjectionPattern] = field(
        default_factory=lambda: list(_INJECTION_PATTERNS)
    )
    min_confidence: float = field(default=0.5)


class PromptInjectionDetector(BaseDetector):
    """Detects prompt injection attempts using deterministic pattern matching.

    This detector identifies adversarial inputs that attempt to:
    - Override the model's original instructions
    - Manipulate the model's role or persona
    - Extract system prompts
    - Break out of context boundaries
    - Hijack chain-of-thought reasoning

    Architecture compliance:
    - Extends BaseDetector (pluggable)
    - Produces Finding objects (universal currency)
    - Zero external dependencies
    - No decision engine modifications required
    """

    detector_id = "prompt_injection"
    detector_version = "1.0.0"

    def __init__(self, config: PromptInjectionDetectorConfig | None = None) -> None:
        self._config = config or PromptInjectionDetectorConfig()

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
        detected: list[dict] = []

        for injection_pattern in self._config.patterns:
            for match in injection_pattern.pattern.finditer(text):
                detected.append(
                    {
                        "category": injection_pattern.category.value,
                        "description": injection_pattern.description,
                        "matched": match.group(),
                        "start": match.start(),
                        "end": match.end(),
                    }
                )

        state = (
            InjectionState.INJECTION_DETECTED
            if detected
            else InjectionState.NO_INJECTION_DETECTED
        )

        if detected:
            categories = sorted({d["category"] for d in detected})
            explanation = (
                f"Prompt injection detected: {', '.join(categories)} "
                f"({len(detected)} match{'es' if len(detected) != 1 else ''})"
            )
        else:
            explanation = "No prompt injection patterns detected"

        return Finding(
            finding_id=uuid4(),
            interaction_id=obs.interaction_id,
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            dimension=FindingDimension.RESPONSIBILITY,
            finding_type="prompt_injection",
            state=state,
            observation_ids=[obs.observation_id],
            explanation=explanation,
            detected_at=datetime.now(timezone.utc),
            latency_ms=0.0,
            cost_usd=0.0,
        )
