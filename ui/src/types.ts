export interface Finding {
  finding_id: string;
  interaction_id: string;
  detector_id: string;
  detector_version: string;
  dimension: string;
  finding_type: string;
  state: string;
  explanation: string;
  latency_ms: number;
  cost_usd: number;
  detected_at: string | null;
  evidence: {
    claim_text: string | null;
    source_ids: string[];
    source_quality: string | null;
    counter_evidence: string[];
    quality_assessment: Record<string, any> | null;
  };
  measurement: {
    input_tokens: number | null;
    output_tokens: number | null;
    model_calls: number | null;
    tool_calls: number | null;
    latency_ms: number | null;
    estimated_cost_usd: number | null;
  };
  ambiguity: {
    reasons: string[];
    conflicting_sources: number;
    evidence_gaps: string[];
  };
}

export interface Decision {
  decision_id: string;
  interaction_id: string;
  decision_version: string;
  decision: string;
  reason_codes: string[];
  finding_ids: string[];
  policy_id: string;
  policy_version: string;
  required_assurance: string;
  current_assurance: string;
  selected_verifier: string | null;
  decided_at: string | null;
}

export interface Intervention {
  intervention_id: string;
  action: string;
  modification_type: string | null;
  modification_detail: string | null;
  blocked_reason: string | null;
  escalation_reason: string | null;
}

export interface Outcome {
  outcome_type: string;
  description: string;
}

export interface Interaction {
  interaction_id: string;
  request_text: string;
  response_text: string;
  model: string | null;
  provider: string | null;
  decision: string;
  findings_count: number;
  dimensions: string[];
  intervention_action: string | null;
  created_at: string | null;
  policy_id: string;
  policy_version: string;
}

export interface InteractionDetail extends Interaction {
  blocked: boolean;
  escalated: boolean;
  observations: any[];
  findings: Finding[];
  decision_history: Decision[];
  final_decision: string;
  intervention: Intervention | null;
  outcome: Outcome | null;
  verification_events: any[];
  audit_id: string;
  policy_snapshot: Record<string, any>;
  context: {
    consequence: string;
    use_case: string;
    data_sensitivity: string;
    latency_budget_ms: number;
  };
  released_response: string | null;
}

export interface Metrics {
  total_interactions: number;
  findings_by_dimension: Record<string, Record<string, number>>;
  decisions: Record<string, number>;
  latency: Record<string, any>;
}

export interface DemoScenario {
  name: string;
  label: string;
  tag: string;
  description: string;
  dimensions: string[];
  expected_decision: string;
}

export interface Detector {
  detector_id: string;
  name: string;
  dimension: string;
  method: string;
  version: string;
  status: string;
  description: string;
  patterns: number;
}

export interface ModelInfo {
  name: string;
  provider: string;
  status: string;
  type: string;
  description: string;
}

export interface PolicyInfo {
  policy_id: string;
  name: string;
  version: string;
  scope: string;
  description: string;
  assurance_requirements: Record<string, string>;
  hard_constraints: {
    blocked_patterns: string[];
    required_verifications: string[];
    escalation_triggers: string[];
  };
  allowed_verifiers: string[];
  allowed_interventions: string[];
  failure_mode: string;
}

export interface AuditRecord {
  audit_id: string;
  interaction_id: string;
  created_at: string | null;
  model: string | null;
  provider: string | null;
  findings_count: number;
  dimensions: string[];
  decisions: { decision: string; reason_codes: string[] }[];
  intervention_action: string | null;
  released_response: string | null;
  policy_id: string;
  policy_version: string;
}

export interface RunResult {
  interaction_id: string;
  scenario: string;
  request_text: string;
  response_text: string;
  model: string;
  provider: string;
  decision: string;
  released_response: string | null;
  blocked: boolean;
  escalated: boolean;
  findings: Finding[];
  decision_history: Decision[];
  intervention: Intervention | null;
  outcome: Outcome | null;
  audit_persisted: boolean;
  policy_snapshot: Record<string, any>;
  context: {
    consequence: string;
    use_case: string;
    data_sensitivity: string;
    latency_budget_ms: number;
  };
  applied_policy_name: string;
}

export interface PolicyComparison {
  policy_name: string;
  policy_snapshot: Record<string, any>;
  findings: Finding[];
  decision: string;
  intervention: Intervention | null;
  released_response: string | null;
  outcome: Outcome | null;
  blocked: boolean;
  escalated: boolean;
}

export interface PolicyComparisonResult {
  model_output: {
    request_text: string;
    response_text: string;
    model: string;
    provider: string;
  };
  scenario: string;
  context: {
    consequence: string;
    use_case: string;
    data_sensitivity: string;
    latency_budget_ms: number;
  };
  comparisons: PolicyComparison[];
}
