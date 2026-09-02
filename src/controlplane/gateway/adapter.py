"""Model adapter protocol — generic interface for model callables.

The model adapter is a thin protocol that any model provider can implement.
It does NOT import any specific model provider (openai, anthropic, etc.).

A model adapter produces a ModelResponse containing:
- response_text: the model's generated text
- metadata: runtime telemetry (tokens, latency, etc.)
- claims: optional structured claims for performance detection
- evidence: optional evidence for claim verification

The adapter is replaceable. A real model adapter would call the actual
model API and parse the response. A simulated adapter produces deterministic
outputs for testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class ModelResponse:
    """Output from a model callable.

    This is the minimum interface a model adapter must produce.
    Everything else (context, policy, etc.) comes from the caller,
    not from the model.
    """

    response_text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    claims: list[dict[str, Any]] | None = None
    evidence: list[dict[str, Any]] | None = None
    model: str = "unknown"
    provider: str = "unknown"


@runtime_checkable
class ModelAdapter(Protocol):
    """Protocol for model callables.

    Any callable that accepts a request string and returns a ModelResponse
    satisfies this protocol. The gateway does not care how the model works
    internally.

    Usage::

        class MyModel:
            def __call__(self, request_text: str) -> ModelResponse:
                # Call actual model API
                return ModelResponse(response_text="...", metadata={...})

        gateway = ControlPlaneGateway(runtime=runtime, model=my_model)
    """

    def __call__(self, request_text: str) -> ModelResponse:
        """Execute the model and return a response.

        Args:
            request_text: The user's input text.

        Returns:
            ModelResponse with the model's output and metadata.

        Raises:
            Exception: If the model execution fails. The gateway will
                       handle this according to policy.failure_mode.
        """
        ...
