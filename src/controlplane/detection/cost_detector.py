"""Cost Detector — dedicated cost/budget detection.

Separate from RuntimeTelemetryDetector. Distinct from latency detection.
Evaluates token consumption, estimated monetary cost, and budget thresholds.

Exact observations consumed:
    MODEL_RUNTIME observations with numeric payload fields.

Detection produces findings for:
    - token consumption vs budget
    - estimated monetary cost vs budget
    - latency vs threshold
    - missing pricing (COST_UNAVAILABLE)

Finding type: cost_budget
Finding state: CostState

Limitations:
    - Pricing must be configured; missing pricing → COST_UNAVAILABLE.
    - Estimated cost is approximate (based on token counts, not actual billing).
    - Does NOT predict future cost.
    - Does NOT implement model routing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from controlplane.detection.base import BaseDetector
from controlplane.detection.cost_types import CostBudget, ModelPricing
from controlplane.schemas.enums import CostState, FindingDimension, ObservationType
from controlplane.schemas.finding import Finding, FindingMeasurement
from controlplane.schemas.observation import Observation


@dataclass(frozen=True)
class CostDetectorConfig:
    """Configuration for the Cost Detector."""

    budget: CostBudget = field(default_factory=CostBudget)
    pricing: list[ModelPricing] = field(default_factory=list)


class CostDetector(BaseDetector):
    """Detects cost/budget anomalies by comparing metrics against thresholds."""

    detector_id = "cost_budget"
    detector_version = "1.0.0"

    def __init__(self, config: CostDetectorConfig | None = None) -> None:
        self._config = config or CostDetectorConfig()
        self._pricing_by_key: dict[tuple[str, str], ModelPricing] = {}
        for p in self._config.pricing:
            self._pricing_by_key[(p.model, p.provider)] = p

    def detect(self, observations: list[Observation]) -> list[Finding]:
        findings: list[Finding] = []
        for obs in observations:
            if obs.observation_type != ObservationType.MODEL_RUNTIME:
                continue
            findings.append(self._evaluate_observation(obs))
        return findings

    def _evaluate_observation(self, obs: Observation) -> Finding:
        payload = obs.payload
        budget = self._config.budget
        anomalies: list[str] = []
        measurements: dict[str, float] = {}

        # Extract token counts
        input_tokens = payload.get("input_tokens")
        output_tokens = payload.get("output_tokens")
        total_tokens = payload.get("total_tokens")
        latency_ms = payload.get("latency_ms")

        # Normalize token counts
        if input_tokens is not None and isinstance(input_tokens, (int, float)):
            measurements["input_tokens"] = float(input_tokens)
        if output_tokens is not None and isinstance(output_tokens, (int, float)):
            measurements["output_tokens"] = float(output_tokens)
        if total_tokens is not None and isinstance(total_tokens, (int, float)):
            measurements["total_tokens"] = float(total_tokens)
        elif input_tokens is not None and output_tokens is not None:
            measurements["total_tokens"] = float(input_tokens) + float(output_tokens)
        if latency_ms is not None and isinstance(latency_ms, (int, float)):
            measurements["latency_ms"] = float(latency_ms)

        # Check token budgets
        if budget.max_input_tokens is not None and input_tokens is not None:
            if isinstance(input_tokens, (int, float)) and input_tokens > budget.max_input_tokens:
                anomalies.append(
                    f"input_tokens={input_tokens} exceeds budget {budget.max_input_tokens}"
                )

        if budget.max_output_tokens is not None and output_tokens is not None:
            if isinstance(output_tokens, (int, float)) and output_tokens > budget.max_output_tokens:
                anomalies.append(
                    f"output_tokens={output_tokens} exceeds budget {budget.max_output_tokens}"
                )

        if budget.max_total_tokens is not None:
            effective_total = measurements.get("total_tokens")
            if effective_total is not None and effective_total > budget.max_total_tokens:
                anomalies.append(
                    f"total_tokens={effective_total} exceeds budget {budget.max_total_tokens}"
                )

        # Check latency threshold
        if budget.max_latency_ms is not None and latency_ms is not None:
            if isinstance(latency_ms, (int, float)) and latency_ms > budget.max_latency_ms:
                anomalies.append(
                    f"latency_ms={latency_ms} exceeds threshold {budget.max_latency_ms}"
                )

        # Calculate estimated cost
        model = payload.get("model", "")
        provider = payload.get("provider", "")
        estimated_cost: float | None = None

        if model and provider:
            pricing = self._pricing_by_key.get((str(model), str(provider)))
            if pricing is not None:
                in_tok = float(input_tokens) if isinstance(input_tokens, (int, float)) else 0.0
                out_tok = float(output_tokens) if isinstance(output_tokens, (int, float)) else 0.0
                estimated_cost = (
                    in_tok * pricing.input_price_per_token
                    + out_tok * pricing.output_price_per_token
                )
                measurements["estimated_cost_usd"] = estimated_cost

                # Check cost budget
                if budget.max_estimated_cost_usd is not None:
                    if estimated_cost > budget.max_estimated_cost_usd:
                        anomalies.append(
                            f"estimated_cost_usd={estimated_cost:.6f} exceeds "
                            f"budget {budget.max_estimated_cost_usd}"
                        )
            else:
                # Pricing not available for this model/provider
                if budget.max_estimated_cost_usd is not None:
                    anomalies.append(
                        f"cost unavailable for model={model} provider={provider}"
                    )

        # Determine state — first anomaly wins priority ordering
        state = CostState.COST_WITHIN_BUDGET
        if anomalies:
            # Priority: cost unavailable > cost threshold > token budget > latency
            if any("cost unavailable" in a for a in anomalies):
                state = CostState.COST_UNAVAILABLE
            elif any("estimated_cost_usd" in a for a in anomalies):
                state = CostState.COST_THRESHOLD_EXCEEDED
            elif any("token" in a for a in anomalies):
                state = CostState.TOKEN_BUDGET_EXCEEDED
            elif any("latency" in a for a in anomalies):
                state = CostState.LATENCY_THRESHOLD_EXCEEDED

        explanation = (
            f"Cost anomaly: {'; '.join(anomalies)}"
            if anomalies
            else "Cost metrics within configured budgets"
        )

        return Finding(
            finding_id=uuid4(),
            interaction_id=obs.interaction_id,
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            dimension=FindingDimension.COST,
            finding_type="cost_budget",
            state=state,
            observation_ids=[obs.observation_id],
            measurement=FindingMeasurement(
                input_tokens=int(measurements.get("input_tokens", 0)) or None,
                output_tokens=int(measurements.get("output_tokens", 0)) or None,
                latency_ms=measurements.get("latency_ms"),
                estimated_cost_usd=measurements.get("estimated_cost_usd"),
            ),
            explanation=explanation,
            detected_at=datetime.now(timezone.utc),
            latency_ms=0.0,
            cost_usd=0.0,
        )
