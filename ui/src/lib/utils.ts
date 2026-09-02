export function cn(...classes: (string | false | null | undefined)[]): string {
  return classes.filter(Boolean).join(' ')
}

export function formatTimestamp(ts: string | null): string {
  if (!ts) return '—'
  try {
    return new Date(ts).toLocaleTimeString('en-US', { hour12: false })
  } catch {
    return ts
  }
}

export function formatTimestampFull(ts: string | null): string {
  if (!ts) return '—'
  try {
    return new Date(ts).toLocaleString('en-US', {
      hour12: false,
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return ts
  }
}

export function truncate(str: string, max: number): string {
  return str.length > max ? str.slice(0, max) + '...' : str
}

export function formatTokens(n: number | null): string {
  if (n == null) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export function formatCost(n: number | null): string {
  if (n == null) return '—'
  return `$${n.toFixed(4)}`
}

export function formatLatency(ms: number | null): string {
  if (ms == null) return '—'
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)}s`
  return `${ms.toFixed(0)}ms`
}

// ─── Semantic State Model ───────────────────────────────────────
// CLEAN: "I checked and found nothing risk-relevant"
// UNAVAILABLE: "I could not establish the relevant fact"
// UNKNOWN: "ControlPlane does not recognize this state" (fail-closed)
// EVIDENCE: "Detector found something risk-relevant"

const CLEAN_STATES = new Set([
  'no_pii_detected',
  'responsibility_clean',
  'cost_within_budget',
  'runtime_observed',
  'supported',
  'policy_match',
])

const UNAVAILABLE_STATES = new Set([
  'cost_unavailable',
  'policy_unresolved',
  'unverifiable',
])

const EVIDENCE_STATES = new Set([
  'supported',
  'contradicted',
  'conflicted',
  'insufficient_evidence',
  'pii_detected',
  'unsafe_content_detected',
  'secret_detected',
  'cost_threshold_exceeded',
  'token_budget_exceeded',
  'latency_threshold_exceeded',
  'runtime_anomaly',
  'policy_violation',
])

export type StateCategory = 'clean' | 'unavailable' | 'unknown' | 'evidence'

export function stateCategory(state: string): StateCategory {
  if (CLEAN_STATES.has(state)) return 'clean'
  if (UNAVAILABLE_STATES.has(state)) return 'unavailable'
  if (EVIDENCE_STATES.has(state)) return 'evidence'
  // Unknown state — fail-closed
  return 'unknown'
}

export function isKnownState(state: string): boolean {
  return CLEAN_STATES.has(state) || UNAVAILABLE_STATES.has(state) || stateSeverity(state) !== 'unknown'
}

// Human-readable state labels
const STATE_LABELS: Record<string, string> = {
  // Evidence/Risk states
  supported: 'Verified',
  contradicted: 'Contradicted',
  conflicted: 'Conflicting Evidence',
  insufficient_evidence: 'Unverified',
  pii_detected: 'PII Detected',
  unsafe_content_detected: 'Unsafe Content',
  secret_detected: 'Secret Detected',
  cost_threshold_exceeded: 'Over Budget',
  token_budget_exceeded: 'Token Limit Exceeded',
  latency_threshold_exceeded: 'High Latency',
  runtime_anomaly: 'Anomaly',
  policy_violation: 'Policy Violation',
  // Clean states
  no_pii_detected: 'No PII Detected',
  responsibility_clean: 'Clean',
  cost_within_budget: 'Within Budget',
  runtime_observed: 'Observed',
  // Unavailable states
  cost_unavailable: 'Pricing Unavailable',
  policy_unresolved: 'Policy Unresolved',
  unverifiable: 'Unverifiable',
}

export function stateLabel(state: string): string {
  return STATE_LABELS[state] || state.replace(/_/g, ' ')
}

// Severity: critical / warning / info / unknown
// UNKNOWN states fail-closed -> critical
export function stateSeverity(state: string): 'critical' | 'warning' | 'info' | 'unknown' {
  const critical = new Set([
    'contradicted', 'unsafe_content_detected', 'secret_detected',
    'policy_violation', 'cost_threshold_exceeded', 'token_budget_exceeded',
  ])
  const warning = new Set([
    'insufficient_evidence', 'conflicted', 'pii_detected',
    'latency_threshold_exceeded', 'runtime_anomaly',
  ])
  const unavailable = new Set([
    'cost_unavailable', 'policy_unresolved', 'unverifiable',
  ])
  if (critical.has(state)) return 'critical'
  if (warning.has(state)) return 'warning'
  if (unavailable.has(state)) return 'info'
  if (CLEAN_STATES.has(state)) return 'info'
  // Unknown state -> fail-closed
  return 'unknown'
}

// Finding status display text
export function findingStatusText(state: string): { icon: string; label: string; description: string } {
  const cat = stateCategory(state)
  const lbl = stateLabel(state)
  switch (cat) {
    case 'clean':
      return { icon: '\u2713', label: `Checked \u2014 ${lbl}`, description: 'Detector ran and found no risk' }
    case 'unavailable':
      return { icon: '\u25CB', label: `Unavailable \u2014 ${lbl}`, description: 'Could not evaluate this dimension' }
    case 'evidence':
      return { icon: '!', label: `Risk Found \u2014 ${lbl}`, description: 'Detector identified a potential issue' }
    case 'unknown':
      return { icon: '?', label: `Unknown \u2014 ${lbl}`, description: 'Unrecognized state \u2014 fail-closed' }
  }
}

// Human-readable decision labels
const DECISION_LABELS: Record<string, string> = {
  allow: 'Allow',
  modify: 'Modify',
  block: 'Block',
  escalate: 'Escalate',
  verify: 'Verify',
}

export function decisionLabel(d: string): string {
  return DECISION_LABELS[d] || d
}

// Decision color classes for the warm palette
export function decisionColor(d: string): string {
  switch (d) {
    case 'allow': return 'allow'
    case 'modify': return 'modify'
    case 'block': return 'block'
    case 'escalate': return 'escalate'
    case 'verify': return 'verify'
    default: return 'unknown'
  }
}

// Human-readable dimension labels
const DIMENSION_LABELS: Record<string, string> = {
  performance: 'Performance',
  cost: 'Cost',
  responsibility: 'Responsibility',
  pii: 'PII',
  policy: 'Policy',
  runtime: 'Runtime',
}

export function dimensionLabel(d: string): string {
  return DIMENSION_LABELS[d] || d
}

// Dimension semantic mapping for the warm palette
export function dimensionColor(d: string): string {
  switch (d) {
    case 'performance': return 'brand'
    case 'cost': return 'accent'
    case 'responsibility': return 'block'
    case 'pii': return 'block'
    case 'policy': return 'text-secondary'
    case 'runtime': return 'text-secondary'
    default: return 'text-secondary'
  }
}

// Explain reason codes in human-readable form
export function explainReason(code: string): string {
  const explanations: Record<string, string> = {
    // Hard constraint reasons
    hard_constraint_violation: 'Policy hard constraint violated',
    hard_constraint_required: 'Verification required by policy',
    hard_constraint_trigger: 'Escalation trigger activated',

    // Verification reasons
    verification_not_feasible: 'Verification required but no verifier available within budget',
    verification_failed: 'Verification process failed',
    verification_timeout: 'Verification timed out',
    max_verification_depth_reached: 'Maximum verification depth exceeded',

    // Assurance reasons
    basic_detection_satisfied: 'Basic detection requirements met',
    evidence_review_not_met: 'Evidence review requirements not met',
    verified_evidence_not_met: 'Verified evidence requirements not met',
    all_findings_clean: 'All detectors checked \u2014 no issues found',

    // Fail-closed reasons
    unknown_finding_state: 'Unrecognized finding state \u2014 fail-closed escalation',
    no_findings: 'No risk signals detected',
    all_findings_within_tolerance: 'All findings within acceptable tolerance',

    // Intervention reasons
    pii_redacted: 'PII detected and redacted',
    response_blocked: 'Response blocked by policy',
    held_for_review: 'Response held for human review',
  }

  // Check for exact match
  if (explanations[code]) return explanations[code]

  // Handle dimension:state format (e.g., "pii:no_pii_detected")
  if (code.includes(':')) {
    const [dim, state] = code.split(':')
    const dimLabel = dimensionLabel(dim)
    const stateLbl = stateLabel(state)
    return `${dimLabel}: ${stateLbl}`
  }

  // Handle verification_ prefix (e.g., "verification_failed")
  if (code.startsWith('verification_')) {
    const status = code.slice('verification_'.length)
    return `Verification ${status.replace(/_/g, ' ')}`
  }

  // Handle assurance level suffix (e.g., "basic_detection_satisfied")
  if (code.endsWith('_satisfied')) {
    const assurance = code.slice(0, -'_satisfied'.length)
    return `${assurance.replace(/_/g, ' ')} requirements met`
  }
  if (code.endsWith('_not_met')) {
    const assurance = code.slice(0, -'_not_met'.length)
    return `${assurance.replace(/_/g, ' ')} requirements not met`
  }

  // Fallback: capitalize words
  return code.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase())
}

// Get dimension summary from findings
export function getDimensionSummary(findings: any[]): {
  performance: { status: string; severity: string; detail: string }
  cost: { status: string; severity: string; detail: string }
  responsibility: { status: string; severity: string; detail: string }
} {
  const perf = findings.filter(f => f.dimension === 'performance')
  const cost = findings.filter(f => f.dimension === 'cost')
  const resp = findings.filter(f => f.dimension === 'responsibility' || f.dimension === 'pii')

  return {
    performance: perf.length > 0 ? {
      status: stateLabel(perf[0].state),
      severity: stateSeverity(perf[0].state),
      detail: perf[0].explanation || perf[0].evidence?.claim_text || '',
    } : { status: 'Not checked', severity: 'info', detail: 'No performance claims to evaluate' },
    cost: cost.length > 0 ? {
      status: stateLabel(cost[0].state),
      severity: stateSeverity(cost[0].state),
      detail: cost[0].explanation || '',
    } : { status: 'Not checked', severity: 'info', detail: 'No cost information available' },
    responsibility: resp.length > 0 ? {
      status: stateLabel(resp[0].state),
      severity: stateSeverity(resp[0].state),
      detail: resp[0].explanation || '',
    } : { status: 'Not checked', severity: 'info', detail: 'No responsibility check performed' },
  }
}

// Severity classes for the warm palette
export function severityBg(severity: string): string {
  switch (severity) {
    case 'critical': return 'bg-cp-block-soft border-cp-block/20'
    case 'warning': return 'bg-cp-escalate-soft border-cp-escalate/20'
    case 'unknown': return 'bg-cp-surface-2 border-cp-border'
    default: return 'bg-cp-allow-soft border-cp-allow/20'
  }
}

export function severityText(severity: string): string {
  switch (severity) {
    case 'critical': return 'text-cp-block'
    case 'warning': return 'text-cp-escalate'
    case 'unknown': return 'text-cp-unknown'
    default: return 'text-cp-allow'
  }
}

export function severityDot(severity: string): string {
  switch (severity) {
    case 'critical': return 'bg-cp-block'
    case 'warning': return 'bg-cp-escalate'
    case 'unknown': return 'bg-cp-unknown'
    default: return 'bg-cp-allow'
  }
}

// Decision border colors for the warm palette
export function decisionBorder(d: string): string {
  switch (d) {
    case 'allow': return 'border-l-cp-allow'
    case 'modify': return 'border-l-cp-modify'
    case 'block': return 'border-l-cp-block'
    case 'escalate': return 'border-l-cp-escalate'
    case 'verify': return 'border-l-cp-verify'
    default: return 'border-l-cp-text-muted'
  }
}

// Decision text colors for the warm palette
export function decisionText(d: string): string {
  switch (d) {
    case 'allow': return 'text-cp-allow'
    case 'modify': return 'text-cp-modify'
    case 'block': return 'text-cp-block'
    case 'escalate': return 'text-cp-escalate'
    case 'verify': return 'text-cp-verify'
    default: return 'text-cp-text-muted'
  }
}

// Get badge class for decision
export function decisionBadgeClass(d: string): string {
  switch (d) {
    case 'allow': return 'cp-badge-allow'
    case 'modify': return 'cp-badge-modify'
    case 'block': return 'cp-badge-block'
    case 'escalate': return 'cp-badge-escalate'
    case 'verify': return 'cp-badge-verify'
    default: return 'cp-badge-unknown'
  }
}

// Get status indicator class
export function statusIndicatorClass(severity: string): string {
  switch (severity) {
    case 'critical': return 'status-dot-block'
    case 'warning': return 'status-dot-escalate'
    case 'unknown': return 'status-dot-unknown'
    default: return 'status-dot-allow'
  }
}
