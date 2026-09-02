"""Shared enums for ControlPlane V1 schemas."""

from enum import Enum


class ObservationType(str, Enum):
    """What was observed."""

    REQUEST = "request"
    RESPONSE = "response"
    MODEL_RUNTIME = "model_runtime"
    TOOL_CALL = "tool_call"
    RETRIEVAL = "retrieval"
    DOWNSTREAM_ACTION = "downstream_action"
    HUMAN_EVENT = "human_event"
    OUTCOME_EVENT = "outcome_event"


class PerformanceState(str, Enum):
    """Evidence-grounded performance detector states."""

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    CONFLICTED = "conflicted"
    UNVERIFIABLE = "unverifiable"


class PIIState(str, Enum):
    """PII detector states."""

    PII_DETECTED = "pii_detected"
    NO_PII_DETECTED = "no_pii_detected"


class PolicyState(str, Enum):
    """Policy detector states."""

    POLICY_VIOLATION = "policy_violation"
    POLICY_MATCH = "policy_match"
    POLICY_UNRESOLVED = "policy_unresolved"


class RuntimeState(str, Enum):
    """Runtime/cost telemetry detector states."""

    RUNTIME_OBSERVED = "runtime_observed"
    RUNTIME_ANOMALY = "runtime_anomaly"


class CostState(str, Enum):
    """Cost detector states."""

    COST_WITHIN_BUDGET = "cost_within_budget"
    COST_THRESHOLD_EXCEEDED = "cost_threshold_exceeded"
    TOKEN_BUDGET_EXCEEDED = "token_budget_exceeded"
    LATENCY_THRESHOLD_EXCEEDED = "latency_threshold_exceeded"
    COST_UNAVAILABLE = "cost_unavailable"


class ResponsibilityState(str, Enum):
    """Responsibility detector states (unsafe content, secrets, data leakage)."""

    UNSAFE_CONTENT_DETECTED = "unsafe_content_detected"
    SECRET_DETECTED = "secret_detected"
    RESPONSIBILITY_CLEAN = "responsibility_clean"


class FindingDimension(str, Enum):
    """Which dimension a finding belongs to."""

    PERFORMANCE = "performance"
    PII = "pii"
    POLICY = "policy"
    RUNTIME = "runtime"
    COST = "cost"
    RESPONSIBILITY = "responsibility"


class Consequence(str, Enum):
    """How severe the outcome of a wrong decision would be."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class Reversibility(str, Enum):
    """Whether the downstream action can be undone."""

    REVERSIBLE = "reversible"
    PARTIALLY_REVERSIBLE = "partially_reversible"
    IRREVERSIBLE = "irreversible"


class DownstreamAction(str, Enum):
    """What the AI response triggers downstream."""

    NONE = "none"
    RECOMMENDATION = "recommendation"
    BUSINESS_ACTION = "business_action"


class DataSensitivity(str, Enum):
    """Sensitivity level of data involved."""

    PUBLIC = "public"
    INTERNAL = "internal"
    PERSONAL = "personal"
    CONFIDENTIAL = "confidential"
    SENSITIVE = "sensitive"


class DecisionAction(str, Enum):
    """What the decision engine decided."""

    ALLOW = "allow"
    VERIFY = "verify"
    BLOCK = "block"
    ESCALATE = "escalate"


class UncertaintyType(str, Enum):
    """What specific uncertainty a verification request targets."""

    FACTUAL_SUPPORT = "factual_support"
    NUMERIC_CONSISTENCY = "numeric_consistency"
    ENTITY_CONSISTENCY = "entity_consistency"
    DATE_CONSISTENCY = "date_consistency"
    SOURCE_CONFLICT = "source_conflict"
    PII_AUTHORIZATION = "pii_authorization"
    POLICY_STATUS = "policy_status"
    ACTION_PRECONDITION = "action_precondition"


class VerificationStatus(str, Enum):
    """Whether the verification completed."""

    RESOLVED = "resolved"
    UNRESOLVED = "unresolved"
    FAILED = "failed"
    TIMEOUT = "timeout"


class VerificationResolution(str, Enum):
    """What the verification determined."""

    SUPPORTED = "supported"
    CONTRADICTED = "contradicted"
    CONFLICTED = "conflicted"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    UNVERIFIABLE = "unverifiable"
    NOT_APPLICABLE = "not_applicable"


class InterventionAction(str, Enum):
    """What ControlPlane actually does."""

    ALLOW = "allow"
    MODIFY = "modify"
    BLOCK = "block"
    ESCALATE = "escalate"


class ModificationType(str, Enum):
    """Deterministic/safe modifications only."""

    PII_REDACTION = "pii_redaction"
    DETERMINISTIC_FORMAT_CORRECTION = "deterministic_format_correction"


class OutcomeType(str, Enum):
    """What actually happened after intervention."""

    RESPONSE_DELIVERED = "response_delivered"
    ACTION_EXECUTED = "action_executed"
    HUMAN_DECISION = "human_decision"
    USER_CORRECTION = "user_correction"
    DOWNSTREAM_FAILURE = "downstream_failure"
    REVERSED = "reversed"
    REWORK_REQUIRED = "rework_required"
    LATER_EVIDENCE_STATE = "later_evidence_state"


class FeedbackAssessment(str, Enum):
    """Was the decision correct given actual outcome."""

    CORRECT = "correct"
    INCORRECT = "incorrect"
    UNCERTAIN = "uncertain"


class FeedbackSource(str, Enum):
    """Who provided the feedback."""

    HUMAN_REVIEWER = "human_reviewer"
    USER = "user"
    DOWNSTREAM_SYSTEM = "downstream_system"
    BENCHMARK_GOLD = "benchmark_gold"


class LabelStrength(str, Enum):
    """How confident we are in the feedback label."""

    SINGLE_OBSERVER = "single_observer"
    ADJUDICATED = "adjudicated"
    OBJECTIVE_OUTCOME = "objective_outcome"


class FailureMode(str, Enum):
    """How the system should behave when ControlPlane itself fails."""

    ALLOW = "allow"
    BLOCK = "block"
    ESCALATE = "escalate"


class Scope(str, Enum):
    """What the policy applies to."""

    GLOBAL = "global"
    USE_CASE = "use_case"
    JURISDICTION = "jurisdiction"
    INTERACTION = "interaction"
