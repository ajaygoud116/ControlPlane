import { useEffect, useState } from 'react'
import { api } from '../api'
import type { Metrics } from '../types'
import { cn, decisionLabel, decisionText, dimensionLabel, stateLabel, stateCategory } from '../lib/utils'

export default function Insights() {
  const [metrics, setMetrics] = useState<Metrics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    api.getMetrics()
      .then(setMetrics)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  if (loading) {
    return (
      <div className="p-6 lg:p-8">
        <div className="flex items-center gap-3 text-cp-text-muted py-12">
          <div className="w-3 h-3 border-[1.5px] border-cp-accent/30 border-t-cp-accent rounded-full animate-spin" />
          <span className="text-[12px] font-mono">Loading insights...</span>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="p-6 lg:p-8">
        <div className="cp-panel border-cp-block/30 bg-cp-block-soft/30">
          <div className="text-cp-block text-[13px]">Failed to load insights: {error}</div>
        </div>
      </div>
    )
  }

  const decisions = metrics?.decisions || {}
  const findingsByDim = metrics?.findings_by_dimension || {}

  const totalDecisions = Object.values(decisions).reduce((s, n) => s + n, 0)

  const decisionOrder = ['allow', 'modify', 'block', 'escalate'] as const
  const presentDecisions = decisionOrder.filter(d => (decisions[d] ?? 0) > 0)

  return (
    <div className="p-6 lg:p-8 space-y-7 bg-cp-surface">
      <div>
        <div className="cp-eyebrow mb-2">INSIGHTS</div>
        <h1 className="text-display-sm font-bold text-cp-text tracking-tight">System Insights</h1>
        <p className="text-[13px] text-cp-text-secondary mt-1">Aggregate system behavior</p>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="cp-panel">
          <div className="cp-section-title">Total Interactions</div>
          <div className="text-2xl font-bold font-mono text-cp-text mt-1">{metrics?.total_interactions ?? 0}</div>
        </div>
        {presentDecisions.map(d => (
          <div key={d} className="cp-panel">
            <div className="cp-section-title">{decisionLabel(d)}</div>
            <div className={cn('text-2xl font-bold font-mono mt-1', decisionText(d))}>{decisions[d]}</div>
          </div>
        ))}
      </div>

      {Object.keys(findingsByDim).length > 0 && (
        <div className="cp-panel overflow-hidden">
          <div className="pb-3 border-b border-cp-border mb-4">
            <div className="cp-section-title">Findings by Dimension</div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {Object.entries(findingsByDim).map(([dim, states]) => {
              const total = Object.values(states).reduce((s, n) => s + n, 0)
              return (
                <div key={dim} className="p-4 bg-cp-surface rounded-md border border-cp-border/50">
                  <div className="flex items-center justify-between mb-3">
                    <span className="cp-section-title">{dimensionLabel(dim)}</span>
                    <span className="text-[10px] font-mono text-cp-text-muted">{total}</span>
                  </div>
                  <div className="space-y-2">
                    {Object.entries(states).map(([state, count]) => {
                      const cat = stateCategory(state)
                      const pct = total > 0 ? (count / total) * 100 : 0
                      return (
                        <div key={state}>
                          <div className="flex items-center justify-between mb-1">
                            <span className="text-[11px] text-cp-text-secondary font-mono">{stateLabel(state)}</span>
                            <span className="text-[11px] font-mono font-bold text-cp-text">{count}</span>
                          </div>
                          <div className="h-1 bg-cp-surface rounded-full overflow-hidden">
                            <div
                              className={cn(
                                'h-full rounded-full',
                                cat === 'clean' && 'bg-cp-allow',
                                cat === 'evidence' && 'bg-cp-escalate',
                                cat === 'unavailable' && 'bg-cp-text-muted',
                                cat === 'unknown' && 'bg-cp-unknown',
                              )}
                              style={{ width: `${pct}%` }}
                            />
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {totalDecisions > 0 && (
        <div className="cp-panel overflow-hidden">
          <div className="pb-3 border-b border-cp-border mb-4">
            <div className="cp-section-title">Decision Distribution</div>
          </div>
          <div className="flex h-3 rounded-full overflow-hidden bg-cp-surface">
            {presentDecisions.map(d => {
              const pct = (decisions[d] / totalDecisions) * 100
              return (
                <div
                  key={d}
                  className={cn(
                    'h-full first:rounded-l-full last:rounded-r-full',
                    d === 'allow' && 'bg-cp-allow',
                    d === 'modify' && 'bg-cp-modify',
                    d === 'block' && 'bg-cp-block',
                    d === 'escalate' && 'bg-cp-escalate',
                  )}
                  style={{ width: `${pct}%` }}
                  title={`${decisionLabel(d)}: ${decisions[d]} (${pct.toFixed(0)}%)`}
                />
              )
            })}
          </div>
          <div className="flex flex-wrap gap-4 mt-3">
            {presentDecisions.map(d => (
              <div key={d} className="flex items-center gap-2">
                <div className={cn(
                  'w-2 h-2 rounded-full',
                  d === 'allow' && 'bg-cp-allow',
                  d === 'modify' && 'bg-cp-modify',
                  d === 'block' && 'bg-cp-block',
                  d === 'escalate' && 'bg-cp-escalate',
                )} />
                <span className="text-[11px] font-mono text-cp-text-secondary">
                  {decisionLabel(d)}: {decisions[d]}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {totalDecisions === 0 && (
        <div className="cp-panel p-10 text-center">
          <div className="text-[13px] text-cp-text-muted">No decision data yet. Run scenarios to generate insights.</div>
        </div>
      )}
    </div>
  )
}
