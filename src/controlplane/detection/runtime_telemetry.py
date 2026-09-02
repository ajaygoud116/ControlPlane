"""Runtime/Cost Telemetry Detector.

Detects runtime anomalies by comparing observed metrics against configured thresholds.

Exact observations consumed:
    MODEL_RUNTIME observations with numeric payload fields.

Detection rule:
    For each configured threshold, compare the corresponding payload value.
    If ANY threshold is exceeded → RUNTIME_ANOMALY.
    Otherwise → RUNTIME_OBSERVED.

Observation-to-finding mapping:
    This detector evaluates each MODEL_RUNTIME observation independently
    and produces one finding per observation. The detector contract permits
    other mappings (e.g., multiple observations → one finding) but this
    detector does not use them.

Finding type: runtime_telemetry
Finding state: RUNTIME_OBSERVED | RUNTIME_ANOMALY

Limitations:
    - Only detects anomalies against configured thresholds.
    - Does NOT determine if high cost is "inefficient".
    - Does NOT consider use case context.
    - HIGH COST ≠ INEFFICIENCY.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from controlplane.detection.base import BaseDetector
from controlplane.schemas.enums import FindingDimension, ObservationType, RuntimeState
from controlplane.schemas.finding import Finding
from controlplane.schemas.observation import Observation


@dataclass(frozen=True)
class RuntimeThreshold:
    """A threshold for a single runtime metric."""

    field_name: str
    max_value: float
    description: str = ""


@dataclass(frozen=True)
class RuntimeDetectorConfig:
    """Configuration for the Runtime/Cost Telemetry Detector."""

    thresholds: list[RuntimeThreshold] = field(default_factory=list)


class RuntimeTelemetryDetector(BaseDetector):
    """Detects runtime anomalies by comparing metrics against thresholds."""

    detector_id = "runtime_telemetry"
    detector_version = "1.0.0"

    def __init__(self, config: RuntimeDetectorConfig | None = None) -> None:
        self._config = config or RuntimeDetectorConfig()

    def detect(self, observations: list[Observation]) -> list[Finding]:
        findings: list[Finding] = []
        for obs in observations:
            if obs.observation_type != ObservationType.MODEL_RUNTIME:
                continue
            findings.append(self._evaluate_observation(obs))
        return findings

    def _evaluate_observation(self, obs: Observation) -> Finding:
        anomalies: list[str] = []
        measurements: dict[str, float] = {}

        for threshold in self._config.thresholds:
            value = obs.payload.get(threshold.field_name)
            if value is not None and isinstance(value, (int, float)):
                measurements[threshold.field_name] = float(value)
                if value > threshold.max_value:
                    anomalies.append(
                        f"{threshold.field_name}={value} exceeds "
                        f"threshold {threshold.max_value}"
                    )

        state = RuntimeState.RUNTIME_ANOMALY if anomalies else RuntimeState.RUNTIME_OBSERVED

        explanation = (
            f"Runtime anomaly detected: {'; '.join(anomalies)}"
            if anomalies
            else "Runtime metrics within configured thresholds"
        )

        return Finding(
            finding_id=uuid4(),
            interaction_id=obs.interaction_id,
            detector_id=self.detector_id,
            detector_version=self.detector_version,
            dimension=FindingDimension.RUNTIME,
            finding_type="runtime_telemetry",
            state=state,
            observation_ids=[obs.observation_id],
            explanation=explanation,
            detected_at=datetime.now(timezone.utc),
            latency_ms=0.0,
            cost_usd=0.0,
        )
