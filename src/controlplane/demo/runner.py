"""End-to-end runner for CP-5 demonstration.

Executes scenarios through the full ControlPlane pipeline:
    Simulated Model → ControlPlane → Observe → Detect → Decide → Intervene → Audit

Measures latency at each stage. Produces a structured result for verification.

This module exercises PRODUCTION ControlPlane code.
It does NOT duplicate decision logic.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from controlplane.demo.scenarios import Scenario
from controlplane.demo.simulated_model import SimulatedModel
from controlplane.persistence.audit_store import AuditStore
from controlplane.runtime.runtime import ControlPlaneRuntime
from controlplane.runtime.result import ControlPlaneResult

logger = logging.getLogger(__name__)


@dataclass
class LatencyMeasurement:
    """Latency measurements for a single scenario run."""

    total_ms: float = 0.0
    model_generation_ms: float = 0.0
    observation_ms: float = 0.0
    detection_ms: float = 0.0
    decision_ms: float = 0.0
    intervention_ms: float = 0.0
    audit_persist_ms: float = 0.0


@dataclass
class ScenarioResult:
    """Result of running a single scenario through ControlPlane."""

    scenario_name: str
    description: str
    dimensions: list[str]
    model_output: Any  # ModelOutput
    control_plane_result: ControlPlaneResult
    latency: LatencyMeasurement
    audit_record: Any | None = None  # AuditRecord if persisted


class DemoRunner:
    """End-to-end runner for CP-5 demonstration scenarios.

    Wires together:
    - SimulatedModel (produces deterministic outputs)
    - ControlPlaneRuntime (production code)
    - AuditStore (durable persistence)
    - LatencyMeasurement (timing)

    Usage::

        runner = DemoRunner()
        result = runner.run("clean")
        print(result.control_plane_result.decision.decision)
    """

    def __init__(self, audit_dir: str | None = None) -> None:
        """Initialize the demo runner.

        Args:
            audit_dir: Directory for audit persistence. If None, uses temp dir.
        """
        self._model = SimulatedModel()
        self._audit_dir = audit_dir
        self._audit_store: AuditStore | None = None
        self._runtime: ControlPlaneRuntime | None = None

    def setup(self) -> None:
        """Initialize runtime and audit store. Call before run()."""
        from controlplane.verification.registry import VerifierRegistry
        from controlplane.detection.cost_detector import CostDetector, CostDetectorConfig
        from controlplane.detection.cost_types import CostBudget
        from controlplane.detection.unsafe_content_detector import UnsafeContentDetector
        from controlplane.detection.secrets_detector import SecretsDetector
        import tempfile

        if self._audit_dir is None:
            self._audit_dir = tempfile.mkdtemp(prefix="cp5_demo_")

        self._audit_store = AuditStore(self._audit_dir)
        registry = VerifierRegistry()

        # Configure detectors for demonstration
        cost_detector = CostDetector(config=CostDetectorConfig(
            budget=CostBudget(
                max_input_tokens=1000,
                max_output_tokens=500,
                max_latency_ms=5000.0,
            ),
        ))
        unsafe_detector = UnsafeContentDetector()
        secrets_detector = SecretsDetector()

        self._runtime = ControlPlaneRuntime(
            registry=registry,
            audit_store=self._audit_store,
            cost_detector=cost_detector,
            unsafe_content_detector=unsafe_detector,
            secrets_detector=secrets_detector,
        )

    def run(self, scenario_name: str) -> ScenarioResult:
        """Run a single scenario through the full ControlPlane pipeline.

        Args:
            scenario_name: Name of the scenario to run.

        Returns:
            ScenarioResult with all measurements and results.

        Raises:
            RuntimeError: If setup() has not been called.
        """
        if self._runtime is None:
            raise RuntimeError("Call setup() before run()")

        from controlplane.demo.scenarios import ALL_SCENARIOS

        # Find scenario definition
        scenario = None
        for s in ALL_SCENARIOS:
            if s.name == scenario_name:
                scenario = s
                break
        if scenario is None:
            raise ValueError(f"Unknown scenario: {scenario_name!r}")

        latency = LatencyMeasurement()

        # Phase 1: Model generation
        t0 = time.perf_counter()
        model_output = self._model.generate(scenario.model_scenario)
        latency.model_generation_ms = (time.perf_counter() - t0) * 1000

        # Convert claims/evidence dicts to typed objects if needed
        claims = model_output.claims
        evidence = model_output.evidence
        if claims is not None:
            from controlplane.detection.performance_types import Claim
            claims = [Claim(**c) if isinstance(c, dict) else c for c in claims]
        if evidence is not None:
            from controlplane.detection.performance_types import Evidence
            evidence = [Evidence(**e) if isinstance(e, dict) else e for e in evidence]

        # Phase 2: ControlPlane execution (full pipeline)
        t1 = time.perf_counter()
        result: ControlPlaneResult = self._runtime.check(
            request_text=model_output.request_text,
            response_text=model_output.response_text,
            context=scenario.context,
            policy=scenario.policy,
            model=model_output.model,
            provider=model_output.provider,
            metadata=model_output.metadata,
            claims=claims,
            evidence=evidence,
        )
        latency.total_ms = (time.perf_counter() - t1) * 1000

        # Phase 3: Retrieve audit record
        audit_record = None
        if self._audit_store is not None:
            audit_record = self._audit_store.get(result.interaction.interaction_id)

        return ScenarioResult(
            scenario_name=scenario.name,
            description=scenario.description,
            dimensions=scenario.dimensions,
            model_output=model_output,
            control_plane_result=result,
            latency=latency,
            audit_record=audit_record,
        )

    def run_all(self) -> list[ScenarioResult]:
        """Run all scenarios and return results."""
        results = []
        for scenario_name in self._model.list_scenarios():
            try:
                result = self.run(scenario_name)
                results.append(result)
            except Exception as exc:
                logger.error("Scenario %s failed: %s", scenario_name, exc)
                raise
        return results

    def teardown(self) -> None:
        """Clean up resources."""
        if self._audit_dir is not None and self._audit_dir.startswith("/tmp/"):
            import shutil
            shutil.rmtree(self._audit_dir, ignore_errors=True)
