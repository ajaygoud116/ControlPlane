"""Demo layer — simulated model boundary for CP-5 demonstration.

This module provides a deterministic simulated AI application/model
that produces controlled responses for known scenarios.

It exercises PRODUCTION ControlPlane code without modifying it.
The simulated model is NOT required by the core runtime.
"""

__all__ = ["SimulatedModel", "Scenario", "run_scenario"]
