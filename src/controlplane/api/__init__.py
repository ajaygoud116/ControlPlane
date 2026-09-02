"""API package — model-agnostic transport adapter for ControlPlane V1.

This package provides a FastAPI-based HTTP interface to ControlPlaneRuntime.
The HTTP layer contains NO detection or decision logic — it is purely
a transport adapter that converts HTTP requests into Runtime.check() calls.
"""

from controlplane.api.check import create_app
from controlplane.api.app import create_full_app

__all__ = ["create_app", "create_full_app"]
