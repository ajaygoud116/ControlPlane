"""Traffic interception and real-time observation for ControlPlane.

This module provides automatic capture and processing of all AI model
responses through the ControlPlane pipeline, enabling continuous
real-time observation without requiring manual /check calls.
"""

from controlplane.traffic.interceptor import TrafficInterceptor

__all__ = ["TrafficInterceptor"]
