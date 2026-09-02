"""POST /check endpoint — model-agnostic transport adapter.

This module creates a FastAPI application that exposes ControlPlaneRuntime
via HTTP. The HTTP layer contains NO detection or decision logic — it is
purely a transport adapter.

The endpoint receives request/response metadata and passes it directly
to ControlPlaneRuntime.check(). It does NOT call any LLM.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from fastapi import FastAPI, HTTPException

from controlplane.api.schemas import CheckRequest, CheckResponse
from controlplane.runtime.runtime import ControlPlaneRuntime
from controlplane.runtime.result import ControlPlaneResult

logger = logging.getLogger(__name__)


def create_app(runtime: ControlPlaneRuntime) -> FastAPI:
    """Create a FastAPI application with the /check endpoint.

    Args:
        runtime: Configured ControlPlaneRuntime instance.

    Returns:
        FastAPI application with the /check endpoint registered.
    """
    app = FastAPI(
        title="ControlPlane V1 API",
        description="Model-agnostic AI oversight layer",
        version="0.1.0",
    )

    @app.post("/check", response_model=CheckResponse)
    async def check(request: CheckRequest) -> CheckResponse:
        """Process an AI interaction through ControlPlane.

        This endpoint receives request/response metadata and passes it
        to ControlPlaneRuntime.check(). It does NOT call any LLM.

        The runtime performs:
        - Observation recording
        - Detection (PII, Policy, Runtime, Performance)
        - Decision making
        - Intervention execution
        - Audit record construction
        - Audit persistence (if configured)
        """
        try:
            # Parse context from dict
            from controlplane.schemas.context import Context

            context = Context(**request.context)

            # Parse policy from dict
            from controlplane.schemas.policy import Policy

            policy = Policy(**request.policy)

            # Parse claims if provided
            claims = None
            if request.claims is not None:
                from controlplane.detection.performance_types import Claim

                claims = [Claim(**c) for c in request.claims]

            # Parse evidence if provided
            evidence = None
            if request.evidence is not None:
                from controlplane.detection.performance_types import Evidence

                evidence = [Evidence(**e) for e in request.evidence]

            # Execute the runtime check
            result: ControlPlaneResult = runtime.check(
                request_text=request.request_text,
                response_text=request.response_text,
                context=context,
                policy=policy,
                model=request.model,
                provider=request.provider,
                metadata=request.metadata,
                claims=claims,
                evidence=evidence,
            )

            # Convert findings to serializable dicts
            findings_data = []
            for f in result.interaction.findings:
                findings_data.append(
                    {
                        "finding_id": str(f.finding_id),
                        "detector_id": f.detector_id,
                        "dimension": f.dimension.value,
                        "finding_type": f.finding_type,
                        "state": f.state.value if hasattr(f.state, "value") else str(f.state),
                        "explanation": f.explanation,
                    }
                )

            # Convert decision history to serializable dicts
            decision_history = []
            for d in result.interaction.decisions:
                decision_history.append(
                    {
                        "decision_id": str(d.decision_id),
                        "decision": d.decision.value,
                        "reason_codes": d.reason_codes,
                        "required_assurance": d.required_assurance,
                        "current_assurance": d.current_assurance,
                    }
                )

            # Convert intervention if present
            intervention_data = None
            if result.interaction.intervention:
                intervention_data = {
                    "intervention_id": str(result.interaction.intervention.intervention_id),
                    "action": result.interaction.intervention.action.value,
                    "modification_type": result.interaction.intervention.modification_type,
                }

            # Convert outcome if present
            outcome_data = None
            if result.interaction.outcome:
                outcome_data = {
                    "outcome_id": str(result.interaction.outcome.outcome_id),
                    "outcome_type": result.interaction.outcome.outcome_type,
                    "description": result.interaction.outcome.description,
                }

            return CheckResponse(
                interaction_id=str(result.interaction.interaction_id),
                decision=result.decision.decision.value,
                released_response=result.released_response,
                blocked=result.blocked,
                escalated=result.escalated,
                findings=findings_data,
                decision_history=decision_history,
                intervention=intervention_data,
                outcome=outcome_data,
                audit_persisted=result.audit_persisted,
                audit_persist_error=result.audit_persist_error,
                errors=[],
            )

        except Exception as exc:
            logger.exception("Error processing /check request")
            raise HTTPException(
                status_code=400,
                detail=f"Processing error: {str(exc)}",
            ) from exc

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Health check endpoint."""
        return {"status": "ok"}

    return app
