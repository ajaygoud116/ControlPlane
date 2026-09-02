"""Anthropic model adapter — real model integration for ControlPlane.

Wraps the Anthropic API to satisfy the ModelAdapter protocol.
Requires the `anthropic` package (optional dependency).

Usage::

    from controlplane.gateway.anthropic_adapter import AnthropicAdapter

    adapter = AnthropicAdapter(
        api_key="sk-ant-...",
        model="claude-3-opus-20240229",
    )
    response = adapter("What is 2+2?")
    print(response.response_text)
"""

from __future__ import annotations

import time
from typing import Any

from controlplane.gateway.adapter import ModelResponse

try:
    import anthropic
    from anthropic import Anthropic

    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False


class AnthropicAdapter:
    """Anthropic model adapter implementing the ModelAdapter protocol.

    This adapter calls the Anthropic Messages API and returns
    a ModelResponse with the model's output and metadata.

    The adapter is stateless — each call is independent.
    It does NOT maintain conversation history.

    Attributes:
        api_key: Anthropic API key.
        model: Model identifier (e.g., 'claude-3-opus-20240229').
        max_tokens: Maximum tokens in the response.
        temperature: Sampling temperature (0.0 = deterministic).
        timeout: Request timeout in seconds.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-3-opus-20240229",
        max_tokens: int = 1024,
        temperature: float = 0.0,
        timeout: float = 30.0,
    ) -> None:
        """Initialize the Anthropic adapter.

        Args:
            api_key: Anthropic API key.
            model: Model identifier.
            max_tokens: Maximum response tokens.
            temperature: Sampling temperature.
            timeout: Request timeout in seconds.

        Raises:
            ImportError: If the `anthropic` package is not installed.
        """
        if not ANTHROPIC_AVAILABLE:
            raise ImportError(
                "The 'anthropic' package is required for AnthropicAdapter. "
                "Install it with: pip install anthropic"
            )

        self._api_key = api_key
        self._model = model
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._timeout = timeout

        # Initialize Anthropic client
        self._client = Anthropic(api_key=api_key)

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

        response = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
            messages=[{"role": "user", "content": request_text}],
            timeout=self._timeout,
        )

        t_end = time.perf_counter()
        latency_ms = (t_end - t_start) * 1000

        # Extract response text
        response_text = ""
        if response.content:
            for block in response.content:
                if block.type == "text":
                    response_text += block.text

        # Extract metadata
        metadata: dict[str, Any] = {
            "latency_ms": latency_ms,
            "model": response.model,
            "provider": "anthropic",
        }

        # Add usage if available
        if response.usage:
            metadata["input_tokens"] = response.usage.input_tokens
            metadata["output_tokens"] = response.usage.output_tokens
            metadata["total_tokens"] = (
                response.usage.input_tokens + response.usage.output_tokens
            )

        # Add stop reason
        if response.stop_reason:
            metadata["stop_reason"] = response.stop_reason

        return ModelResponse(
            response_text=response_text,
            metadata=metadata,
            model=response.model,
            provider="anthropic",
        )
