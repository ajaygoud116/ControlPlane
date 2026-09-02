import { useEffect, useState } from 'react'
import { api } from '../api'
import type { PolicyInfo } from '../types'
import { cn } from '../lib/utils'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'

export default function Policies() {
  const [policies, setPolicies] = useState<PolicyInfo[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedPolicy, setSelectedPolicy] = useState<string | null>(null)

  useEffect(() => {
    api.listPolicies()
      .then(setPolicies)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="p-6 lg:p-8">
        <div className="flex items-center gap-3 text-cp-text-muted py-12">
          <div className="w-3 h-3 border-2 border-cp-brand/30 border-t-cp-brand rounded-full animate-spin" />
          <span className="text-body-sm font-mono">Loading policies...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 lg:p-8">
        <div className="cp-panel border-cp-block/30 bg-cp-block-soft/30">
          <p className="text-body-sm text-cp-text">Failed to load policies: {error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 lg:p-8 space-y-6 bg-cp-surface">
      {/* Header */}
      <PageHeader
        eyebrow="POLICIES"
        title="Governance Rules"
        description="Define what ControlPlane is allowed to release"
        action={
          <button className="cp-btn-primary">
            + CREATE POLICY
          </button>
        }
      />

      {policies.length === 0 ? (
        <EmptyState
          icon="◇"
          title="No Policies Configured"
          description="Create a policy to define how ControlPlane governs AI responses."
          action={{
            label: 'Create Policy',
            onClick: () => {},
          }}
        />
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {policies.map(policy => (
            <div
              key={policy.policy_id}
              onClick={() => setSelectedPolicy(selectedPolicy === policy.policy_id ? null : policy.policy_id)}
              className={cn(
                'cp-panel cursor-pointer transition-all duration-200',
                selectedPolicy === policy.policy_id
                  ? 'border-cp-brand shadow-sm'
                  : 'hover:border-cp-border-strong hover:shadow-card-hover'
              )}
            >
              {/* Policy Header */}
              <div className="flex items-start justify-between mb-3">
                <div>
                  <h3 className="text-heading-sm text-cp-text">{policy.name}</h3>
                  <p className="text-caption font-mono text-cp-text-muted mt-0.5">
                    v{policy.version} · {policy.scope}
                  </p>
                </div>
                {selectedPolicy === policy.policy_id && (
                  <div className="w-5 h-5 rounded-full bg-cp-brand flex items-center justify-center">
                    <span className="text-white text-caption">✓</span>
                  </div>
                )}
              </div>

              {policy.description && (
                <p className="text-body-sm text-cp-text-secondary mb-4">{policy.description}</p>
              )}

              {/* Assurance Requirements */}
              {Object.keys(policy.assurance_requirements).length > 0 && (
                <div className="mb-4">
                  <div className="cp-section-title mb-2">ASSURANCE LEVELS</div>
                  <div className="grid grid-cols-3 gap-2">
                    {Object.entries(policy.assurance_requirements).map(([dim, level]) => (
                      <div key={dim} className="p-2 bg-cp-surface rounded-md">
                        <div className="text-caption text-cp-text-muted capitalize">{dim}</div>
                        <div className="text-body-sm font-mono font-medium text-cp-text">{level as string}</div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Hard Constraints */}
              <div className="space-y-2">
                {policy.hard_constraints.blocked_patterns.length > 0 && (
                  <div>
                    <div className="cp-section-title mb-1">BLOCKED</div>
                    <div className="flex flex-wrap gap-1.5">
                      {policy.hard_constraints.blocked_patterns.map((pattern, i) => (
                        <span key={i} className="cp-badge-block text-caption">{pattern}</span>
                      ))}
                    </div>
                  </div>
                )}

                {policy.hard_constraints.escalation_triggers.length > 0 && (
                  <div>
                    <div className="cp-section-title mb-1">ESCALATION TRIGGERS</div>
                    <div className="flex flex-wrap gap-1.5">
                      {policy.hard_constraints.escalation_triggers.map((trigger, i) => (
                        <span key={i} className="cp-badge-escalate text-caption">{trigger}</span>
                      ))}
                    </div>
                  </div>
                )}

                {policy.hard_constraints.required_verifications.length > 0 && (
                  <div>
                    <div className="cp-section-title mb-1">REQUIRED VERIFICATIONS</div>
                    <div className="flex flex-wrap gap-1.5">
                      {policy.hard_constraints.required_verifications.map((verification, i) => (
                        <span key={i} className="cp-badge-verify text-caption">{verification}</span>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {/* Expanded Details */}
              {selectedPolicy === policy.policy_id && (
                <div className="mt-4 pt-4 cp-divider space-y-4 animate-fade-in">
                  {/* Allowed Interventions */}
                  <div>
                    <div className="cp-section-title mb-2">ALLOWED INTERVENTIONS</div>
                    {(policy.allowed_interventions ?? []).length === 0 ? (
                      <p className="text-caption text-cp-text-muted">None configured</p>
                    ) : (
                      <div className="flex flex-wrap gap-1.5">
                        {(policy.allowed_interventions ?? []).map((action, i) => (
                          <span
                            key={i}
                            className="cp-badge bg-cp-surface-2 text-cp-text-secondary text-caption"
                          >
                            {action}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>

                  {/* Footer */}
                  <div className="flex items-center gap-4 text-caption text-cp-text-muted">
                    <span>
                      Verifiers: {(policy.allowed_verifiers ?? []).length > 0 
                        ? (policy.allowed_verifiers ?? []).join(', ') 
                        : 'none'}
                    </span>
                    <span>·</span>
                    <span>
                      Failure Mode: <span className={cn(
                        'font-medium',
                        policy.failure_mode === 'block' ? 'text-cp-block' : 'text-cp-escalate'
                      )}>
                        {policy.failure_mode.toUpperCase()}
                      </span>
                    </span>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Key Insight */}
      <div className="cp-panel border-l-4 border-l-cp-accent bg-cp-accent-light/30">
        <p className="text-body-sm text-cp-text">
          <span className="font-semibold text-cp-accent">Key Insight:</span>{' '}
          Detection is not the same as decision. The same finding produces different actions depending on which policy
          is active. ControlPlane separates what was detected from what should be done about it.
        </p>
      </div>
    </div>
  )
}
