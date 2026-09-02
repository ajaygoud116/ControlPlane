import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { api } from '../api'
import type { InteractionDetail, Finding } from '../types'
import {
  cn,
  explainReason,
  decisionLabel,
  decisionText,
  formatTimestampFull,
  dimensionLabel,
  getDimensionSummary,
} from '../lib/utils'
import PageHeader from '../components/PageHeader'
import ModelOutput from '../components/ModelOutput'
import ControlPlaneIntercept from '../components/ControlPlaneIntercept'
import DecisionBanner from '../components/DecisionBanner'
import ReleasedResponse from '../components/ReleasedResponse'
import FindingCard from '../components/FindingCard'
import AuditTimeline from '../components/AuditTimeline'

export default function RunDetail() {
  const { id } = useParams<{ id: string }>()
  const [detail, setDetail] = useState<InteractionDetail | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!id) return
    setLoading(true)
    api.getInteraction(id)
      .then(d => setDetail(d))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) {
    return (
      <div className="p-6 lg:p-8">
        <div className="flex items-center gap-3 text-cp-text-muted py-12">
          <div className="w-3 h-3 border-2 border-cp-brand/30 border-t-cp-brand rounded-full animate-spin" />
          <span className="text-body-sm font-mono">Loading execution trace...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 lg:p-8">
        <div className="cp-panel border-cp-block/30 bg-cp-block-soft/30">
          <div className="cp-section-title text-cp-block mb-1">Error</div>
          <p className="text-body-sm text-cp-text">Failed to load: {error}</p>
          <Link to="/activity" className="cp-btn-ghost cp-btn-sm mt-3 inline-block">
            Back to Runs
          </Link>
        </div>
      </div>
    )
  }

  if (!detail) return null

  const findings = detail.findings || []
  const decision = detail.decision_history?.[detail.decision_history.length - 1]
  const intervention = detail.intervention
  const finalDecision = detail.final_decision || detail.decision
  const dimensionSummary = getDimensionSummary(findings)

  // Generate audit timeline events from detail
  const auditEvents = [
    { timestamp: detail.created_at || new Date().toISOString(), event_type: 'MODEL_OUTPUT' },
    ...findings.map(f => ({
      timestamp: f.detected_at || detail.created_at || new Date().toISOString(),
      event_type: `${f.dimension.toUpperCase()}_FINDING`,
    })),
    { timestamp: detail.created_at || new Date().toISOString(), event_type: 'POLICY_EVALUATED' },
    decision && {
      timestamp: decision.decided_at || detail.created_at || new Date().toISOString(),
      event_type: `DECISION_${decision.decision?.toUpperCase()}`,
    },
    intervention && {
      timestamp: detail.created_at || new Date().toISOString(),
      event_type: 'INTERVENTION_APPLIED',
    },
    {
      timestamp: detail.created_at || new Date().toISOString(),
      event_type: 'RESPONSE_RELEASED',
    },
  ].filter(Boolean) as { timestamp: string; event_type: string }[]

  return (
    <div className="p-6 lg:p-8 space-y-6 max-w-5xl bg-cp-surface">
      {/* Back */}
      <Link
        to="/activity"
        className="cp-btn-ghost cp-btn-sm inline-flex items-center gap-2"
      >
        ← BACK TO RUNS
      </Link>

      {/* Header */}
      <div className="flex items-start justify-between gap-4">
        <PageHeader
          eyebrow="EXECUTION TRACE"
          title={`RUN #${detail.interaction_id?.slice(0, 8)}`}
          description={`${detail.model || 'unknown'}${detail.provider ? ` · ${detail.provider}` : ''} · ${formatTimestampFull(detail.created_at)}`}
        />
        {finalDecision && (
          <div className={cn(
            'px-4 py-2 rounded-md text-body-lg font-semibold text-white',
            finalDecision === 'allow' && 'bg-cp-allow',
            finalDecision === 'modify' && 'bg-cp-modify',
            finalDecision === 'block' && 'bg-cp-block',
            finalDecision === 'escalate' && 'bg-cp-escalate',
            finalDecision === 'verify' && 'bg-cp-verify'
          )}>
            {decisionLabel(finalDecision)}
          </div>
        )}
      </div>

      {/* Execution Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Main Content - Pipeline */}
        <div className="lg:col-span-2">
          <div className="cp-pipeline-rail cp-pipeline-rail-active">
            
            {/* Stage 01: User Prompt */}
            <div className="cp-stage">
              <div className="cp-stage-marker cp-stage-marker-complete">✓</div>
              <div className="cp-panel mb-4">
                <div className="cp-section-title mb-2">USER PROMPT</div>
                <p className="text-body text-cp-text">{detail.request_text}</p>
              </div>
            </div>

            <div className="cp-flow-arrow cp-flow-arrow-green" />

            {/* Stage 02: Model Output */}
            <div className="cp-stage">
              <div className="cp-stage-marker cp-stage-marker-complete">✓</div>
              <ModelOutput
                response={detail.response_text}
                model={detail.model}
                provider={detail.provider}
              />
            </div>

            <div className="cp-flow-arrow cp-flow-arrow-green" />

            {/* Stage 03: ControlPlane Intercept */}
            <div className="cp-stage">
              <div className="cp-stage-marker cp-stage-marker-complete">✓</div>
              <ControlPlaneIntercept findings={dimensionSummary} />
            </div>

            <div className="cp-flow-arrow cp-flow-arrow-green" />

            {/* Stage 04: Findings */}
            {findings.length > 0 && (
              <>
                <div className="cp-stage">
                  <div className="cp-stage-marker cp-stage-marker-complete">✓</div>
                  <div className="space-y-3 mb-4">
                    <div className="cp-section-title pl-12">DETAILED FINDINGS</div>
                    <div className="space-y-3">
                      {findings.map(finding => (
                        <FindingCard key={finding.finding_id} finding={finding} />
                      ))}
                    </div>
                  </div>
                </div>
                <div className="cp-flow-arrow cp-flow-arrow-green" />
              </>
            )}

            {/* Stage 05: Policy */}
            <div className="cp-stage">
              <div className="cp-stage-marker cp-stage-marker-complete">✓</div>
              <div className="cp-panel mb-4">
                <div className="cp-section-title mb-2">POLICY</div>
                <div className="flex items-center gap-3">
                  <span className="text-body-lg font-mono font-medium text-cp-text">
                    {detail.policy_id || detail.policy_snapshot?.name || 'Unknown'}
                  </span>
                  {detail.policy_snapshot?.version && (
                    <span className="text-caption font-mono text-cp-text-muted">
                      v{detail.policy_snapshot.version}
                    </span>
                  )}
                </div>
              </div>
            </div>

            <div className="cp-flow-arrow cp-flow-arrow-green" />

            {/* Stage 06: Decision */}
            <div className="cp-stage">
              <div className="cp-stage-marker cp-stage-marker-complete">✓</div>
              <DecisionBanner
                decision={finalDecision}
                policy={detail.policy_id || detail.policy_snapshot?.name}
                reason={decision?.reason_codes?.[0] ? explainReason(decision.reason_codes[0]) : undefined}
                action={intervention?.action}
              />
            </div>

            <div className="cp-flow-arrow cp-flow-arrow-green" />

            {/* Stage 07: Released Response */}
            <div className="cp-stage">
              <div className="cp-stage-marker cp-stage-marker-complete">✓</div>
              <ReleasedResponse
                response={detail.released_response || detail.response_text}
                intervention={intervention?.action}
                rawResponse={detail.response_text}
              />
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-4">
          {/* Decision Summary */}
          <div className="cp-panel">
            <div className="cp-section-title mb-3">DECISION SUMMARY</div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-caption text-cp-text-secondary">Decision</span>
                <span className={cn(
                  'text-body-sm font-medium',
                  finalDecision === 'allow' && 'text-cp-allow',
                  finalDecision === 'modify' && 'text-cp-modify',
                  finalDecision === 'block' && 'text-cp-block',
                  finalDecision === 'escalate' && 'text-cp-escalate',
                  finalDecision === 'verify' && 'text-cp-verify'
                )}>
                  {decisionLabel(finalDecision)}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-caption text-cp-text-secondary">Policy</span>
                <span className="text-body-sm font-mono text-cp-text">
                  {detail.policy_id || 'Unknown'}
                </span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-caption text-cp-text-secondary">Findings</span>
                <span className="text-body-sm text-cp-text">{findings.length}</span>
              </div>
              {intervention && (
                <div className="flex items-center justify-between">
                  <span className="text-caption text-cp-text-secondary">Intervention</span>
                  <span className="text-body-sm text-cp-modify">{intervention.action}</span>
                </div>
              )}
            </div>
          </div>

          {/* Reason Codes */}
          {decision?.reason_codes && decision.reason_codes.length > 0 && (
            <div className="cp-panel">
              <div className="cp-section-title mb-3">REASON CODES</div>
              <div className="space-y-2">
                {decision.reason_codes.map((code, i) => (
                  <div key={i} className="text-body-sm text-cp-text-secondary">
                    {explainReason(code)}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Audit Timeline */}
          <AuditTimeline events={auditEvents} />
        </div>
      </div>
    </div>
  )
}
