"""Monitoring API — FastAPI router for operational visibility.

Exposes read-only endpoints that let operators watch ControlPlane activity
across Performance, Cost, and Responsibility dimensions.

Endpoints:
    GET /monitor/summary          — aggregate counts by dimension, decision, latency
    GET /monitor/interactions     — recent interactions with optional filters
    GET /monitor/interactions/{id} — full detail for a single interaction
    GET /health                   — service health check

This API is strictly read-only. It never creates detections, decisions,
or interventions. It reads exclusively from AuditStore.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from controlplane.monitoring.monitor import MonitoringService


def create_monitoring_router(monitoring_service: MonitoringService) -> APIRouter:
    """Create a FastAPI router for monitoring endpoints.

    Args:
        monitoring_service: MonitoringService instance for reading AuditStore.

    Returns:
        APIRouter with monitoring endpoints registered.
    """
    router = APIRouter(prefix="/monitor", tags=["monitoring"])

    @router.get("/summary")
    async def summary() -> dict:
        """Aggregate summary across all persisted interactions.

        Returns counts by dimension, decision, and latency statistics.
        """
        return monitoring_service.get_summary()

    @router.get("/interactions")
    async def interactions(
        limit: int = Query(default=50, ge=1, le=500),
        offset: int = Query(default=0, ge=0),
        use_case: str | None = Query(default=None),
        dimension: str | None = Query(default=None),
        decision: str | None = Query(default=None),
        model: str | None = Query(default=None,
                                   description="Filter by model name"),
    ) -> list[dict]:
        """List recent interactions with optional filtering.

        Returns lightweight summaries for operator review.
        """
        return monitoring_service.list_interactions(
            limit=limit,
            offset=offset,
            use_case=use_case,
            dimension=dimension,
            decision=decision,
            model=model,
        )

    @router.get("/interactions/{interaction_id}")
    async def interaction_detail(interaction_id: str) -> dict:
        """Get full detail for a single interaction.

        Returns the complete audit record including findings by dimension,
        decision history, intervention, outcome, and latency.
        """
        try:
            iid = UUID(interaction_id)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid interaction_id: {interaction_id}",
            )

        detail = monitoring_service.get_interaction(iid)
        if detail is None:
            raise HTTPException(
                status_code=404,
                detail=f"Interaction {interaction_id} not found",
            )
        return detail

    return router


def create_monitoring_app(monitoring_service: MonitoringService):
    """Create a standalone FastAPI app with monitoring endpoints.

    This is an alternative to attaching the router to an existing app.
    Useful for testing or running monitoring as a separate service.

    Args:
        monitoring_service: MonitoringService instance.

    Returns:
        FastAPI app with monitoring endpoints.
    """
    from fastapi import FastAPI

    app = FastAPI(
        title="ControlPlane Monitoring API",
        description="Operational visibility for ControlPlane",
        version="0.1.0",
    )

    router = create_monitoring_router(monitoring_service)
    app.include_router(router)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app
