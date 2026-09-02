"""Feedback schema — structured information connecting decision to outcome."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from controlplane.schemas.enums import FeedbackAssessment, FeedbackSource, LabelStrength


class Feedback(BaseModel):
    """Structured information connecting ControlPlane's decision to actual outcome.

    V1 does NOT require online learning. Feedback primarily becomes
    an evaluation dataset for measuring system performance.
    """

    feedback_id: UUID
    interaction_id: UUID
    decision_id: UUID = Field(description="Decision being assessed")
    outcome_id: UUID = Field(description="Outcome used for assessment")

    assessment: FeedbackAssessment = Field(
        description="Was the decision correct given actual outcome"
    )
    source: FeedbackSource = Field(description="Who or what provided this feedback")
    label_strength: LabelStrength = Field(
        description="How confident we are in this feedback label"
    )

    explanation: str = Field(
        description="Human-readable explanation of why this assessment was made"
    )

    reviewed_at: datetime

    model_config = {"extra": "forbid"}
