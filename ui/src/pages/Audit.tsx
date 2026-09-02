import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { AuditRecord } from '../types'
import {
  cn, decisionLabel, decisionBadgeClass, formatTimestampFull,
  explainReason,
} from '../lib/utils'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'

export default function Audit() {
  const navigate = useNavigate()
  const [records, setRecords] = useState<AuditRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(0)
  const [filter, setFilter] = useState<'all' | 'denied' | 'modified' | 'passed' | 'escalated'>('all')
  const pageSize = 50

  useEffect(() => {
    setLoading(true)
    api.listAudit({ limit: pageSize, offset: page * pageSize })
      .then(setRecords)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [page])

  const filtered = records.filter(r => {
    if (filter === 'all') return true
    const d = r.decisions?.[r.decisions.length - 1]?.decision
    if (filter === 'denied') return d === 'block'
    if (filter === 'modified') return d === 'modify'
    if (filter === 'passed') return d === 'allow'
    if (filter === 'escalated') return d === 'escalate'
    return true
  })

  const counts = { total: records.length, allow: 0, modify: 0, block: 0, escalate: 0 }
  records.forEach(r => {
    const d = r.decisions?.[r.decisions.length - 1]?.decision
    if (d === 'allow') counts.allow++
    else if (d === 'modify') counts.modify++
    else if (d === 'block') counts.block++
    else if (d === 'escalate') counts.escalate++
  })

  if (loading) {
    return (
      <div className="p-6 lg:p-8">
        <div className="flex items-center gap-3 text-cp-text-muted py-12">
          <div className="w-3 h-3 border-2 border-cp-brand/30 border-t-cp-brand rounded-full animate-spin" />
          <span className="text-body-sm font-mono">Loading audit trail...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 lg:p-8">
        <div className="cp-panel border-cp-block/30 bg-cp-block-soft/30">
          <p className="text-body-sm text-cp-text">Failed to load audit trail: {error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 lg:p-8 space-y-6 bg-cp-surface">
      {/* Header */}
      <PageHeader
        eyebrow="AUDIT"
        title="Decision Evidence"
        description="Immutable execution history — why ControlPlane made each decision"
      />

      {/* Summary */}
      {filtered.length > 0 && (
        <div className="grid grid-cols-5 gap-3">
          {[
            { label: 'Total', value: counts.total, className: 'text-cp-text' },
            { label: 'Allow', value: counts.allow, className: 'text-cp-allow' },
            { label: 'Modify', value: counts.modify, className: 'text-cp-modify' },
            { label: 'Block', value: counts.block, className: 'text-cp-block' },
            { label: 'Escalate', value: counts.escalate, className: 'text-cp-escalate' },
          ].map(m => (
            <div key={m.label} className="cp-panel">
              <div className="cp-section-title">{m.label}</div>
              <div className={cn('text-heading-lg font-semibold mt-1', m.className)}>
                {m.value}
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Filters and Pagination */}
      <div className="flex items-center justify-between gap-4">
        <div className="flex items-center gap-2">
          {(['all', 'passed', 'modified', 'denied', 'escalated'] as const).map(f => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                'cp-btn-sm',
                filter === f ? 'cp-btn-primary' : 'cp-btn-ghost'
              )}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
        
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPage(Math.max(0, page - 1))}
            disabled={page === 0}
            className="cp-btn-ghost cp-btn-sm disabled:opacity-40"
          >
            ← Prev
          </button>
          <span className="text-caption text-cp-text-muted font-mono min-w-[50px] text-center">
            Page {page + 1}
          </span>
          <button
            onClick={() => setPage(page + 1)}
            disabled={records.length < pageSize}
            className="cp-btn-ghost cp-btn-sm disabled:opacity-40"
          >
            Next →
          </button>
        </div>
        
        <span className="text-caption text-cp-text-muted">
          {filtered.length} record{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Audit Records */}
      {filtered.length === 0 ? (
        <EmptyState
          icon="▣"
          title="No Audit Records Yet"
          description="Run an execution from the Control Room to begin building an audit trail."
          action={{
            label: 'Open Control Room',
            onClick: () => navigate('/run'),
          }}
        />
      ) : (
        <div className="space-y-2">
          {filtered.map(record => {
            const d = record.decisions?.[record.decisions.length - 1]
            const primaryReason = d?.reason_codes?.[0]
            
            return (
              <div
                key={record.audit_id}
                onClick={() => navigate(`/interactions/${record.interaction_id}`)}
                className="cp-panel cp-card-hover"
              >
                <div className="flex items-center gap-4">
                  {/* Time */}
                  <div className="text-caption font-mono text-cp-text-muted w-32 flex-shrink-0">
                    {formatTimestampFull(record.created_at)}
                  </div>

                  {/* Interaction ID */}
                  <div className="text-caption font-mono text-cp-brand w-24 flex-shrink-0">
                    #{record.interaction_id.slice(0, 8)}
                  </div>

                  {/* Decision Badge */}
                  {d && (
                    <div className={cn('cp-badge font-mono', decisionBadgeClass(d.decision))}>
                      {decisionLabel(d.decision)}
                    </div>
                  )}

                  {/* Reason */}
                  <div className="flex-1 min-w-0">
                    <p className="text-body-sm text-cp-text truncate">
                      {primaryReason ? explainReason(primaryReason) : 'No reason recorded'}
                    </p>
                  </div>

                  {/* Findings */}
                  <div className="text-caption text-cp-text-muted flex-shrink-0">
                    {record.findings_count} finding{record.findings_count !== 1 ? 's' : ''}
                  </div>

                  {/* Intervention */}
                  <div className="text-caption text-cp-modify flex-shrink-0 w-20">
                    {record.intervention_action || '—'}
                  </div>

                  {/* Policy */}
                  <div className="text-caption font-mono text-cp-text-muted flex-shrink-0 w-16">
                    {record.policy_version || 'v1'}
                  </div>

                  {/* Arrow */}
                  <div className="text-cp-text-muted group-hover:text-cp-brand transition-colors flex-shrink-0">
                    →
                  </div>
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
