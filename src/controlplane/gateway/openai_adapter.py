"""OpenAI model adapter — real model integration for ControlPlane.

Wraps the OpenAI API to satisfy the ModelAdapter protocol.
Requires the `openai` package (optional dependency).

Usage::

    from controlplane.gateway.openai_adapter import OpenAIAdapter

    adapter = OpenAIAdapter(
        api_key="sk-...",
        model="gpt-4",
    )
    response = adapter("What is 2+2?")
    print(response.response_text)
"""

from __future__ import annotations

import time
from typing import Any

from controlplane.gateway.adapter import ModelResponse

try:
    import openai
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class OpenAIAdapter:
    """OpenAI model adapter implementing the ModelAdapter protocol.

    This adapter calls the OpenAI Chat Completions API and returns
    a ModelResponse with the model's output and metadata.

    The adapter is stateless — each call is independent.
    It does NOT maintain conversation history.

    Attributes:
        api_key: OpenAI API key.
        model: Model identifier (e.g., 'gpt-4', 'gpt-3.5-turbo').
        base_url: Optional custom base URL for OpenAI-compatible APIs.
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature (0.0 = deterministic).
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4",
        base_url: str | None = None,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        timeout: float = 30.0,
    ) -> None:
        """Initialize the OpenAI adapter.

        Args:
            api_key: OpenAI API key.
            model: Model identifier.
            base_url: Optional custom base URL.
            max_tokens: Maximum response tokens.
            temperature: Sampling temperature.
            timeout: Request timeout in seconds.

        Raises:
            ImportError: If the `openai` package is not installed.
        """
        if not OPENAI_AVAILABLE:
            raise ImportError(
                "The 'openai' package is required for OpenAIAdapter. "
                "Install it with: pip install openai"
            )

        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout = timeout

        # Initialize OpenAI client
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = OpenAI(**client_kwargs)

    def __call__(self, request_text: str) -> ModelResponse:
        """Execute the model and return a response.

        Args:
            request_text: The user's input text.

        Returns:
            ModelResponse with the model's output and metadata.

        Raises:
            Exception: If the API call fails.
        """
        t_start = time.perf_counter()

        response = self._client.chat.completions.create(
            model=self._model,
            messages=[{"role": "user", "content": request_text}],
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            timeout=self._timeout,
        )

        t_end = time.perf_counter()
        latency_ms = (t_end - t_start) * 1000

        # Extract response text
        response_text = response.choices[0].message.content or ""

        # Extract metadata
        metadata: dict[str, Any] = {
            "latency_ms": latency_ms,
            "model": response.model,
            "provider": "openai",
        }

        # Add usage if available
        if response.usage:
            metadata["input_tokens"] = response.usage.prompt_tokens
            metadata["output_tokens"] = response.usage.completion_tokens
            metadata["total_tokens"] = response.usage.total_tokens

        return ModelResponse(
            response_text=response_text,
            metadata=metadata,
            model=response.model,
            provider="openai",
        )
