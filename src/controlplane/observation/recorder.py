"""ObservationRecorder — creates and stores validated Observation objects.

This layer answers ONLY: "What did ControlPlane observe?"
It does NOT answer: "Was it risky?", "Was it wrong?", "Should it be blocked?"
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from controlplane.schemas.enums import ObservationType
from controlplane.schemas.observation import Observation


class ObservationRecorder:
    """Creates, validates, and stores Observation objects.

    Usage::

        recorder = ObservationRecorder()
        obs = recorder.record(
            interaction_id=uuid4(),
            observation_type=ObservationType.REQUEST,
            source="api_gateway",
            payload={"text": "Hello", "channel": "customer_support"},
        )
        assert obs.observation_id  # assigned automatically
        assert obs.interaction_id == interaction_id
    """

    def __init__(self) -> None:
        self._observations: list[Observation] = []

    def record(
        self,
        interaction_id: UUID,
        observation_type: ObservationType,
        source: str,
        payload: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
        observation_id: UUID | None = None,
        duration_ms: float | None = None,
    ) -> Observation:
        """Create a validated Observation and store it.

        Args:
            interaction_id: Which interaction this observation belongs to.
            observation_type: What kind of observation this is.
            source: Which component produced this observation.
            payload: Raw observed data. Must contain only raw values, no interpretations.
            timestamp: When the observation occurred. Defaults to now (UTC).
            observation_id: Explicit ID. Auto-generated if not provided.
            duration_ms: Duration of the observed event. Must be >= 0 if provided.

        Returns:
            The validated and stored Observation object.
        """
        obs = Observation(
            observation_id=observation_id or uuid4(),
            interaction_id=interaction_id,
            observation_type=observation_type,
            timestamp=timestamp or datetime.now(timezone.utc),
            source=source,
            payload=payload or {},
            duration_ms=duration_ms,
        )
        self._observations.append(obs)
        return obs

    def get_by_interaction(self, interaction_id: UUID) -> list[Observation]:
        """Return all observations for a given interaction, in recording order."""
        return [o for o in self._observations if o.interaction_id == interaction_id]

    def get_by_id(self, observation_id: UUID) -> Observation | None:
        """Return a single observation by its ID, or None if not found."""
        for o in self._observations:
            if o.observation_id == observation_id:
                return o
        return None

    def get_all(self) -> list[Observation]:
        """Return all recorded observations, in recording order."""
        return list(self._observations)

    def count(self) -> int:
        """Return the total number of recorded observations."""
        return len(self._observations)

    def clear(self) -> None:
        """Remove all stored observations."""
        self._observations.clear()
