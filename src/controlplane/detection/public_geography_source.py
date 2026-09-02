"""PublicGeographyEvidenceSource — real public evidence via REST Countries API.

V2-9: Keyless, offline-safe public evidence source for geography claims.

Uses the REST Countries API (https://restcountries.com/v3.1) which is:
- Completely free, no API key required
- Provides structured JSON with capitals, populations, regions
- Stable public HTTP interface

Architecture:

    Claim (subject, predicate)
        ↓
    PublicGeographyEvidenceSource.retrieve()
        ↓
    HTTP request (urllib, stdlib)
        ↓
    Response parser
        ↓
    EvidenceRetrievalResult
        ↓
    ClaimVerifier (provider-agnostic)

The source does NOT:
- Verify claims
- Make decisions
- Require API keys
- Fabricate evidence
- Trust HTTP responses blindly

The source DOES:
- Make bounded HTTP requests with timeouts
- Retry transient failures (bounded)
- Validate response structure
- Preserve full provenance
- Handle rate limiting gracefully
- Work offline with mocked responses in tests
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from controlplane.detection.evidence_retriever import (
    AuthorityLevel,
    EvidenceRetrievalResult,
    RetrievedEvidence,
    RetrievalStatus,
)


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DEFAULT_BASE_URL = "https://restcountries.com/v3.1"
_DEFAULT_CONNECT_TIMEOUT = 5  # seconds
_DEFAULT_READ_TIMEOUT = 10  # seconds
_DEFAULT_MAX_RETRIES = 2
_DEFAULT_RETRY_BACKOFF = 0.5  # seconds

# HTTP status codes that are safe to retry
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}

# Predicate mapping: claim predicate -> REST Countries API field
_PREDICATE_MAP = {
    "capital_of": "capital",
    "population": "population",
    "country_of": "name",
    "region": "region",
    "subregion": "subregion",
    "area": "area",
    "language": "languages",
    "currency": "currencies",
}


# ---------------------------------------------------------------------------
# HTTP transport (isolated boundary)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class HttpRequest:
    """Simple HTTP request descriptor."""

    url: str
    method: str = "GET"
    headers: dict[str, str] = field(default_factory=dict)
    timeout: tuple[int, int] = (5, 10)


@dataclass(frozen=True)
class HttpResponse:
    """Simple HTTP response descriptor."""

    status_code: int
    body: str
    headers: dict[str, str] = field(default_factory=dict)
    latency_ms: float = 0.0


def _http_request(request: HttpRequest) -> HttpResponse:
    """Execute an HTTP request using urllib (stdlib).

    This is the ONLY function that touches the network.
    Everything else operates on HttpRequest/HttpResponse.

    Args:
        request: The HTTP request to execute.

    Returns:
        HttpResponse with status, body, and latency.

    Raises:
        urllib.error.URLError: On network errors.
        TimeoutError: On timeout.
    """
    t_start = time.perf_counter()

    req = urllib.request.Request(
        url=request.url,
        method=request.method,
        headers=request.headers or {"Accept": "application/json"},
    )

    connect_timeout, read_timeout = request.timeout

    try:
        with urllib.request.urlopen(req, timeout=read_timeout) as response:
            body = response.read().decode("utf-8")
            latency_ms = (time.perf_counter() - t_start) * 1000
            return HttpResponse(
                status_code=response.status,
                body=body,
                headers=dict(response.headers),
                latency_ms=latency_ms,
            )
    except urllib.error.HTTPError as exc:
        latency_ms = (time.perf_counter() - t_start) * 1000
        body = ""
        if exc.fp:
            try:
                body = exc.fp.read().decode("utf-8", errors="replace")
            except Exception:
                pass
        return HttpResponse(
            status_code=exc.code,
            body=body,
            latency_ms=latency_ms,
        )
    except urllib.error.URLError as exc:
        latency_ms = (time.perf_counter() - t_start) * 1000
        raise TimeoutError(f"HTTP request failed: {exc.reason}") from exc
    except TimeoutError:
        latency_ms = (time.perf_counter() - t_start) * 1000
        raise
    except Exception as exc:
        latency_ms = (time.perf_counter() - t_start) * 1000
        raise TimeoutError(f"HTTP request failed: {type(exc).__name__}: {exc}") from exc


# ---------------------------------------------------------------------------
# Response validation
# ---------------------------------------------------------------------------


def _validate_country_response(data: Any, subject: str) -> list[dict] | None:
    """Validate and extract country data from API response.

    Returns list of country dicts if valid, empty list if no data,
    None if response is malformed.
    Never raises — malformed data returns None.
    """
    if not isinstance(data, list):
        return None

    if len(data) == 0:
        return []

    valid = []
    for item in data:
        if not isinstance(item, dict):
            continue
        # Must have name at minimum
        if "name" not in item:
            continue
        valid.append(item)

    return valid


# ---------------------------------------------------------------------------
# PublicGeographyEvidenceSource
# ---------------------------------------------------------------------------


class PublicGeographyEvidenceSource:
    """Real public evidence source using REST Countries API.

    Implements the EvidenceSource protocol for geography claims.
    Requires no API key. Uses stdlib urllib for HTTP.

    Supported claim types:
    - capital_of: which country a city is capital of
    - population: country population
    - region: geographic region
    - subregion: geographic subregion

    Usage::

        source = PublicGeographyEvidenceSource()
        result = source.retrieve("Paris", "capital_of", "factual")
        if result.status == RetrievalStatus.FOUND:
            for ev in result.evidence:
                print(f"{ev.source_id}: {ev.content[:80]}")

    With custom HTTP transport (for testing)::

        source = PublicGeographyEvidenceSource(http_fn=my_mock_http)
    """

    def __init__(
        self,
        base_url: str = _DEFAULT_BASE_URL,
        connect_timeout: int = _DEFAULT_CONNECT_TIMEOUT,
        read_timeout: int = _DEFAULT_READ_TIMEOUT,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        retry_backoff: float = _DEFAULT_RETRY_BACKOFF,
        http_fn: Any = None,
    ) -> None:
        """Initialize the public evidence source.

        Args:
            base_url: REST Countries API base URL.
            connect_timeout: Connection timeout in seconds.
            read_timeout: Read timeout in seconds.
            max_retries: Maximum retry attempts for transient failures.
            retry_backoff: Backoff between retries in seconds.
            http_fn: Injectable HTTP function for testing. If None, uses real HTTP.
        """
        self._base_url = base_url.rstrip("/")
        self._connect_timeout = connect_timeout
        self._read_timeout = read_timeout
        self._max_retries = max_retries
        self._retry_backoff = retry_backoff
        self._http_fn = http_fn or _http_request
        self._request_count = 0
        self._retry_count = 0

    @property
    def request_count(self) -> int:
        """Number of HTTP requests made."""
        return self._request_count

    @property
    def retry_count(self) -> int:
        """Number of retries performed."""
        return self._retry_count

    def retrieve(
        self,
        subject: str,
        predicate: str,
        claim_type: str = "factual",
    ) -> EvidenceRetrievalResult:
        """Retrieve evidence for a geography claim.

        Args:
            subject: The entity (country name) the claim is about.
            predicate: The attribute (capital_of, population, region, etc.).
            claim_type: Type of claim.

        Returns:
            EvidenceRetrievalResult with status and evidence.
        """
        t_start = time.perf_counter()

        if not subject:
            return EvidenceRetrievalResult(
                status=RetrievalStatus.NOT_FOUND,
                evidence=[],
                retrieval_method="restcountries_api",
                latency_ms=0.0,
                claim_text=f"{subject} {predicate}",
            )

        # Check if this predicate is supported
        api_field = _PREDICATE_MAP.get(predicate)
        if api_field is None:
            return EvidenceRetrievalResult(
                status=RetrievalStatus.NOT_FOUND,
                evidence=[],
                retrieval_method="restcountries_api",
                latency_ms=0.0,
                error=f"Unsupported predicate: {predicate}",
                claim_text=f"{subject} {predicate}",
            )

        # Build request
        url = f"{self._base_url}/name/{urllib.request.quote(subject)}?fullText=true"
        request = HttpRequest(
            url=url,
            timeout=(self._connect_timeout, self._read_timeout),
        )

        # Execute with retries
        response = self._execute_with_retries(request)

        t_end = time.perf_counter()
        latency_ms = (t_end - t_start) * 1000

        # Handle HTTP errors
        if response.status_code == 404:
            return EvidenceRetrievalResult(
                status=RetrievalStatus.NOT_FOUND,
                evidence=[],
                retrieval_method="restcountries_api",
                latency_ms=latency_ms,
                claim_text=f"{subject} {predicate}",
            )

        if response.status_code == 429:
            return EvidenceRetrievalResult(
                status=RetrievalStatus.FAILED,
                evidence=[],
                retrieval_method="restcountries_api",
                latency_ms=latency_ms,
                error=f"Rate limited (HTTP 429)",
                claim_text=f"{subject} {predicate}",
            )

        if response.status_code >= 400:
            return EvidenceRetrievalResult(
                status=RetrievalStatus.FAILED,
                evidence=[],
                retrieval_method="restcountries_api",
                latency_ms=latency_ms,
                error=f"HTTP {response.status_code}",
                claim_text=f"{subject} {predicate}",
            )

        # Parse response
        try:
            data = json.loads(response.body)
        except (json.JSONDecodeError, ValueError) as exc:
            return EvidenceRetrievalResult(
                status=RetrievalStatus.FAILED,
                evidence=[],
                retrieval_method="restcountries_api",
                latency_ms=latency_ms,
                error=f"Malformed JSON: {exc}",
                claim_text=f"{subject} {predicate}",
            )

        # Validate response structure
        countries = _validate_country_response(data, subject)
        if countries is None:
            return EvidenceRetrievalResult(
                status=RetrievalStatus.FAILED,
                evidence=[],
                retrieval_method="restcountries_api",
                latency_ms=latency_ms,
                error="Invalid response structure",
                claim_text=f"{subject} {predicate}",
            )

        if len(countries) == 0:
            return EvidenceRetrievalResult(
                status=RetrievalStatus.NOT_FOUND,
                evidence=[],
                retrieval_method="restcountries_api",
                latency_ms=latency_ms,
                claim_text=f"{subject} {predicate}",
            )

        # Extract evidence
        evidence = self._extract_evidence(countries, predicate, api_field)

        if not evidence:
            return EvidenceRetrievalResult(
                status=RetrievalStatus.NOT_FOUND,
                evidence=[],
                retrieval_method="restcountries_api",
                latency_ms=latency_ms,
                claim_text=f"{subject} {predicate}",
            )

        return EvidenceRetrievalResult(
            status=RetrievalStatus.FOUND,
            evidence=evidence,
            retrieval_method="restcountries_api",
            latency_ms=latency_ms,
            claim_text=f"{subject} {predicate}",
        )

    def _execute_with_retries(self, request: HttpRequest) -> HttpResponse:
        """Execute HTTP request with bounded retries for transient failures."""
        last_response = None

        for attempt in range(1 + self._max_retries):
            self._request_count += 1

            try:
                response = self._http_fn(request)
            except TimeoutError as exc:
                last_response = HttpResponse(
                    status_code=0,
                    body="",
                    latency_ms=0.0,
                )
                if attempt < self._max_retries:
                    self._retry_count += 1
                    time.sleep(self._retry_backoff * (attempt + 1))
                    continue
                return last_response

            # Success or non-retryable error
            if response.status_code < 500 and response.status_code != 429:
                return response

            # Retryable error
            last_response = response
            if attempt < self._max_retries:
                self._retry_count += 1
                backoff = self._retry_backoff * (attempt + 1)
                if response.status_code == 429:
                    # Rate limit: respect Retry-After if present
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            backoff = max(backoff, float(retry_after))
                        except (ValueError, TypeError):
                            pass
                time.sleep(backoff)

        return last_response or HttpResponse(status_code=0, body="")

    def _extract_evidence(
        self,
        countries: list[dict],
        predicate: str,
        api_field: str,
    ) -> list[RetrievedEvidence]:
        """Extract evidence items from country data."""
        now = datetime.now(timezone.utc).isoformat()
        evidence = []

        for country in countries:
            name_data = country.get("name", {})
            common_name = name_data.get("common", "Unknown")
            official_name = name_data.get("official", common_name)
            cca2 = country.get("cca2", "XX")

            # Build source ID from country code
            source_id = f"restcountries_{cca2.lower()}"

            # Extract the relevant field value
            raw_value = country.get(api_field)
            content = self._format_content(common_name, predicate, raw_value)

            if content is None:
                continue

            # Build structured values for the verifier
            structured_values = {"entity": common_name}
            if predicate == "capital_of":
                caps = country.get("capital", [])
                if caps:
                    structured_values["capital_of"] = caps[0]
            elif predicate == "population":
                pop = country.get("population")
                if pop is not None:
                    structured_values["population"] = str(pop)
            elif predicate == "region":
                structured_values["region"] = country.get("region", "")
            elif predicate == "subregion":
                structured_values["subregion"] = country.get("subregion", "")

            evidence.append(RetrievedEvidence(
                source_id=source_id,
                title=f"REST Countries: {official_name}",
                content=content,
                authority=AuthorityLevel.PRIMARY,
                relevance_score=0.95,
                structured_values=structured_values,
                domain="geography",
                source_uri=f"https://restcountries.com/v3.1/alpha/{cca2}",
                source_date="",  # REST Countries doesn't provide update dates
                retrieved_at=now,
            ))

        return evidence

    def _format_content(
        self, country_name: str, predicate: str, raw_value: Any
    ) -> str | None:
        """Format raw API value into human-readable evidence content."""
        if raw_value is None:
            return None

        if predicate == "capital_of":
            if isinstance(raw_value, list) and raw_value:
                return f"The capital of {country_name} is {raw_value[0]}."
            return None

        elif predicate == "population":
            if isinstance(raw_value, (int, float)):
                return f"The population of {country_name} is {int(raw_value):,}."
            return None

        elif predicate == "region":
            if isinstance(raw_value, str) and raw_value:
                return f"{country_name} is in the {raw_value} region."
            return None

        elif predicate == "subregion":
            if isinstance(raw_value, str) and raw_value:
                return f"{country_name} is in the {raw_value} subregion."
            return None

        elif predicate == "area":
            if isinstance(raw_value, (int, float)):
                return f"The area of {country_name} is {raw_value:,.0f} square kilometers."
            return None

        elif predicate == "country_of":
            if isinstance(raw_value, dict):
                common = raw_value.get("common", "")
                if common:
                    return f"The country is {common}."
            return None

        elif predicate == "language":
            if isinstance(raw_value, dict):
                langs = list(raw_value.values())
                if langs:
                    return f"The official language(s) of {country_name} include {langs[0]}."
            return None

        elif predicate == "currency":
            if isinstance(raw_value, dict):
                for code, info in raw_value.items():
                    if isinstance(info, dict):
                        name = info.get("name", code)
                        return f"The currency of {country_name} is {name} ({code})."
            return None

        return None
