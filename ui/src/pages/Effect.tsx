import { useState, useEffect } from 'react'
import { api } from '../api'
import type { DemoScenario, RunResult, PolicyComparisonResult } from '../types'
import { cn, decisionLabel, decisionText, getDimensionSummary } from '../lib/utils'
import PageHeader from '../components/PageHeader'
import EmptyState from '../components/EmptyState'
import ComparisonTable from '../components/ComparisonTable'

type Mode = 'without-vs-with' | 'policy-comparison'

export default function Effect() {
  const [mode, setMode] = useState<Mode>('without-vs-with')
  const [scenarios, setScenarios] = useState<DemoScenario[]>([])
  const [selectedScenario, setSelectedScenario] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const [singleResult, setSingleResult] = useState<RunResult | null>(null)
  const [compareResult, setCompareResult] = useState<PolicyComparisonResult | null>(null)

  useEffect(() => {
    api.listDemoScenarios()
      .then(setScenarios)
      .catch(() => {})
  }, [])

  const runWithoutVsWith = async (scenario: string) => {
    setLoading(true)
    setError(null)
    setSingleResult(null)
    setSelectedScenario(scenario)
    try {
      const result = await api.runDemo({ scenario })
      setSingleResult(result)
    } catch (err: any) {
      setError(err.message || 'Run failed')
    } finally {
      setLoading(false)
    }
  }

  const runPolicyComparison = async (scenario: string) => {
    setLoading(true)
    setError(null)
    setCompareResult(null)
    setSelectedScenario(scenario)
    try {
      const result = await api.comparePolicy({ scenario, policies: ['Balanced', 'Strict', 'Lenient'] })
      setCompareResult(result)
    } catch (err: any) {
      setError(err.message || 'Comparison failed')
    } finally {
      setLoading(false)
    }
  }

  const clearResults = () => {
    setSingleResult(null)
    setCompareResult(null)
    setError(null)
    setSelectedScenario(null)
  }

  return (
    <div className="p-6 lg:p-8 space-y-6 bg-cp-surface">
      {/* Header */}
      <PageHeader
        eyebrow="EFFECTS"
        title="What ControlPlane Changed"
        description="Demonstrate the impact of AI governance by comparing outcomes with and without ControlPlane"
        action={
          <div className="flex items-center gap-2">
            <button
              onClick={() => { setMode('without-vs-with'); clearResults() }}
              className={cn(
                'cp-btn-sm',
                mode === 'without-vs-with' ? 'cp-btn-primary' : 'cp-btn-ghost'
              )}
            >
              Without vs With
            </button>
            <button
              onClick={() => { setMode('policy-comparison'); clearResults() }}
              className={cn(
                'cp-btn-sm',
                mode === 'policy-comparison' ? 'cp-btn-primary' : 'cp-btn-ghost'
              )}
            >
              Policy Comparison
            </button>
          </div>
        }
      />

      {/* Mode Indicator */}
      <div className="cp-panel border-l-4 border-l-cp-accent">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-cp-accent" />
          <span className="text-body-sm font-medium text-cp-text">
            {mode === 'without-vs-with'
              ? 'Comparing raw model output vs. governed response'
              : 'Comparing the same output across Balanced, Strict, and Lenient policies'}
          </span>
        </div>
      </div>

      {/* Scenario Selector */}
      <div className="cp-panel">
        <div className="cp-section-title mb-3">
          {mode === 'without-vs-with' ? 'SELECT SCENARIO — WITHOUT VS WITH' : 'SELECT SCENARIO — POLICY COMPARISON'}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {scenarios.map(s => {
            const isSelected = selectedScenario === s.name;
            return (
              <button
                key={s.name}
                onClick={() => mode === 'without-vs-with' ? runWithoutVsWith(s.name) : runPolicyComparison(s.name)}
                disabled={loading}
                className={cn(
                  'text-left p-3 rounded-md border-2 transition-all duration-150 group',
                  'disabled:opacity-40 disabled:cursor-not-allowed',
                  isSelected
                    ? 'border-cp-accent bg-cp-accent text-white shadow-sm'
                    : 'border-cp-border bg-cp-surface hover:border-cp-accent hover:bg-cp-accent hover:text-white',
                )}
              >
                <div className="flex items-baseline gap-2 mb-0.5">
                  <span className={cn(
                    'text-caption font-mono font-semibold',
                    isSelected ? 'text-white/70' : 'text-cp-text-muted group-hover:text-white/70',
                  )}>{s.tag}</span>
                  <span className={cn(
                    'text-body-sm font-semibold',
                    isSelected ? 'text-white' : 'text-cp-text group-hover:text-white',
                  )}>{s.label}</span>
                </div>
                <p className={cn(
                  'text-caption',
                  isSelected ? 'text-white/80' : 'text-cp-text-muted group-hover:text-white/80',
                )}>{s.description}</p>
                {s.dimensions.length > 0 && s.dimensions[0] !== 'none' && (
                  <div className="flex gap-1 mt-1.5">
                    {s.dimensions.map(d => (
                      <span key={d} className={cn(
                        'text-caption px-1.5 py-0.5 rounded',
                        isSelected
                          ? 'bg-white/20 text-white'
                          : 'bg-cp-surface-2 text-cp-text-muted group-hover:bg-white/20 group-hover:text-white',
                      )}>{d}</span>
                    ))}
                  </div>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {/* Loading */}
      {loading && (
        <div className="cp-panel animate-fade-in">
          <div className="flex items-center gap-3 text-cp-text-muted">
            <div className="w-3 h-3 border-2 border-cp-brand/30 border-t-cp-brand rounded-full animate-spin" />
            <span className="text-body-sm font-mono">
              {mode === 'without-vs-with' ? 'Running through ControlPlane pipeline...' : 'Comparing policies...'}
            </span>
          </div>
        </div>
      )}

      {/* Error */}
      {error && (
        <div className="cp-panel border-cp-block/30 bg-cp-block-soft/30 animate-fade-in">
          <div className="cp-section-title text-cp-block mb-1">Error</div>
          <p className="text-body-sm text-cp-text">{error}</p>
        </div>
      )}

      {/* ─── WITHOUT VS WITH RESULT ─────────────────────────── */}
      {singleResult && mode === 'without-vs-with' && (
        <div className="space-y-6 animate-fade-in">
          <h2 className="text-heading-lg text-cp-text">Governance Impact</h2>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Without ControlPlane */}
            <div className="cp-panel border-2 border-cp-border">
              <div className="cp-section-title text-cp-text-muted mb-3">WITHOUT CONTROLPLANE</div>
              <p className="text-caption text-cp-text-muted mb-4">Raw model response — no governance applied</p>
              
              <div className="p-4 bg-cp-surface rounded-md">
                <p className="text-body-sm text-cp-text font-mono whitespace-pre-wrap">
                  {singleResult.response_text}
                </p>
              </div>
              
              <div className="mt-4 pt-4 cp-divider">
                <div className="flex items-center gap-2 text-caption text-cp-text-muted">
                  <span className="text-cp-block">✕</span>
                  <span>No policy evaluation</span>
                </div>
                <div className="flex items-center gap-2 text-caption text-cp-text-muted mt-1">
                  <span className="text-cp-block">✕</span>
                  <span>No findings detection</span>
                </div>
                <div className="flex items-center gap-2 text-caption text-cp-text-muted mt-1">
                  <span className="text-cp-block">✕</span>
                  <span>No intervention</span>
                </div>
              </div>
            </div>

            {/* With ControlPlane */}
            <div className={cn(
              'cp-panel border-2',
              singleResult.decision === 'block' && 'border-cp-block/30',
              singleResult.decision === 'modify' && 'border-cp-modify/30',
              singleResult.decision === 'escalate' && 'border-cp-escalate/30',
              singleResult.decision === 'allow' && 'border-cp-allow/30',
              singleResult.decision === 'verify' && 'border-cp-verify/30'
            )}>
              <div className="cp-section-title text-cp-brand mb-3">WITH CONTROLPLANE</div>
              <p className="text-caption text-cp-text-muted mb-4">Governed response — policy applied</p>
              
              <div className="p-4 bg-cp-brand-light/30 rounded-md">
                {singleResult.decision === 'block' ? (
                  <div className="text-center py-4">
                    <div className="text-body-lg font-semibold text-cp-block tracking-wide">RESPONSE BLOCKED</div>
                    <p className="text-caption text-cp-text-muted mt-1">Blocked by ControlPlane policy</p>
                  </div>
                ) : singleResult.decision === 'escalate' ? (
                  <div className="text-center py-4">
                    <div className="text-body-lg font-semibold text-cp-escalate tracking-wide">HELD FOR REVIEW</div>
                    <p className="text-caption text-cp-text-muted mt-1">Escalated for human review</p>
                  </div>
                ) : singleResult.decision === 'modify' ? (
                  <p className="text-body-sm text-cp-text font-mono whitespace-pre-wrap">
                    {singleResult.released_response}
                  </p>
                ) : (
                  <p className="text-body-sm text-cp-text font-mono whitespace-pre-wrap">
                    {singleResult.released_response || singleResult.response_text}
                  </p>
                )}
              </div>
              
              <div className="mt-4 pt-4 cp-divider space-y-2">
                <div className="flex items-center gap-2 text-caption">
                  <span className="text-cp-allow">✓</span>
                  <span className="text-cp-text-secondary">Policy evaluated: <span className="font-mono text-cp-text">{singleResult.applied_policy_name}</span></span>
                </div>
                <div className="flex items-center gap-2 text-caption">
                  <span className="text-cp-allow">✓</span>
                  <span className="text-cp-text-secondary">{singleResult.findings?.length ?? 0} finding{singleResult.findings?.length !== 1 ? 's' : ''} detected</span>
                </div>
                <div className="flex items-center gap-2 text-caption">
                  <span className="text-cp-allow">✓</span>
                  <span className="text-cp-text-secondary">Decision: <span className="font-medium text-cp-text">{decisionLabel(singleResult.decision)}</span></span>
                </div>
                {singleResult.intervention?.action && (
                  <div className="flex items-center gap-2 text-caption">
                    <span className="text-cp-allow">✓</span>
                    <span className="text-cp-text-secondary">Intervention: <span className="text-cp-modify">{singleResult.intervention.action}</span></span>
                  </div>
                )}
              </div>
            </div>
          </div>

          {/* Key Insight */}
          <div className="cp-panel border-l-4 border-l-cp-accent bg-cp-accent-light/30">
            <p className="text-body-sm text-cp-text">
              <span className="font-semibold text-cp-accent">Key Insight:</span>{' '}
              ControlPlane intercepted the model response, evaluated it against policy, and determined the appropriate governance action. Without ControlPlane, the raw response would reach the user unchanged.
            </p>
          </div>

          <button onClick={clearResults} className="cp-btn-ghost">
            CLEAR
          </button>
        </div>
      )}

      {/* ─── POLICY COMPARISON RESULT ───────────────────── */}
      {compareResult && mode === 'policy-comparison' && (
        <div className="space-y-6 animate-fade-in">
          <h2 className="text-heading-lg text-cp-text">Same Model. Same Finding. Different Policy. Different Outcome.</h2>
          
          {/* Model Output (shown once - identical across all) */}
          <div className="cp-panel">
            <div className="cp-section-title mb-2">MODEL OUTPUT</div>
            <p className="text-caption text-cp-text-muted mb-3">Identical across all policies</p>
            <div className="p-4 bg-cp-surface rounded-md">
              <p className="text-body-sm text-cp-text font-mono whitespace-pre-wrap">
                {compareResult.model_output.response_text}
              </p>
            </div>
            <div className="mt-3 pt-3 cp-divider flex items-center gap-4">
              <span className="text-caption font-mono text-cp-text-muted">
                Model: <span className="text-cp-text">{compareResult.model_output.model}</span>
              </span>
              <span className="text-caption text-cp-text-muted">·</span>
              <span className="text-caption text-cp-text-muted">
                Provider: <span className="text-cp-text">{compareResult.model_output.provider}</span>
              </span>
            </div>
          </div>

          {/* Comparison Table */}
          <ComparisonTable
            title="POLICY COMPARISON"
            rows={[
              {
                label: 'FINDING',
                balanced: compareResult.comparisons[0]?.findings.length ? `⚠ ${compareResult.comparisons[0].findings.length} detected` : '✓ Clear',
                strict: compareResult.comparisons[1]?.findings.length ? `⚠ ${compareResult.comparisons[1].findings.length} detected` : '✓ Clear',
                type: 'finding',
              },
              {
                label: 'POLICY',
                balanced: compareResult.comparisons[0]?.policy_name || 'Balanced',
                strict: compareResult.comparisons[1]?.policy_name || 'Strict',
                type: 'policy',
              },
              {
                label: 'DECISION',
                balanced: decisionLabel(compareResult.comparisons[0]?.decision || 'allow'),
                strict: decisionLabel(compareResult.comparisons[1]?.decision || 'allow'),
                type: 'policy',
              },
              {
                label: 'ACTION',
                balanced: compareResult.comparisons[0]?.intervention?.action || 'None',
                strict: compareResult.comparisons[1]?.intervention?.action || 'None',
                type: 'action',
              },
              {
                label: 'RELEASE',
                balanced: compareResult.comparisons[0]?.decision === 'block' ? '✕' : '✓',
                strict: compareResult.comparisons[1]?.decision === 'block' ? '✕' : '✓',
                type: 'release',
              },
            ]}
          />

          {/* Authority Proof Summary */}
          <div className="cp-panel">
            <div className="cp-section-title mb-4">AUTHORITY PROOF</div>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="p-3 bg-cp-allow-soft/50 rounded-md">
                <div className="text-caption font-medium text-cp-allow mb-1">MODEL OUTPUT</div>
                <p className="text-caption text-cp-text-secondary">UNCHANGED across all policies</p>
              </div>
              <div className="p-3 bg-cp-allow-soft/50 rounded-md">
                <div className="text-caption font-medium text-cp-allow mb-1">FINDING</div>
                <p className="text-caption text-cp-text-secondary">UNCHANGED — detection is policy-independent</p>
              </div>
              <div className="p-3 bg-cp-block-soft/50 rounded-md">
                <div className="text-caption font-medium text-cp-block mb-1">POLICY</div>
                <p className="text-caption text-cp-text-secondary">CHANGED — different policy snapshots applied</p>
              </div>
              <div className="p-3 bg-cp-block-soft/50 rounded-md">
                <div className="text-caption font-medium text-cp-block mb-1">OUTCOME</div>
                <p className="text-caption text-cp-text-secondary">CHANGED — policy determines the action</p>
              </div>
            </div>
          </div>

          {/* Key Insight */}
          <div className="cp-panel border-l-4 border-l-cp-accent bg-cp-accent-light/30">
            <p className="text-body-sm text-cp-text">
              <span className="font-semibold text-cp-accent">Key Insight:</span>{' '}
              The same model output produces different outcomes under different policies. Detection is constant. Authority is the policy. ControlPlane is the gap between them.
            </p>
          </div>

          <button onClick={clearResults} className="cp-btn-ghost">
            CLEAR
          </button>
        </div>
      )}

      {/* Empty State */}
      {!singleResult && !compareResult && !loading && !error && (
        <EmptyState
          icon="◈"
          title={mode === 'without-vs-with' ? 'Compare Without vs With ControlPlane' : 'Compare Across Policies'}
          description={mode === 'without-vs-with'
            ? 'Select a scenario above to see the raw model response alongside the governed response with policy evaluation, findings, and intervention.'
            : 'Select a scenario above to see how the same model output produces different outcomes under Balanced, Strict, and Lenient policies.'}
        />
      )}
    </div>
  )
}
