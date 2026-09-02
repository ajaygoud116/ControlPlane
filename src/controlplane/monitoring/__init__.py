"""Monitoring — operational read layer for ControlPlane AuditStore.

Provides MonitoringService for aggregate summaries and interaction detail,
and a FastAPI router for operator-facing monitoring endpoints.

Architecture:

    AuditStore (source of truth)
        ↓
    MonitoringService (read-only aggregation)
        ↓
    Monitoring API (GET endpoints)
        ↓
    Operator / UI (polling)

This module is strictly read-only. It never creates detections, decisions,
or interventions. It never modifies AuditStore records.
"""

from controlplane.monitoring.monitor import MonitoringService
from controlplane.monitoring.api import create_monitoring_router

__all__ = ["MonitoringService", "create_monitoring_router"]
