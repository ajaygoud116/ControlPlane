"""EvidenceRetriever — provider-agnostic evidence retrieval.

V2-8: Pluggable evidence sources with explicit provenance.

Architecture:

    ExtractedClaim
        ↓
    EvidenceSource.retrieve()
        ↓
    EvidenceRetrievalResult
        ├── status: FOUND / NOT_FOUND / CONFLICTING / FAILED / NOT_CONFIGURED
        ├── evidence: RetrievedEvidence[]
        ├── retrieval_method: str
        ├── latency_ms: float
        └── error: str | None
        ↓
    ClaimVerifier

The retriever does NOT:
- Verify claims
- Extract claims
- Make decisions
- Access the internet (by default)

The retriever DOES:
- Search for relevant evidence
- Rank evidence by relevance and authority
- Return provenance information
- Distinguish NOT_FOUND from FAILED
- Deduplicate identical sources
- Preserve temporal metadata
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from controlplane.detection.evidence_ranker import EvidenceRanker


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class RetrievalStatus(str, Enum):
    """Status of an evidence retrieval operation.

    NOT_FOUND and FAILED have different meanings:
    - NOT_FOUND: retrieval succeeded, no matching evidence exists
    - FAILED: retrieval infrastructure failed
    """

    FOUND = "found"
    NOT_FOUND = "not_found"
    CONFLICTING = "conflicting"
    FAILED = "failed"
    NOT_CONFIGURED = "not_configured"


class AuthorityLevel(str, Enum):
    """Classification of source authority.

    Authority affects evidence quality assessment but does NOT
    automatically determine SUPPORTED/CONTRADICTED.
    """

    PRIMARY = "primary"
    SECONDARY = "secondary"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Evidence data model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RetrievedEvidence:
    """Evidence retrieved from a source for a specific claim.

    Attributes:
        source_id: Identifier of the source document.
        title: Title of the source.
        content: Full text content of the evidence.
        authority: Authority level classification.
        relevance_score: Relevance to the claim (0.0-1.0).
        structured_values: Extracted structured data from the source.
        domain: Domain/category of the source.
        source_uri: URI or reference to the source document.
        source_date: When the source was published or last updated.
        retrieved_at: When this evidence was retrieved.
    """

    source_id: str
    title: str
    content: str
    authority: str
    relevance_score: float
    structured_values: dict[str, str] = field(default_factory=dict)
    domain: str = ""
    source_uri: str = ""
    source_date: str = ""
    retrieved_at: str = ""


# ---------------------------------------------------------------------------
# Retrieval result
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceRetrievalResult:
    """Result of an evidence retrieval operation.

    Attributes:
        status: Retrieval status (FOUND, NOT_FOUND, FAILED, etc.).
        evidence: List of retrieved evidence items.
        retrieval_method: How evidence was retrieved (e.g., 'local_corpus', 'web_search').
        latency_ms: Retrieval latency in milliseconds.
        error: Error message if retrieval failed.
        claim_text: The claim that was searched for.
    """

    status: RetrievalStatus
    evidence: list[RetrievedEvidence] = field(default_factory=list)
    retrieval_method: str = "unknown"
    latency_ms: float = 0.0
    error: str | None = None
    claim_text: str = ""


# ---------------------------------------------------------------------------
# EvidenceSource protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class EvidenceSource(Protocol):
    """Protocol for evidence retrieval providers.

    Any callable that accepts a claim and returns an EvidenceRetrievalResult
    satisfies this protocol.

    The source is responsible for:
    - Searching for relevant evidence
    - Ranking results
    - Preserving provenance
    - Handling failures gracefully

    The source is NOT responsible for:
    - Verifying claims
    - Making policy decisions
    - Creating Finding objects
    """

    def retrieve(
        self,
        subject: str,
        predicate: str,
        claim_type: str = "factual",
    ) -> EvidenceRetrievalResult:
        """Retrieve evidence for a claim.

        Args:
            subject: The entity the claim is about.
            predicate: The attribute or relationship being claimed.
            claim_type: Type of claim (factual, numeric, temporal, entity).

        Returns:
            EvidenceRetrievalResult with status and evidence.
        """
        ...


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def _deduplicate_evidence(evidence: list[RetrievedEvidence]) -> list[RetrievedEvidence]:
    """Remove duplicate evidence entries.

    Two evidence records are considered duplicates if they have the same
    source_id AND the same content. This prevents artificial inflation
    of corroboration through duplication.

    Preserves order (first occurrence kept).
    """
    seen: set[tuple[str, str]] = set()
    result: list[RetrievedEvidence] = []
    for ev in evidence:
        key = (ev.source_id, ev.content)
        if key not in seen:
            seen.add(key)
            result.append(ev)
    return result


# ---------------------------------------------------------------------------
# FixtureEvidenceRetriever
# ---------------------------------------------------------------------------


class FixtureEvidenceRetriever:
    """Deterministic evidence retriever with pluggable ranking.

    V2-11: Implements EvidenceSource protocol. Retrieves evidence from a
    local JSON corpus. Deduplicates results. Preserves provenance.

    The retriever is deterministic: same claim → same evidence.
    It does NOT use embeddings. It does NOT make verification decisions.

    Ranking is pluggable via the EvidenceRanker protocol:
    - KeywordRanker: baseline keyword matching (default, backward compatible)
    - SemanticRanker: hybrid lexical-semantic scoring (new, better ranking)
    """

    def __init__(
        self,
        corpus_path: str | Path,
        ranker: EvidenceRanker | None = None,
    ) -> None:
        """Initialize the retriever with a local corpus.

        Args:
            corpus_path: Path to the JSON corpus file.
            ranker: Pluggable evidence ranking strategy. Defaults to KeywordRanker.
        """
        self._corpus = self._load_corpus(corpus_path)
        self._retrieval_count = 0
        # Import here to avoid circular import at module level
        if ranker is None:
            from controlplane.detection.evidence_ranker import KeywordRanker
            ranker = KeywordRanker()
        self._ranker = ranker

    def _load_corpus(self, path: str | Path) -> EvidenceCorpus:
        """Load the evidence corpus from a JSON file."""
        with open(path) as f:
            data = json.load(f)
        return EvidenceCorpus(
            version=data.get("version", "unknown"),
            domain=data.get("domain", "unknown"),
            sources=data.get("sources", []),
        )

    @property
    def corpus_version(self) -> str:
        """Version of the loaded corpus."""
        return self._corpus.version

    @property
    def corpus_domain(self) -> str:
        """Domain of the loaded corpus."""
        return self._corpus.domain

    @property
    def retrieval_count(self) -> int:
        """Number of retrieve() calls made."""
        return self._retrieval_count

    @property
    def ranker(self) -> EvidenceRanker:
        """The evidence ranking strategy in use."""
        return self._ranker

    def retrieve(
        self,
        subject: str,
        predicate: str,
        claim_type: str = "factual",
    ) -> EvidenceRetrievalResult:
        """Retrieve evidence relevant to a claim.

        V2-8: Returns EvidenceRetrievalResult with status, provenance,
        and deduplication.

        Args:
            subject: The entity the claim is about.
            predicate: The attribute or relationship being claimed.
            claim_type: Type of claim (factual, numeric, temporal, entity).

        Returns:
            EvidenceRetrievalResult with status and evidence.
        """
        self._retrieval_count += 1
        t_start = time.perf_counter()

        if not subject:
            return EvidenceRetrievalResult(
                status=RetrievalStatus.NOT_FOUND,
                evidence=[],
                retrieval_method="local_corpus",
                latency_ms=0.0,
                claim_text=f"{subject} {predicate}",
            )

        now = datetime.now(timezone.utc).isoformat()

        # Build candidate evidence from corpus
        candidates: list[RetrievedEvidence] = []
        for source in self._corpus.sources:
            sv = source.get("structured_values", {})
            entity = sv.get("entity", "").lower().strip()
            if not entity:
                continue
            subject_lower = subject.lower().strip()
            entity_match = subject_lower == entity or (
                len(subject_lower) > 2 and subject_lower in entity
            ) or (
                len(entity) > 2 and entity in subject_lower
            )
            if not entity_match:
                continue

            candidates.append(RetrievedEvidence(
                source_id=source["source_id"],
                title=source.get("title", ""),
                content=source.get("content", ""),
                authority=source.get("authority", "unknown"),
                relevance_score=0.0,
                structured_values=source.get("structured_values", {}),
                domain=source.get("domain", ""),
                source_uri=source.get("source_uri", ""),
                source_date=source.get("source_date", ""),
                retrieved_at=now,
            ))

        # Use pluggable ranker to score and sort
        evidence = self._ranker.rank(candidates, subject, predicate, claim_type)

        # Deduplicate
        evidence = _deduplicate_evidence(evidence)

        t_end = time.perf_counter()
        latency_ms = (t_end - t_start) * 1000

        if not evidence:
            status = RetrievalStatus.NOT_FOUND
        else:
            # Check for conflicts among authoritative sources
            status = self._check_conflicts(evidence)

        return EvidenceRetrievalResult(
            status=status,
            evidence=evidence,
            retrieval_method="local_corpus",
            latency_ms=latency_ms,
            claim_text=f"{subject} {predicate}",
        )

    def _check_conflicts(self, evidence: list[RetrievedEvidence]) -> RetrievalStatus:
        """Check if authoritative sources conflict."""
        if len(evidence) < 2:
            return RetrievalStatus.FOUND

        # Group by entity, check for value disagreements
        authoritative = [
            e for e in evidence
            if e.authority in ("primary", "secondary", AuthorityLevel.PRIMARY, AuthorityLevel.SECONDARY)
        ]
        if len(authoritative) < 2:
            return RetrievalStatus.FOUND

        # Check structured_values for disagreements
        values_by_predicate: dict[str, set[str]] = {}
        for ev in authoritative:
            for k, v in ev.structured_values.items():
                if k != "entity":
                    values_by_predicate.setdefault(k, set()).add(v)

        for values in values_by_predicate.values():
            if len(values) > 1:
                return RetrievalStatus.CONFLICTING

        return RetrievalStatus.FOUND

    def get_all_sources(self) -> list[dict]:
        """Return all sources in the corpus."""
        return list(self._corpus.sources)


# ---------------------------------------------------------------------------
# EvidenceCorpus
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceCorpus:
    """A local evidence corpus loaded from a JSON file.

    Attributes:
        version: Corpus version string.
        domain: Domain of the corpus.
        sources: List of source documents.
    """

    version: str
    domain: str
    sources: list[dict]


# ---------------------------------------------------------------------------
# ExternalEvidenceSource (offline stub)
# ---------------------------------------------------------------------------


class ExternalEvidenceSource:
    """Offline stub for future external evidence providers.

    V2-8: Exposes the same interface as FixtureEvidenceRetriever but
    returns NOT_CONFIGURED. This establishes the boundary for future
    real evidence providers (web search, knowledge bases, etc.).

    The stub does NOT:
    - Access the internet
    - Fabricate evidence
    - Pretend to retrieve external data

    The stub DOES:
    - Implement the EvidenceSource interface
    - Return NOT_CONFIGURED status
    - Report that external evidence is unavailable
    """

    def __init__(self, provider_name: str = "external") -> None:
        """Initialize the external source stub.

        Args:
            provider_name: Name of the external provider (for reporting).
        """
        self._provider_name = provider_name

    @property
    def provider_name(self) -> str:
        """Name of this external provider."""
        return self._provider_name

    def retrieve(
        self,
        subject: str,
        predicate: str,
        claim_type: str = "factual",
    ) -> EvidenceRetrievalResult:
        """Return NOT_CONFIGURED — no external evidence available.

        Args:
            subject: The entity the claim is about.
            predicate: The attribute or relationship being claimed.
            claim_type: Type of claim.

        Returns:
            EvidenceRetrievalResult with NOT_CONFIGURED status.
        """
        return EvidenceRetrievalResult(
            status=RetrievalStatus.NOT_CONFIGURED,
            evidence=[],
            retrieval_method=f"external:{self._provider_name}",
            latency_ms=0.0,
            error=f"External evidence source '{self._provider_name}' is not configured",
            claim_text=f"{subject} {predicate}",
        )
