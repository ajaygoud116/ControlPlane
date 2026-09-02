"""EvidenceRanker — pluggable evidence ranking strategies.

V2-11: Semantic/Vector Evidence Retrieval.

Provides deterministic, offline evidence ranking without external embeddings.

Architecture:

    RetrievedEvidence[] + Claim
        ↓
    EvidenceRanker.rank()
        ↓
    Ranked RetrievedEvidence[]

Ranking strategies:
- KeywordRanker: baseline keyword matching (existing behavior)
- SemanticRanker: hybrid lexical-semantic scoring

The ranker does NOT:
- Verify claims
- Make decisions
- Access the internet
- Use external embedding APIs

The ranker DOES:
- Score evidence relevance to a claim
- Handle synonym/paraphrase variation
- Handle numeric/entity matching
- Preserve provenance
- Operate deterministically
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from controlplane.detection.evidence_retriever import RetrievedEvidence


# ---------------------------------------------------------------------------
# Synonym map for semantic normalization
# ---------------------------------------------------------------------------

_SYNONYM_MAP: dict[str, str] = {
    # Population synonyms
    "residents": "population",
    "inhabitants": "population",
    "people": "population",
    "citizens": "population",
    "populace": "population",
    "population": "population",
    "pop": "population",
    # Location synonyms
    "located in": "location",
    "situated in": "location",
    "found in": "location",
    "positioned in": "location",
    # Capital synonyms
    "capital": "capital",
    "seat of government": "capital",
    "capital city": "capital",
    # Size synonyms
    "large": "size",
    "big": "size",
    "small": "size",
    "tiny": "size",
    "massive": "size",
    "enormous": "size",
    # Founded synonyms
    "founded": "founded",
    "established": "founded",
    "created": "founded",
    "built": "founded",
    "settled": "founded",
    "originated": "founded",
    # Numeric approximation
    "approximately": "approx",
    "about": "approx",
    "roughly": "approx",
    "nearly": "approx",
    "around": "approx",
    "some": "approx",
    "estimated": "approx",
    "close to": "approx",
    # Size words for numeric
    "million": "million",
    "billion": "billion",
    "thousand": "thousand",
    "trillion": "trillion",
    # Percentage
    "percent": "percent",
    "percentage": "percent",
    "%": "percent",
    # Country/location
    "country": "country",
    "nation": "country",
    "state": "country",
    "island country": "country",
    # City
    "city": "city",
    "metropolis": "city",
    "metropolitan": "city",
    # Height
    "tall": "height",
    "height": "height",
    "high": "height",
    "meters": "meters",
    "metres": "meters",
    "feet": "feet",
    "ft": "feet",
}

# Numeric word to number mapping
_NUMERIC_WORDS: dict[str, float] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4,
    "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9,
    "ten": 10, "eleven": 11, "twelve": 12, "thirteen": 13,
    "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30,
    "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70,
    "eighty": 80, "ninety": 90, "hundred": 100,
    "thousand": 1000, "million": 1_000_000, "billion": 1_000_000_000,
    "trillion": 1_000_000_000_000,
}

# Stop words for TF-IDF-like scoring
_STOP_WORDS: set[str] = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "because", "but", "and", "or", "if", "while", "about",
}


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class EvidenceRanker(Protocol):
    """Protocol for evidence ranking strategies."""

    def rank(
        self,
        evidence: list[RetrievedEvidence],
        subject: str,
        predicate: str,
        claim_type: str = "factual",
    ) -> list[RetrievedEvidence]:
        """Rank evidence by relevance to the claim.

        Args:
            evidence: Candidate evidence items.
            subject: The entity the claim is about.
            predicate: The attribute or relationship being claimed.
            claim_type: Type of claim.

        Returns:
            Evidence sorted by relevance (highest first).
        """
        ...


# ---------------------------------------------------------------------------
# Text normalization utilities
# ---------------------------------------------------------------------------


def _tokenize(text: str) -> list[str]:
    """Tokenize text into lowercase word tokens."""
    return re.findall(r"[a-z0-9]+(?:\.[0-9]+)?", text.lower())


def _normalize_token(token: str) -> str:
    """Normalize a token using synonym map."""
    return _SYNONYM_MAP.get(token, token)


def _normalize_tokens(tokens: list[str]) -> list[str]:
    """Normalize a list of tokens."""
    return [_normalize_token(t) for t in tokens]


def _parse_numeric(text: str) -> float | None:
    """Parse a numeric value from text, handling words and abbreviations."""
    text = text.strip().lower().replace(",", "")

    # Try direct float parse
    try:
        return float(text)
    except (ValueError, TypeError):
        pass

    # Try word-to-number conversion
    words = text.split()
    total = 0.0
    current = 0.0

    for word in words:
        if word in _NUMERIC_WORDS:
            val = _NUMERIC_WORDS[word]
            if val >= 1000:
                if current == 0:
                    current = 1
                total += current * val
                current = 0
            else:
                current += val
        else:
            return None

    total += current
    return total if total > 0 else None


def _extract_numbers(text: str) -> list[float]:
    """Extract all numeric values from text."""
    numbers = []

    # Arabic numerals with optional commas/dots
    for match in re.finditer(r"\b[\d,]+(?:\.\d+)?\b", text):
        val = _parse_numeric(match.group())
        if val is not None:
            numbers.append(val)

    # Word numerals
    words = text.lower().split()
    i = 0
    while i < len(words):
        if words[i] in _NUMERIC_WORDS and _NUMERIC_WORDS[words[i]] >= 1000:
            # Check for preceding number word
            if i > 0 and words[i - 1] in _NUMERIC_WORDS:
                pass  # Already handled by _parse_numeric
        i += 1

    return numbers


# ---------------------------------------------------------------------------
# KeywordRanker (baseline)
# ---------------------------------------------------------------------------


class KeywordRanker:
    """Baseline keyword matching ranker.

    Replicates the existing FixtureEvidenceRetriever._compute_relevance logic.
    Used as a fallback and for comparison.
    """

    def rank(
        self,
        evidence: list[RetrievedEvidence],
        subject: str,
        predicate: str,
        claim_type: str = "factual",
    ) -> list[RetrievedEvidence]:
        """Rank evidence using keyword matching."""
        scored: list[tuple[float, RetrievedEvidence]] = []

        for ev in evidence:
            score = self._score(subject, predicate, ev)
            if score > 0:
                scored.append((score, ev))

        scored.sort(key=lambda x: (-x[0], x[1].source_id))
        return [
            RetrievedEvidence(
                source_id=ev.source_id,
                title=ev.title,
                content=ev.content,
                authority=ev.authority,
                relevance_score=score,
                structured_values=ev.structured_values,
                domain=ev.domain,
                source_uri=ev.source_uri,
                source_date=ev.source_date,
                retrieved_at=ev.retrieved_at,
            )
            for score, ev in scored
        ]

    def _score(
        self, subject: str, predicate: str, ev: RetrievedEvidence
    ) -> float:
        """Score a single evidence item."""
        sv = ev.structured_values
        content = ev.content.lower()
        subject_lower = subject.lower().strip()

        score = 0.0

        entity = sv.get("entity", "").lower().strip()
        if not entity:
            return 0.0

        entity_match = subject_lower == entity or (
            len(subject_lower) > 2 and subject_lower in entity
        ) or (
            len(entity) > 2 and entity in subject_lower
        )

        if not entity_match:
            return 0.0

        score = 0.5

        predicate_lower = predicate.lower()
        if predicate_lower == "capital_of":
            if "capital" in content:
                score += 0.3
        elif predicate_lower == "population":
            if "population" in content:
                score += 0.3
        elif predicate_lower in ("completed_in", "founded"):
            if any(w in content for w in ["completed", "founded", "established", "dedicated"]):
                score += 0.3
        elif predicate_lower == "height_meters":
            if any(w in content for w in ["height", "meters", "tall", "high"]):
                score += 0.3
        else:
            score += 0.2

        if sv.get("type", "") in content:
            score += 0.1

        return min(score, 1.0)


# ---------------------------------------------------------------------------
# SemanticRanker
# ---------------------------------------------------------------------------


class SemanticRanker:
    """Deterministic semantic/hybrid evidence ranker.

    V2-11: Combines multiple signals for robust ranking:
    1. Entity overlap (strongest signal)
    2. Predicate/topic similarity (normalized lexical + synonym)
    3. Content similarity (TF-IDF-like scoring)
    4. Numeric matching (support or contradiction signal)
    5. Authority bonus

    Does NOT use external embeddings. Operates offline deterministically.
    """

    def __init__(self, top_k: int = 10) -> None:
        """Initialize the semantic ranker.

        Args:
            top_k: Maximum number of evidence items to return.
        """
        self._top_k = top_k

    def rank(
        self,
        evidence: list[RetrievedEvidence],
        subject: str,
        predicate: str,
        claim_type: str = "factual",
    ) -> list[RetrievedEvidence]:
        """Rank evidence using hybrid semantic scoring."""
        if not evidence:
            return []

        # Build claim representation
        claim_tokens = self._build_claim_tokens(subject, predicate, claim_type)
        claim_entities = self._extract_entities(subject)
        claim_numbers = self._extract_numbers_from_claim(subject, predicate)

        scored: list[tuple[float, RetrievedEvidence]] = []

        for ev in evidence:
            score = self._score(
                ev, claim_tokens, claim_entities, claim_numbers, subject, predicate
            )
            if score > 0:
                scored.append((score, ev))

        # Sort by score descending, then by source_id for deterministic tie-breaking
        scored.sort(key=lambda x: (-x[0], x[1].source_id))

        return [
            RetrievedEvidence(
                source_id=ev.source_id,
                title=ev.title,
                content=ev.content,
                authority=ev.authority,
                relevance_score=score,
                structured_values=ev.structured_values,
                domain=ev.domain,
                source_uri=ev.source_uri,
                source_date=ev.source_date,
                retrieved_at=ev.retrieved_at,
            )
            for score, ev in scored[:self._top_k]
        ]

    def _build_claim_tokens(
        self, subject: str, predicate: str, claim_type: str
    ) -> list[str]:
        """Build normalized token set from the claim."""
        text = f"{subject} {predicate} {claim_type}"
        tokens = _tokenize(text)
        return _normalize_tokens(tokens)

    def _extract_entities(self, subject: str) -> set[str]:
        """Extract entity names from subject."""
        entities = set()
        tokens = _tokenize(subject)
        entities.update(tokens)

        # Also add the full subject as a phrase
        entities.add(subject.lower().strip())

        # Add common aliases
        aliases = {
            "nyc": "new york city",
            "new york": "new york city",
            "usa": "united states",
            "us": "united states",
            "uk": "united kingdom",
            "uae": "united arab emirates",
        }
        subject_lower = subject.lower().strip()
        if subject_lower in aliases:
            entities.add(aliases[subject_lower])
            entities.update(_tokenize(aliases[subject_lower]))

        return entities

    def _extract_numbers_from_claim(
        self, subject: str, predicate: str
    ) -> list[float]:
        """Extract numeric values from the claim."""
        text = f"{subject} {predicate}"
        return _extract_numbers(text)

    def _score(
        self,
        ev: RetrievedEvidence,
        claim_tokens: list[str],
        claim_entities: set[str],
        claim_numbers: list[float],
        subject: str,
        predicate: str,
    ) -> float:
        """Compute hybrid relevance score."""
        sv = ev.structured_values
        content = ev.content.lower()
        content_tokens = _tokenize(content)
        content_normalized = _normalize_tokens(content_tokens)

        # 1. Entity match (0.0 - 0.4)
        entity_score = self._entity_score(sv, claim_entities, subject)

        # If no entity match, evidence is not relevant
        if entity_score == 0.0:
            return 0.0

        # 2. Predicate/topic similarity (0.0 - 0.25)
        predicate_score = self._predicate_score(
            predicate, content_normalized, sv
        )

        # 3. Content similarity (0.0 - 0.2)
        content_score = self._content_score(claim_tokens, content_normalized)

        # 4. Numeric matching (0.0 - 0.1)
        # High score if numbers match, moderate if they disagree
        # (contradictory evidence should still be retrieved)
        numeric_score = self._numeric_score(
            claim_numbers, content, sv
        )

        # 5. Authority bonus (0.0 - 0.05)
        authority_bonus = self._authority_score(ev.authority)

        total = entity_score + predicate_score + content_score + numeric_score + authority_bonus
        return min(total, 1.0)

    def _entity_score(
        self,
        sv: dict[str, str],
        claim_entities: set[str],
        subject: str,
    ) -> float:
        """Score entity overlap."""
        entity = sv.get("entity", "").lower().strip()
        if not entity:
            return 0.0

        subject_lower = subject.lower().strip()

        # Exact match
        if subject_lower == entity:
            return 0.4

        # Entity contains subject or vice versa
        if subject_lower in entity or entity in subject_lower:
            return 0.35

        # Token overlap
        entity_tokens = set(_tokenize(entity))
        overlap = claim_entities & entity_tokens
        if overlap:
            return 0.3

        # Partial token match
        for ct in claim_entities:
            for et in entity_tokens:
                if len(ct) > 3 and len(et) > 3:
                    if ct in et or et in ct:
                        return 0.25

        return 0.0

    def _predicate_score(
        self,
        predicate: str,
        content_normalized: list[str],
        sv: dict[str, str],
    ) -> float:
        """Score predicate/topic similarity using normalized tokens."""
        predicate_lower = predicate.lower()

        # Map predicate to expected content tokens
        predicate_tokens = _tokenize(predicate_lower)
        predicate_normalized = _normalize_tokens(predicate_tokens)

        # Check direct predicate match in structured values
        if predicate_lower in sv:
            sv_value = sv[predicate_lower]
            if sv_value:
                return 0.25

        # Check predicate synonyms in content
        score = 0.0
        content_set = set(content_normalized)

        for pt in predicate_normalized:
            if pt in content_set:
                score += 0.08

        # Check for related concepts in content
        predicate_keywords = self._predicate_keywords(predicate_lower)
        for kw in predicate_keywords:
            if kw in " ".join(content_normalized):
                score += 0.05

        return min(score, 0.25)

    def _predicate_keywords(self, predicate: str) -> list[str]:
        """Get related keywords for a predicate."""
        keyword_map = {
            "capital_of": ["capital", "seat", "government"],
            "population": ["population", "residents", "inhabitants", "people", "citizens"],
            "founded": ["founded", "established", "built", "settled", "created"],
            "completed_in": ["completed", "finished", "constructed"],
            "height_meters": ["height", "tall", "high", "elevation"],
            "location": ["located", "situated", "found", "positioned"],
        }
        return keyword_map.get(predicate, [predicate])

    def _content_score(
        self,
        claim_tokens: list[str],
        content_normalized: list[str],
    ) -> float:
        """Score content similarity using TF-IDF-like approach."""
        if not claim_tokens or not content_normalized:
            return 0.0

        content_counter = Counter(content_normalized)
        content_len = len(content_normalized)

        score = 0.0
        matched = 0

        for token in claim_tokens:
            if token in _STOP_WORDS:
                continue
            if token in content_counter:
                # TF component
                tf = content_counter[token] / content_len
                # Simple IDF-like weight (rarer tokens get more weight)
                idf = 1.0  # Uniform for simplicity
                score += tf * idf
                matched += 1

        # Normalize by number of claim tokens
        non_stop = [t for t in claim_tokens if t not in _STOP_WORDS]
        if non_stop:
            score = (score / len(non_stop)) * 0.2

        return min(score, 0.2)

    def _numeric_score(
        self,
        claim_numbers: list[float],
        content: str,
        sv: dict[str, str],
    ) -> float:
        """Score numeric matching.

        Matching numbers get high score.
        Mismatched numbers still get moderate score (contradictory evidence
        should be retrieved, not discarded).
        """
        if not claim_numbers:
            return 0.1  # No numeric claim, neutral score

        content_numbers = _extract_numbers(content)

        # Also check structured values
        for key, val in sv.items():
            if key == "entity":
                continue
            num = _parse_numeric(val)
            if num is not None:
                content_numbers.append(num)

        if not content_numbers:
            return 0.05  # No numbers in evidence

        # Check for matching or close numbers
        for cn in claim_numbers:
            for en in content_numbers:
                if cn == 0 and en == 0:
                    return 0.1
                if cn == 0 or en == 0:
                    if abs(cn - en) < 1000:
                        return 0.1
                else:
                    ratio = abs(cn - en) / max(abs(cn), abs(en))
                    if ratio <= 0.15:
                        return 0.1  # Close match
                    elif ratio <= 0.5:
                        return 0.07  # Partial match
                    else:
                        return 0.05  # Mismatch (still retrieve!)

        return 0.05

    def _authority_score(self, authority: str) -> float:
        """Score based on source authority."""
        if authority in ("primary", "primary_source"):
            return 0.05
        elif authority in ("secondary", "secondary_source"):
            return 0.03
        return 0.0
