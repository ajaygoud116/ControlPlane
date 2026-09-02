"""ClaimExtractor — extracts factual claims from free-form text.

Provider-independent abstraction for claim extraction.
The offline implementation uses deterministic pattern matching.

Architecture:

    Response Text
        ↓
    ClaimExtractor.extract()
        ↓
    ExtractedClaim[]
        ↓
    EvidenceRetriever
        ↓
    ClaimVerifier
        ↓
    Finding

The extractor does NOT:
- Verify claims
- Retrieve evidence
- Make decisions

The extractor DOES:
- Identify factual statements in text
- Classify claim types (factual, numeric, temporal)
- Extract relevant entities and values
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ExtractedClaim:
    """A claim extracted from free-form text.

    Attributes:
        claim_text: The original sentence containing the claim.
        claim_type: Type of claim (factual, numeric, temporal, entity,
                    percentage, comparison, location).
        subject: The main entity the claim is about.
        predicate: The attribute or relationship being claimed.
        value: The claimed value (for numeric/temporal/factual claims).
        confidence: Extraction confidence (0.0-1.0).
        negated: Whether the claim is negated (e.g., "is not").
        approximate: Whether the value is approximate ("about", "roughly").
        temporal_qualifier: Time context (e.g., "in 2020", "as of 2024").
        normalized_value: Normalized numeric value when applicable.
        unit: Unit of measurement when applicable.
        extraction_method: How the claim was extracted (e.g., "pattern_population").
    """

    claim_text: str
    claim_type: str
    subject: str
    predicate: str
    value: str
    confidence: float = 1.0
    negated: bool = False
    approximate: bool = False
    temporal_qualifier: str = ""
    normalized_value: float | None = None
    unit: str = ""
    extraction_method: str = ""


# Patterns for claim extraction
_POPULATION_PATTERNS = [
    re.compile(
        r"(?:population|pop\.?)\s+(?:of\s+)?(.+?)\s+(?:is|was|approximately|about|around|roughly)\s+([\d,.\s]+(?:million|billion|thousand)?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(.+?)\s+(?:has|had)\s+(?:a\s+)?population\s+(?:of\s+)?([\d,.\s]+(?:million|billion|thousand)?)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(.+?)\s+population[:\s]+([\d,.\s]+(?:million|billion|thousand)?)",
        re.IGNORECASE,
    ),
]

_CAPITAL_PATTERNS = [
    re.compile(
        r"(.+?)\s+(?:is|was)\s+the\s+capital\s+(?:of\s+)?(.+?)(?:\.|$)",
        re.IGNORECASE,
    ),
    re.compile(
        r"capital\s+(?:of\s+)?(.+?)\s+(?:is|was)\s+(.+?)(?:\.|$)",
        re.IGNORECASE,
    ),
]

_DATE_PATTERNS = [
    re.compile(
        r"(.+?)\s+(?:was\s+)?(?:completed|built|founded|established|dedicated|opened)\s+(?:in\s+)?(\d{3,4})",
        re.IGNORECASE,
    ),
    re.compile(
        r"(.+?)\s+(?:is\s+)?(?:located\s+in\s+)?(.+?)\.?\s+(?:Completed|Built|Founded|Established|Dedicated|Opened)\s+in\s+(\d{3,4})",
        re.IGNORECASE,
    ),
]

_HEIGHT_PATTERNS = [
    re.compile(
        r"(.+?)\s+(?:is|has)\s+(?:a\s+)?height\s+(?:of\s+)?([\d,.\s]+)\s*(?:meters?|m\b|feet|ft\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"(.+?)\s+([\d,.\s]+)\s*(?:meters?|m\b)\s+(?:tall|high)",
        re.IGNORECASE,
    ),
]


def _parse_number(text: str) -> float | None:
    """Parse a number from text, handling million/billion/thousand."""
    text = text.strip().replace(",", "")
    multiplier = 1.0
    if "million" in text.lower():
        multiplier = 1_000_000
        text = re.sub(r"\s*million", "", text, flags=re.IGNORECASE)
    elif "billion" in text.lower():
        multiplier = 1_000_000_000
        text = re.sub(r"\s*billion", "", text, flags=re.IGNORECASE)
    elif "thousand" in text.lower():
        multiplier = 1_000
        text = re.sub(r"\s*thousand", "", text, flags=re.IGNORECASE)
    try:
        return float(text.strip()) * multiplier
    except (ValueError, TypeError):
        return None


class FixtureClaimExtractor:
    """Deterministic claim extractor using pattern matching.

    Extracts factual claims from free-form text using predefined patterns.
    Designed for the geography domain in V2-6.

    The extractor is deterministic: same input → same output.
    It does NOT use an LLM. It does NOT make verification decisions.
    """

    def extract(self, text: str) -> list[ExtractedClaim]:
        """Extract factual claims from text.

        Args:
            text: Free-form text to extract claims from.

        Returns:
            List of extracted claims. May be empty if no claims found.
        """
        if not text or not text.strip():
            return []

        claims: list[ExtractedClaim] = []
        sentences = self._split_sentences(text)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            claims.extend(self._extract_population_claims(sentence))
            claims.extend(self._extract_capital_claims(sentence))
            claims.extend(self._extract_date_claims(sentence))
            claims.extend(self._extract_height_claims(sentence))

        return claims

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        return re.split(r"[.!?]+", text)

    def _extract_population_claims(self, sentence: str) -> list[ExtractedClaim]:
        """Extract population claims from a sentence."""
        claims = []
        for pattern in _POPULATION_PATTERNS:
            match = pattern.search(sentence)
            if match:
                subject = match.group(1).strip()
                value_text = match.group(2).strip()
                value = _parse_number(value_text)
                if value is not None:
                    claims.append(ExtractedClaim(
                        claim_text=sentence,
                        claim_type="numeric",
                        subject=subject,
                        predicate="population",
                        value=str(int(value)),
                        confidence=0.9,
                    ))
                break
        return claims

    def _extract_capital_claims(self, sentence: str) -> list[ExtractedClaim]:
        """Extract capital city claims from a sentence."""
        claims = []
        for pattern in _CAPITAL_PATTERNS:
            match = pattern.search(sentence)
            if match:
                subject = match.group(1).strip()
                value = match.group(2).strip()
                claims.append(ExtractedClaim(
                    claim_text=sentence,
                    claim_type="factual",
                    subject=subject,
                    predicate="capital_of",
                    value=value,
                    confidence=0.95,
                ))
                break
        return claims

    def _extract_date_claims(self, sentence: str) -> list[ExtractedClaim]:
        """Extract date/temporal claims from a sentence."""
        claims = []
        for pattern in _DATE_PATTERNS:
            match = pattern.search(sentence)
            if match:
                subject = match.group(1).strip()
                value = match.group(2).strip() if match.lastindex >= 2 else match.group(1).strip()
                claims.append(ExtractedClaim(
                    claim_text=sentence,
                    claim_type="temporal",
                    subject=subject,
                    predicate="completed_in",
                    value=value,
                    confidence=0.85,
                ))
                break
        return claims

    def _extract_height_claims(self, sentence: str) -> list[ExtractedClaim]:
        """Extract height claims from a sentence."""
        claims = []
        for pattern in _HEIGHT_PATTERNS:
            match = pattern.search(sentence)
            if match:
                subject = match.group(1).strip()
                value = match.group(2).strip()
                claims.append(ExtractedClaim(
                    claim_text=sentence,
                    claim_type="numeric",
                    subject=subject,
                    predicate="height_meters",
                    value=value,
                    confidence=0.85,
                ))
                break
        return claims


# ---------------------------------------------------------------------------
# V2-10: Robust deterministic claim extractor
# ---------------------------------------------------------------------------

# Approximation indicators
_APPROX_WORDS = r"(?:approximately|about|around|roughly|nearly|close to|some|over|under|more than|less than|at least|up to)"

# Temporal qualifier pattern
_TEMPORAL_QUALIFIER = re.compile(
    r"\b(?:(?:in|as of|during|since|before|after|from|between)\s+\d{4}(?:\s*[-–]\s*\d{4})?)\b",
    re.IGNORECASE,
)

# Negation indicators
_NEGATION_INDICATORS = re.compile(
    r"\b(?:is not|are not|was not|were not|does not|do not|did not|"
    r"has not|have not|had not|cannot|can not|won't|will not|"
    r"doesn't|don't|didn't|hasn't|haven't|hadn't)\b",
    re.IGNORECASE,
)

# Non-factual patterns (questions, opinions, imperatives)
_NON_FACTUAL_PATTERNS = [
    re.compile(r"^(?:what|who|where|when|why|how|which|whom|whose)\b", re.IGNORECASE),
    re.compile(r"\?$"),
    re.compile(r"^(?:explain|describe|tell|show|give|list|name|define|compare)\b", re.IGNORECASE),
    re.compile(r"^(?:i think|i believe|i feel|i guess|i suppose|in my opinion|"
               r"it seems|it appears|probably|maybe|perhaps|might be|could be|"
               r"may be|seems like|looks like)\b", re.IGNORECASE),
    re.compile(r"^(?:do|does|did|is|are|was|were|can|could|would|should|will|shall|"
               r"may|might|must)\b", re.IGNORECASE),
]


def _normalize_subject(text: str) -> str:
    """Normalize subject for matching."""
    return re.sub(r"\s+", " ", text.lower().strip().rstrip("."))


def _normalize_predicate(text: str) -> str:
    """Normalize predicate for matching."""
    return re.sub(r"\s+", " ", text.lower().strip())


def _is_non_factual(sentence: str) -> bool:
    """Check if a sentence is non-factual (question, opinion, imperative)."""
    s = sentence.strip()
    if not s:
        return True
    for pattern in _NON_FACTUAL_PATTERNS:
        if pattern.search(s):
            return True
    return False


def _extract_temporal_qualifier(sentence: str) -> str:
    """Extract temporal qualifier from sentence."""
    match = _TEMPORAL_QUALIFIER.search(sentence)
    return match.group(0) if match else ""


def _has_negation(sentence: str) -> bool:
    """Check if sentence contains negation."""
    return bool(_NEGATION_INDICATORS.search(sentence))


def _is_approximate(sentence: str) -> bool:
    """Check if sentence contains approximation indicators."""
    return bool(re.search(_APPROX_WORDS, sentence, re.IGNORECASE))


def _parse_number_with_approximation(text: str) -> tuple[float | None, str, str]:
    """Parse a number from text, handling million/billion/thousand.

    Returns:
        (numeric_value, unit, raw_number_text)
    """
    text = text.strip().replace(",", "")
    multiplier = 1.0
    unit = ""

    if "million" in text.lower():
        multiplier = 1_000_000
        unit = "million"
        text = re.sub(r"\s*million", "", text, flags=re.IGNORECASE)
    elif "billion" in text.lower():
        multiplier = 1_000_000_000
        unit = "billion"
        text = re.sub(r"\s*billion", "", text, flags=re.IGNORECASE)
    elif "thousand" in text.lower():
        multiplier = 1_000
        unit = "thousand"
        text = re.sub(r"\s*thousand", "", text, flags=re.IGNORECASE)

    text = text.strip()
    try:
        value = float(text) * multiplier
        return value, unit, text
    except (ValueError, TypeError):
        return None, unit, text


class RobustClaimExtractor:
    """V2-10: Robust deterministic claim extractor.

    Generalizes claim extraction without introducing LLM dependencies.
    Supports multiple claims per sentence, numeric/relational/date claims,
    negation, approximation, temporal qualifiers, and non-factual filtering.

    Design principles:
    - Precision > recall: prefer UNKNOWN over confidently inventing claims
    - Deterministic: same input → same output
    - No LLM, no network calls, no truth judgment
    - Preserves original text for every extracted claim
    - Compatible with existing EvidenceSource.retrieve() interface
    """

    def extract(self, text: str) -> list[ExtractedClaim]:
        """Extract factual claims from text.

        Supports multiple claims per sentence. Filters non-factual text.
        Preserves original claim text for audit.

        Args:
            text: Free-form text to extract claims from.

        Returns:
            List of extracted claims. May be empty if no factual claims found.
        """
        if not text or not text.strip():
            return []

        claims: list[ExtractedClaim] = []
        sentences = _split_sentences(text)

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence or _is_non_factual(sentence):
                continue

            sentence_claims: list[ExtractedClaim] = []
            sentence_claims.extend(self._extract_population(sentence))
            sentence_claims.extend(self._extract_capital(sentence))
            sentence_claims.extend(self._extract_location(sentence))
            sentence_claims.extend(self._extract_date(sentence))
            sentence_claims.extend(self._extract_percentage(sentence))
            sentence_claims.extend(self._extract_comparison(sentence))

            claims.extend(sentence_claims)

        return claims

    def _extract_population(self, sentence: str) -> list[ExtractedClaim]:
        """Extract population claims from a sentence."""
        claims = []
        negated = _has_negation(sentence)
        approximate = _is_approximate(sentence)
        temporal = _extract_temporal_qualifier(sentence)

        # Population-related nouns
        _pop_nouns = r"(?:population|residents|citizens|inhabitants|people|pop\.?)"

        patterns = [
            # "Tokyo has approximately 14 million residents"
            # "Tokyo has 14 million population"
            (
                re.compile(
                    r"(.+?)\s+(?:has|had)\s+(?:a\s+)?"
                    r"(?:" + _APPROX_WORDS + r"\s+)?"
                    r"([\d,.\s]+(?:million|billion|thousand)?)\s*"
                    + _pop_nouns + r"(?:\s+of\s+" + _pop_nouns + r")?",
                    re.IGNORECASE,
                ),
                "subject_first",
            ),
            # "Tokyo has approximately 14 million residents"
            # Alternative: number before pop_noun
            (
                re.compile(
                    r"(.+?)\s+(?:has|had)\s+(?:a\s+)?"
                    r"(?:" + _APPROX_WORDS + r"\s+)?"
                    + _pop_nouns + r"\s+(?:of\s+)?"
                    r"([\d,.\s]+(?:million|billion|thousand)?)",
                    re.IGNORECASE,
                ),
                "subject_first_alt",
            ),
            # "Tokyo does not have a population of 2 million"
            (
                re.compile(
                    r"(.+?)\s+(?:does|do|did|has|had)\s+not\s+have\s+"
                    r"(?:a\s+)?(?:" + _APPROX_WORDS + r"\s+)?"
                    + _pop_nouns + r"\s+(?:of\s+)?"
                    r"([\d,.\s]+(?:million|billion|thousand)?)",
                    re.IGNORECASE,
                ),
                "negated_have",
            ),
            # "The population of Tokyo is 14 million"
            # "The population of Tokyo is approximately 14 million"
            (
                re.compile(
                    r"(?:the\s+)?" + _pop_nouns + r"\s+(?:of\s+)?(.+?)\s+"
                    r"(?:is|was)\s+"
                    r"(?:" + _APPROX_WORDS + r"\s+)?"
                    r"([\d,.\s]+(?:million|billion|thousand)?)",
                    re.IGNORECASE,
                ),
                "population_first",
            ),
            # "The population is roughly 2.1 million" (no subject)
            (
                re.compile(
                    r"(?:the\s+)?" + _pop_nouns + r"\s+(?:is|was)\s+"
                    r"(?:" + _APPROX_WORDS + r"\s+)?"
                    r"([\d,.\s]+(?:million|billion|thousand)?)",
                    re.IGNORECASE,
                ),
                "population_no_subject",
            ),
            # "Tokyo population: 14 million"
            (
                re.compile(
                    r"(.+?)\s+" + _pop_nouns + r"[:\s]+"
                    r"(?:" + _APPROX_WORDS + r"\s+)?"
                    r"([\d,.\s]+(?:million|billion|thousand)?)",
                    re.IGNORECASE,
                ),
                "shorthand",
            ),
        ]

        for pattern, variant in patterns:
            match = pattern.search(sentence)
            if match:
                if variant == "population_no_subject":
                    # No subject in this pattern — use "The population" as subject
                    subject = "The population"
                    value_text = match.group(1).strip()
                else:
                    subject = match.group(1).strip()
                    value_text = match.group(2).strip()

                norm_val, unit, raw = _parse_number_with_approximation(value_text)
                if norm_val is not None:
                    claims.append(ExtractedClaim(
                        claim_text=sentence,
                        claim_type="numeric",
                        subject=subject,
                        predicate="population",
                        value=str(int(norm_val)),
                        confidence=0.9,
                        negated=negated,
                        approximate=approximate,
                        temporal_qualifier=temporal,
                        normalized_value=norm_val,
                        unit=unit,
                        extraction_method="pattern_population",
                    ))
                break

        return claims

    def _extract_capital(self, sentence: str) -> list[ExtractedClaim]:
        """Extract capital city claims from a sentence."""
        claims = []
        negated = _has_negation(sentence)
        temporal = _extract_temporal_qualifier(sentence)

        patterns = [
            # "Paris is the capital of France" / "Paris is not the capital of Germany"
            re.compile(
                r"(.+?)\s+(?:is|was)\s+(?:not\s+)?the\s+capital\s+(?:of\s+)?(.+?)(?:\.|$)",
                re.IGNORECASE,
            ),
            # "The capital of France is Paris"
            re.compile(
                r"[Tt]he\s+capital\s+(?:of\s+)?(.+?)\s+(?:is|was)\s+(.+?)(?:\.|$)",
                re.IGNORECASE,
            ),
            # "capital of France is Paris"
            re.compile(
                r"capital\s+(?:of\s+)?(.+?)\s+(?:is|was)\s+(.+?)(?:\.|$)",
                re.IGNORECASE,
            ),
        ]

        for i, pattern in enumerate(patterns):
            match = pattern.search(sentence)
            if match:
                if i == 0:
                    # "X is the capital of Y" → subject=X, value=Y
                    subject = match.group(1).strip()
                    value = match.group(2).strip()
                else:
                    # "The capital of Y is X" → subject=X, value=Y
                    country = match.group(1).strip()
                    city = match.group(2).strip()
                    subject = city
                    value = country
                claims.append(ExtractedClaim(
                    claim_text=sentence,
                    claim_type="factual",
                    subject=subject,
                    predicate="capital_of",
                    value=value,
                    confidence=0.95,
                    negated=negated,
                    approximate=False,
                    temporal_qualifier=temporal,
                    extraction_method="pattern_capital",
                ))
                break

        return claims

    def _extract_location(self, sentence: str) -> list[ExtractedClaim]:
        """Extract location claims (e.g., 'Japan is located in Asia')."""
        claims = []
        negated = _has_negation(sentence)
        temporal = _extract_temporal_qualifier(sentence)

        patterns = [
            re.compile(
                r"(.+?)\s+(?:is|was)\s+located\s+(?:in|on|at)\s+(.+?)(?:\.|$)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(.+?)\s+(?:is|was)\s+(?:in|on|at)\s+"
                r"(?:the\s+)?(.+?)(?:\.|$)",
                re.IGNORECASE,
            ),
        ]

        for pattern in patterns:
            match = pattern.search(sentence)
            if match:
                subject = match.group(1).strip()
                value = match.group(2).strip()
                # Avoid matching capital claims
                if re.search(r"\bcapital\b", sentence, re.IGNORECASE):
                    break
                claims.append(ExtractedClaim(
                    claim_text=sentence,
                    claim_type="location",
                    subject=subject,
                    predicate="located_in",
                    value=value,
                    confidence=0.9,
                    negated=negated,
                    approximate=False,
                    temporal_qualifier=temporal,
                    extraction_method="pattern_location",
                ))
                break

        return claims

    def _extract_date(self, sentence: str) -> list[ExtractedClaim]:
        """Extract date/temporal claims from a sentence."""
        claims = []
        negated = _has_negation(sentence)
        approximate = _is_approximate(sentence)

        patterns = [
            re.compile(
                r"(.+?)\s+(?:was\s+)?(?:completed|built|founded|established|"
                r"dedicated|opened|created|founded|incorporated)\s+"
                r"(?:in\s+)?(\d{3,4})",
                re.IGNORECASE,
            ),
            re.compile(
                r"(.+?)\s+(?:occurred|happened|took place)\s+"
                r"(?:on\s+)?([A-Z][a-z]+\s+\d{1,2},?\s+\d{4}|\d{4})",
                re.IGNORECASE,
            ),
            re.compile(
                r"(.+?)\s+(?:has|had)\s+(?:been\s+)?(?:since|from)\s+(\d{4})",
                re.IGNORECASE,
            ),
        ]

        for pattern in patterns:
            match = pattern.search(sentence)
            if match:
                subject = match.group(1).strip()
                value = match.group(2).strip() if match.lastindex >= 2 else match.group(1).strip()
                claims.append(ExtractedClaim(
                    claim_text=sentence,
                    claim_type="temporal",
                    subject=subject,
                    predicate="founded_in",
                    value=value,
                    confidence=0.85,
                    negated=negated,
                    approximate=approximate,
                    temporal_qualifier="",
                    normalized_value=None,
                    unit="year",
                    extraction_method="pattern_date",
                ))
                break

        return claims

    def _extract_percentage(self, sentence: str) -> list[ExtractedClaim]:
        """Extract percentage claims (e.g., '67% accuracy', 'improved by 15%')."""
        claims = []
        negated = _has_negation(sentence)
        approximate = _is_approximate(sentence)
        temporal = _extract_temporal_qualifier(sentence)

        patterns = [
            # "The treatment shows approximately 67% improvement"
            re.compile(
                r"(.+?)\s+(?:shows?|demonstrates?|achieves?|records?|"
                r"reported?|has|had|is|was|of|at|with)?\s*"
                r"(?:" + _APPROX_WORDS + r"\s+)?"
                r"([\d,.]+)\s*%\s*"
                r"(?:improvement|accuracy|increase|decrease|reduction|"
                r"growth|rate|drop|rise|success|enhancement)?",
                re.IGNORECASE,
            ),
            # "improved by 15%"
            re.compile(
                r"(.+?)\s+(?:improved|increased|decreased|reduced|grew|dropped|rose)\s+"
                r"(?:by\s+)?(?:" + _APPROX_WORDS + r"\s+)?"
                r"([\d,.]+)\s*%",
                re.IGNORECASE,
            ),
        ]

        for pattern in patterns:
            match = pattern.search(sentence)
            if match:
                subject = match.group(1).strip()
                value_text = match.group(2).strip()
                try:
                    norm_val = float(value_text.replace(",", ""))
                    claims.append(ExtractedClaim(
                        claim_text=sentence,
                        claim_type="percentage",
                        subject=subject,
                        predicate="percentage_value",
                        value=f"{norm_val}%",
                        confidence=0.85,
                        negated=negated,
                        approximate=approximate,
                        temporal_qualifier=temporal,
                        normalized_value=norm_val,
                        unit="percent",
                        extraction_method="pattern_percentage",
                    ))
                except (ValueError, TypeError):
                    pass
                break

        return claims

    def _extract_comparison(self, sentence: str) -> list[ExtractedClaim]:
        """Extract comparison claims (e.g., 'A is larger than B')."""
        claims = []
        negated = _has_negation(sentence)
        temporal = _extract_temporal_qualifier(sentence)

        patterns = [
            re.compile(
                r"(.+?)\s+(?:is|was)\s+(?:more|less|greater|smaller|"
                r"larger|bigger|taller|shorter|heavier|lighter|"
                r"faster|slower|higher|lower|older|newer|"
                r"more expensive|less expensive|more valuable|less valuable)"
                r"\s+than\s+(.+?)(?:\.|$)",
                re.IGNORECASE,
            ),
            re.compile(
                r"(.+?)\s+(?:is|was)\s+(?:the\s+)?(?:most|least|"
                r"biggest|smallest|tallest|shortest|heaviest|lightest|"
                r"fastest|slowest|highest|lowest|oldest|newest|"
                r"most expensive|least expensive)\s+"
                r"(?:in|of|among)\s+(.+?)(?:\.|$)",
                re.IGNORECASE,
            ),
        ]

        for pattern in patterns:
            match = pattern.search(sentence)
            if match:
                subject = match.group(1).strip()
                value = match.group(2).strip()
                claims.append(ExtractedClaim(
                    claim_text=sentence,
                    claim_type="comparison",
                    subject=subject,
                    predicate="comparison",
                    value=value,
                    confidence=0.8,
                    negated=negated,
                    approximate=False,
                    temporal_qualifier=temporal,
                    extraction_method="pattern_comparison",
                ))
                break

        return claims


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences on period, exclamation, question mark.

    Does NOT split on periods inside numbers (e.g., '2.1', '3.7').
    """
    # Replace periods inside numbers with a placeholder to avoid splitting
    protected = re.sub(r"(\d)\.(\d)", r"\1__DOT__\2", text)
    # Split on sentence-ending punctuation
    parts = re.split(r"[.!?]+", protected)
    # Restore dots in numbers
    return [p.replace("__DOT__", ".") for p in parts]
