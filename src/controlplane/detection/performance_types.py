"""Claim and Evidence types for the Evidence-Grounded Performance Detector.

Claim.evidence_keys maps to Evidence.evidence_id.
Evidence.claim_ids maps to Claim.claim_id (reverse provenance).
Comparison uses Evidence.structured_values, NOT Evidence.content.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID


@dataclass(frozen=True)
class Claim:
    claim_id: str
    interaction_id: UUID
    response_observation_id: UUID
    claim_text: str
    claim_type: str
    verifiability: str
    relevant_values: dict[str, str] = field(default_factory=dict)
    evidence_keys: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        valid_types = {"factual", "numeric", "temporal", "entity"}
        if self.claim_type not in valid_types:
            raise ValueError(
                f"Invalid claim_type {self.claim_type!r}. "
                f"Must be one of: {sorted(valid_types)}"
            )
        valid_verifiability = {"verifiable", "partially_verifiable", "unverifiable"}
        if self.verifiability not in valid_verifiability:
            raise ValueError(
                f"Invalid verifiability {self.verifiability!r}. "
                f"Must be one of: {sorted(valid_verifiability)}"
            )


@dataclass(frozen=True)
class Evidence:
    evidence_id: str
    source_id: str
    source_type: str
    content: str
    structured_values: dict[str, str] = field(default_factory=dict)
    claim_ids: list[str] = field(default_factory=list)
    provenance: str = ""
    retrieved_at: datetime | None = None
    freshness: str | None = None
    authority_class: str = "unknown"

    def __post_init__(self) -> None:
        valid_source_types = {"authoritative", "enterprise", "retrieved", "benchmark"}
        if self.source_type not in valid_source_types:
            raise ValueError(
                f"Invalid source_type {self.source_type!r}. "
                f"Must be one of: {sorted(valid_source_types)}"
            )
        valid_authority = {"primary", "secondary", "tertiary", "unknown"}
        if self.authority_class not in valid_authority:
            raise ValueError(
                f"Invalid authority_class {self.authority_class!r}. "
                f"Must be one of: {sorted(valid_authority)}"
            )
