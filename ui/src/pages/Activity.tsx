import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { Interaction } from '../types'
import {
  cn, decisionLabel, decisionBadgeClass,
  formatTimestampFull, dimensionLabel,
} from '../lib/utils'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'

export default function Activity() {
  const navigate = useNavigate()
  const [interactions, setInteractions] = useState<Interaction[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')

  useEffect(() => {
    api.listInteractions({ limit: 200 })
      .then(data => setInteractions(data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const filtered = interactions
    .filter(i => {
      if (statusFilter === 'all') return true
      const d = i.decision
      if (statusFilter === 'blocked') return d === 'block'
      if (statusFilter === 'modified') return d === 'modify'
      if (statusFilter === 'passed') return d === 'allow'
      if (statusFilter === 'escalated') return d === 'escalate'
      return true
    })
    .filter(i => {
      if (!searchQuery) return true
      return i.request_text?.toLowerCase().includes(searchQuery.toLowerCase()) ||
             i.model?.toLowerCase().includes(searchQuery.toLowerCase())
    })
    .sort((a, b) => new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime())

  const counts = { total: interactions.length, allow: 0, modify: 0, block: 0, escalate: 0 }
  interactions.forEach(i => {
    const d = i.decision
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
          <span className="text-body-sm font-mono">Loading runs...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 lg:p-8">
        <div className="cp-panel border-cp-block/30 bg-cp-block-soft/30">
          <p className="text-body-sm text-cp-text">Failed to load runs: {error}</p>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 lg:p-8 space-y-6 bg-cp-surface">
      {/* Header */}
      <PageHeader
        eyebrow="RUNS"
        title="Execution History"
        description="All governed AI executions"
      />

      {/* Summary */}
      {interactions.length > 0 && (
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

      {/* Search and Filters */}
      <div className="flex items-center gap-4">
        <input
          type="text"
          id="search-runs"
          name="search"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search runs..."
          className="cp-input flex-1 max-w-md"
        />
        <div className="flex items-center gap-2">
          {(['all', 'passed', 'modified', 'blocked', 'escalated'] as const).map(f => (
            <button
              key={f}
              onClick={() => setStatusFilter(f)}
              className={cn(
                'cp-btn-sm',
                statusFilter === f ? 'cp-btn-primary' : 'cp-btn-ghost'
              )}
            >
              {f.charAt(0).toUpperCase() + f.slice(1)}
            </button>
          ))}
        </div>
        <span className="text-caption text-cp-text-muted">
          {filtered.length} run{filtered.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Runs List */}
      {filtered.length === 0 ? (
        <EmptyState
          icon="◷"
          title="No Governed Runs Yet"
          description="Run an execution from the Control Room to begin building an audit trail."
          action={{
            label: 'Open Control Room',
            onClick: () => navigate('/run'),
          }}
        />
      ) : (
        <div className="space-y-2">
          {filtered.map(item => (
            <div
              key={item.interaction_id}
              onClick={() => navigate(`/interactions/${item.interaction_id}`)}
              className="cp-panel cp-card-hover flex items-center gap-4"
            >
              {/* Time */}
              <div className="text-caption font-mono text-cp-text-muted w-24 flex-shrink-0">
                {formatTimestampFull(item.created_at)}
              </div>

              {/* Decision Badge */}
              <div className={cn('cp-badge font-mono', decisionBadgeClass(item.decision))}>
                {decisionLabel(item.decision)}
              </div>

              {/* Request Preview */}
              <div className="flex-1 min-w-0">
                <p className="text-body-sm text-cp-text truncate">
                  {item.request_text || 'No request text'}
                </p>
                <div className="flex items-center gap-2 mt-1">
                  <span className="text-caption font-mono text-cp-text-muted">
                    {item.model || 'unknown'}
                  </span>
                  {item.policy_id && (
                    <>
                      <span className="text-caption text-cp-text-muted">·</span>
                      <span className="text-caption text-cp-text-muted">
                        {item.policy_id}
                      </span>
                    </>
                  )}
                </div>
              </div>

              {/* Findings Count */}
              <div className="text-right flex-shrink-0">
                <div className="text-body-sm font-medium text-cp-text">
                  {item.findings_count ?? 0} finding{(item.findings_count ?? 0) !== 1 ? 's' : ''}
                </div>
                {item.intervention_action && (
                  <div className="text-caption text-cp-modify">
                    {item.intervention_action}
                  </div>
                )}
              </div>

              {/* Arrow */}
              <div className="text-cp-text-muted group-hover:text-cp-brand transition-colors">
                →
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
