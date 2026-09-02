"""Scenario definitions for CP-5 demonstration.

Each scenario defines:
- name: identifier
- description: what it demonstrates
- context: Context for ControlPlane
- policy: Policy for ControlPlane
- expected_decision: what the decision engine should produce
- expected_intervention: what intervention should be applied
- dimension: which detection dimension(s) are exercised

Scenarios use PRODUCTION ControlPlane schemas (Context, Policy).
They do NOT duplicate decision logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import uuid4

from controlplane.schemas.context import Context
from controlplane.schemas.enums import (
    Consequence,
    DataSensitivity,
    DecisionAction,
    InterventionAction,
)
from controlplane.schemas.policy import Policy


@dataclass(frozen=True)
class Scenario:
    """A demonstration scenario definition."""

    name: str
    label: str
    tag: str
    description: str
    model_scenario: str  # Maps to SimulatedModel.generate() scenario name
    context: Context
    policy: Policy
    expected_decision: str  # DecisionAction value
    expected_intervention: str | None  # InterventionAction value or None
    dimensions: list[str]  # Which dimensions are exercised


def _default_context(**overrides) -> Context:
    defaults = dict(
        context_id=uuid4(),
        use_case="customer_support",
        consequence=Consequence.LOW,
        reversibility="reversible",
        downstream_action="none",
        data_sensitivity=DataSensitivity.INTERNAL,
        latency_budget_ms=500.0,
    )
    defaults.update(overrides)
    return Context(**defaults)


def _default_policy(**overrides) -> Policy:
    defaults = dict(
        policy_id=str(uuid4()),
        version="1.0.0",
        scope="global",
        allowed_interventions=["allow", "modify", "block"],
        failure_mode="escalate",
    )
    defaults.update(overrides)
    return Policy(**defaults)


# ══════════════════════════════════════════════════════════════════════
# SCENARIO DEFINITIONS
# ══════════════════════════════════════════════════════════════════════

SCENARIO_CLEAN = Scenario(
    name="clean",
    label="Clean",
    tag="01",
    description="Clean response — no issues detected. ALLOW + original response released.",
    model_scenario="clean",
    context=_default_context(),
    policy=_default_policy(
        allowed_interventions=["allow", "block"],
        failure_mode="escalate",
    ),
    expected_decision="allow",
    expected_intervention="allow",
    dimensions=["none"],
)

SCENARIO_PERFORMANCE = Scenario(
    name="performance_error",
    label="Confidently Wrong",
    tag="02",
    description="Performance failure — incorrect factual claim with evidence contradiction.",
    model_scenario="performance_error",
    context=_default_context(consequence=Consequence.MEDIUM),
    policy=_default_policy(
        allowed_interventions=["allow", "block"],
        failure_mode="block",
    ),
    expected_decision="verify",  # or block if no verifier available
    expected_intervention=None,  # Depends on verification outcome
    dimensions=["performance"],
)

SCENARIO_COST = Scenario(
    name="cost_excessive",
    label="Expensive",
    tag="03",
    description="Cost violation — excessive tokens, latency, and estimated cost.",
    model_scenario="cost_excessive",
    context=_default_context(),
    policy=_default_policy(
        allowed_interventions=["allow", "block"],
        failure_mode="escalate",
        hard_constraints={
            "escalation_triggers": ["token_budget_exceeded", "cost_threshold_exceeded"],
        },
    ),
    expected_decision="escalate",
    expected_intervention="escalate",
    dimensions=["cost"],
)

SCENARIO_PII = Scenario(
    name="pii",
    label="Sensitive",
    tag="04",
    description="Responsibility — PII (SSN, email) in response. MODIFY via redaction.",
    model_scenario="pii",
    context=_default_context(),
    policy=_default_policy(
        allowed_interventions=["allow", "modify", "block"],
        failure_mode="escalate",
    ),
    expected_decision="allow",
    expected_intervention="modify",
    dimensions=["responsibility", "pii"],
)

SCENARIO_SECRET = Scenario(
    name="secret",
    label="Secrets",
    tag="05",
    description="Responsibility — API keys/credentials detected in response.",
    model_scenario="secret",
    context=_default_context(),
    policy=_default_policy(
        allowed_interventions=["allow", "block"],
        failure_mode="escalate",
        hard_constraints={
            "blocked_patterns": ["secret_detected"],
        },
    ),
    expected_decision="block",
    expected_intervention="block",
    dimensions=["responsibility"],
)

SCENARIO_UNSAFE = Scenario(
    name="unsafe",
    label="Unsafe",
    tag="06",
    description="Responsibility — unsafe content pattern detected.",
    model_scenario="unsafe",
    context=_default_context(),
    policy=_default_policy(
        allowed_interventions=["allow", "block"],
        failure_mode="escalate",
        hard_constraints={
            "blocked_patterns": ["unsafe_content_detected"],
        },
    ),
    expected_decision="block",
    expected_intervention="block",
    dimensions=["responsibility"],
)

SCENARIO_MULTI_DIMENSION = Scenario(
    name="multi_dimension",
    label="Multi-Risk",
    tag="07",
    description=(
        "Multi-dimensional overlap — Performance error + Cost excessive + "
        "Responsibility (PII) in a single response."
    ),
    model_scenario="multi_dimension",
    context=_default_context(consequence=Consequence.MEDIUM),
    policy=_default_policy(
        allowed_interventions=["allow", "modify", "block"],
        failure_mode="block",
        hard_constraints={
            "blocked_patterns": ["contradicted", "token_budget_exceeded", "cost_threshold_exceeded"],
        },
    ),
    expected_decision="block",
    expected_intervention="block",
    dimensions=["performance", "cost", "responsibility", "pii"],
)

SCENARIO_POLICY_SENSITIVE = Scenario(
    name="policy_sensitive",
    label="Policy Test",
    tag="08",
    description="Same PII response under Strict policy — demonstrates policy authority. Same finding, different outcome.",
    model_scenario="pii_same_response",
    context=_default_context(consequence=Consequence.MEDIUM),
    policy=_default_policy(
        allowed_interventions=["allow", "block"],
        failure_mode="block",
        hard_constraints={
            "blocked_patterns": ["pii_detected"],
        },
    ),
    expected_decision="block",
    expected_intervention="block",
    dimensions=["responsibility", "pii"],
)

SCENARIO_COST_UNAVAILABLE = Scenario(
    name="cost_unavailable",
    label="Unknown Pricing",
    tag="09",
    description="Cost information unavailable — model not in pricing table. ControlPlane cannot estimate cost.",
    model_scenario="cost_unavailable",
    context=_default_context(),
    policy=_default_policy(
        allowed_interventions=["allow", "block"],
        failure_mode="escalate",
    ),
    expected_decision="allow",
    expected_intervention="allow",
    dimensions=["cost"],
)

ALL_SCENARIOS: list[Scenario] = [
    SCENARIO_CLEAN,
    SCENARIO_PERFORMANCE,
    SCENARIO_COST,
    SCENARIO_PII,
    SCENARIO_SECRET,
    SCENARIO_UNSAFE,
    SCENARIO_MULTI_DIMENSION,
    SCENARIO_POLICY_SENSITIVE,
    SCENARIO_COST_UNAVAILABLE,
]
