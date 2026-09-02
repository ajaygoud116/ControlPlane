"""BaseDetector — abstract interface for all ControlPlane detectors.

A detector:
- consumes observations
- performs only its defined detection task
- produces structured Finding objects

A detector does NOT:
- make decisions (ALLOW/BLOCK/ESCALATE)
- select verifiers
- calculate universal risk
- determine required assurance

Finding production:
    A detector may produce zero, one, or many findings from any number of
    input observations. The contract permits:

        multiple observations → one finding
        one observation      → one finding
        one observation      → many findings
        many observations    → many findings

    For example, the Evidence-Grounded Performance Detector may correlate
    a response observation with retrieval results and source metadata to
    produce a single finding about a claim's evidential support.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from controlplane.schemas.finding import Finding
from controlplane.schemas.observation import Observation


class BaseDetector(ABC):
    """Abstract base class for all detectors.

    Subclasses must define:
        detector_id: str — stable identifier for this detector
        detector_version: str — version of this detector

    Subclasses must implement:
        detect(observations) → list[Finding]

    The detect() method receives a list of observations and returns a list
    of findings. The mapping between observations and findings is NOT
    restricted to one-to-one. A detector may:

        - Produce zero findings (nothing detected)
        - Produce one finding from many observations (correlation)
        - Produce many findings from one observation (multiple detections)
        - Produce many findings from many observations

    Example::

        class MyDetector(BaseDetector):
            detector_id = "my_detector"
            detector_version = "1.0.0"

            def detect(self, observations):
                findings = []
                for obs in observations:
                    # ... detection logic ...
                    findings.append(Finding(...))
                return findings
    """

    detector_id: str
    detector_version: str

    @abstractmethod
    def detect(
        self,
        observations: list[Observation],
    ) -> list[Finding]:
        """Analyze observations and produce findings.

        Args:
            observations: Observations to analyze. May be empty.
                The detector decides how many observations are relevant
                and how they map to findings.

        Returns:
            List of Finding objects. May be empty if nothing detected.
            Never None. Each Finding's observation_ids should reference
            the observations it depends on.
        """
        ...
