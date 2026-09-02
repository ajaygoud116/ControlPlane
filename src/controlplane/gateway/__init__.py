"""Gateway layer — model-agnostic ControlPlane interceptor.

This module provides a thin gateway that wraps model execution and
automatically controls release through the existing ControlPlane pipeline.

Architecture:

    caller
      |
  ControlPlaneGateway
      |
    model callable
      |
    ModelResponse
      |
  ControlPlaneRuntime
      |
    Decision
      |
    Intervention
      |
  Gateway result

The gateway does NOT contain:
- detector logic
- decision logic
- policy evaluation logic
- verification logic
- duplicated intervention logic

It delegates to existing production components.
"""

from __future__ import annotations

from controlplane.gateway.adapter import ModelAdapter, ModelResponse
from controlplane.gateway.gateway import ControlPlaneGateway, GatewayResult

__all__ = [
    "ControlPlaneGateway",
    "GatewayResult",
    "ModelAdapter",
    "ModelResponse",
]
