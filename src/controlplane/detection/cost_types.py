"""Configurable pricing data for the Cost Detector.

Pricing is data, not decision logic. The CostDetector reads this data
to calculate estimated monetary cost from token counts.

V1: Deterministic calculation from token counts + model pricing.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ModelPricing:
    """Pricing for a specific model from a specific provider.

    All prices are per-token (not per 1K or per million).
    If pricing is unavailable for a model, do not include it —
    the CostDetector will produce COST_UNAVAILABLE.
    """

    model: str
    provider: str
    input_price_per_token: float = 0.0
    output_price_per_token: float = 0.0

    def __post_init__(self) -> None:
        if self.input_price_per_token < 0:
            raise ValueError(
                f"input_price_per_token must be >= 0, got {self.input_price_per_token}"
            )
        if self.output_price_per_token < 0:
            raise ValueError(
                f"output_price_per_token must be >= 0, got {self.output_price_per_token}"
            )


@dataclass(frozen=True)
class CostBudget:
    """Configurable budget thresholds for cost detection.

    All thresholds are optional. Only configured thresholds are evaluated.
    If a threshold is None, that check is skipped.
    """

    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_total_tokens: int | None = None
    max_latency_ms: float | None = None
    max_estimated_cost_usd: float | None = None

    def __post_init__(self) -> None:
        if self.max_input_tokens is not None and self.max_input_tokens < 0:
            raise ValueError(f"max_input_tokens must be >= 0, got {self.max_input_tokens}")
        if self.max_output_tokens is not None and self.max_output_tokens < 0:
            raise ValueError(f"max_output_tokens must be >= 0, got {self.max_output_tokens}")
        if self.max_total_tokens is not None and self.max_total_tokens < 0:
            raise ValueError(f"max_total_tokens must be >= 0, got {self.max_total_tokens}")
        if self.max_latency_ms is not None and self.max_latency_ms < 0:
            raise ValueError(f"max_latency_ms must be >= 0, got {self.max_latency_ms}")
        if self.max_estimated_cost_usd is not None and self.max_estimated_cost_usd < 0:
            raise ValueError(f"max_estimated_cost_usd must be >= 0, got {self.max_estimated_cost_usd}")


# Pre-configured pricing for common models (per-token prices).
# These are EXAMPLES — real pricing must be configured per deployment.
DEFAULT_MODEL_PRICING: list[ModelPricing] = [
    ModelPricing(model="gpt-4", provider="openai",
                 input_price_per_token=0.00003, output_price_per_token=0.00006),
    ModelPricing(model="gpt-4o", provider="openai",
                 input_price_per_token=0.0000025, output_price_per_token=0.00001),
    ModelPricing(model="gpt-3.5-turbo", provider="openai",
                 input_price_per_token=0.0000005, output_price_per_token=0.0000015),
    ModelPricing(model="claude-3-opus", provider="anthropic",
                 input_price_per_token=0.000015, output_price_per_token=0.000075),
    ModelPricing(model="claude-3-sonnet", provider="anthropic",
                 input_price_per_token=0.000003, output_price_per_token=0.000015),
    ModelPricing(model="claude-3-haiku", provider="anthropic",
                 input_price_per_token=0.00000025, output_price_per_token=0.00000125),
]
