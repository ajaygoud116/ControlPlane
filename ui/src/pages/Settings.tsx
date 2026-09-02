import { useEffect, useState } from 'react'
import { api } from '../api'
import type { PolicyInfo, Detector, DemoScenario } from '../types'
import { cn } from '../lib/utils'
import PageHeader from '../components/PageHeader'
import DemoBadge from '../components/DemoBadge'

export default function Settings() {
  const [health, setHealth] = useState<{ status: string } | null>(null)
  const [detectors, setDetectors] = useState<Detector[]>([])
  const [policies, setPolicies] = useState<PolicyInfo[]>([])
  const [scenarios, setScenarios] = useState<DemoScenario[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    Promise.allSettled([
      api.health(),
      api.listDetectors(),
      api.listPolicies(),
      api.listDemoScenarios(),
    ])
      .then(results => {
        const [healthRes, detectorsRes, policiesRes, scenariosRes] = results
        if (healthRes.status === 'fulfilled') setHealth(healthRes.value)
        if (detectorsRes.status === 'fulfilled') setDetectors(detectorsRes.value)
        if (policiesRes.status === 'fulfilled') setPolicies(policiesRes.value)
        if (scenariosRes.status === 'fulfilled') setScenarios(scenariosRes.value)
        const failures = results.filter(r => r.status === 'rejected')
        if (failures.length > 0) {
          setError(failures.map(r => (r as PromiseRejectedResult).reason?.message || 'Unknown error').join('; '))
        }
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const totalVerifiers = policies.reduce((sum, p) => sum + p.allowed_verifiers.length, 0)

  const systemStatus = health?.status === 'ok'
    ? { label: 'Operational', className: 'text-cp-allow' }
    : error
      ? { label: 'Unavailable', className: 'text-cp-block' }
      : { label: 'UNKNOWN', className: 'text-cp-text-muted' }

  if (loading) {
    return (
      <div className="p-6 lg:p-8">
        <div className="flex items-center gap-3 text-cp-text-muted py-12">
          <div className="w-3 h-3 border-2 border-cp-brand/30 border-t-cp-brand rounded-full animate-spin" />
          <span className="text-body-sm font-mono">Loading settings...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="p-6 lg:p-8 space-y-6 bg-cp-surface">
      {/* Header */}
      <PageHeader
        eyebrow="SETTINGS"
        title="System Configuration"
        description="System status and operational information"
      />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* System Status */}
        <div className="cp-panel">
          <div className="cp-section-title mb-4">SYSTEM STATUS</div>
          <div className="space-y-3">
            <div className="flex items-center justify-between py-2 border-b border-cp-border/50">
              <span className="text-body-sm text-cp-text-secondary">Backend API</span>
              <span className={cn('text-body-sm font-medium', systemStatus.className)}>
                {systemStatus.label}
              </span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-cp-border/50">
              <span className="text-body-sm text-cp-text-secondary">Mode</span>
              <DemoBadge />
            </div>
            <div className="flex items-center justify-between py-2 border-b border-cp-border/50">
              <span className="text-body-sm text-cp-text-secondary">Model</span>
              <span className="text-body-sm font-mono text-cp-text">Simulated Model</span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-cp-border/50">
              <span className="text-body-sm text-cp-text-secondary">Corpus</span>
              <span className="text-body-sm font-mono text-cp-text">
                {scenarios.length} scenario{scenarios.length !== 1 ? 's' : ''}
              </span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-cp-border/50">
              <span className="text-body-sm text-cp-text-secondary">Detectors</span>
              <span className="text-body-sm font-mono text-cp-text">
                {detectors.length} active
              </span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-cp-border/50">
              <span className="text-body-sm text-cp-text-secondary">Verifiers</span>
              <span className="text-body-sm font-mono text-cp-text">
                {totalVerifiers} configured
              </span>
            </div>
            <div className="flex items-center justify-between py-2 border-b border-cp-border/50">
              <span className="text-body-sm text-cp-text-secondary">Persistence</span>
              <span className="text-body-sm font-mono text-cp-allow">JSON AuditStore</span>
            </div>
            <div className="flex items-center justify-between py-2">
              <span className="text-body-sm text-cp-text-secondary">External Model Provider</span>
              <span className="text-body-sm font-mono text-cp-text-muted">UNAVAILABLE</span>
            </div>
          </div>
        </div>

        {/* Architecture */}
        <div className="cp-panel">
          <div className="cp-section-title mb-4">ARCHITECTURE</div>
          <div className="space-y-4">
            <p className="text-body-sm text-cp-text-secondary leading-relaxed">
              ControlPlane evaluates every AI model response through a deterministic pipeline:
            </p>
            
            <div className="flex items-center gap-1.5 text-caption flex-wrap">
              {['Request', 'Model', 'Response', 'Detect', 'Decide', 'Intervene', 'Audit'].map((step, i) => (
                <span key={step} className="flex items-center gap-1.5">
                  <span className="px-2 py-1 bg-cp-surface-2 rounded text-cp-text-secondary font-mono">{step}</span>
                  {i < 6 && <span className="text-cp-text-muted">→</span>}
                </span>
              ))}
            </div>
            
            <p className="text-body-sm text-cp-text-secondary leading-relaxed">
              Every decision is logged to the audit store. Every finding traces to a specific detector.
              Every reason code maps to a specific policy rule or assurance check.
            </p>
          </div>
        </div>
      </div>

      {/* Demo Limitations */}
      <div className="cp-panel border-l-4 border-l-cp-escalate bg-cp-escalate-soft/30">
        <div className="cp-section-title text-cp-escalate mb-3">DEMO LIMITATIONS</div>
        <p className="text-body-sm text-cp-text-secondary mb-3">
          This is a demonstration environment. The following capabilities are simulated or not available:
        </p>
        <ul className="space-y-2">
          <li className="flex items-start gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-cp-escalate mt-1.5 shrink-0" />
            <span className="text-body-sm text-cp-text-secondary">
              <span className="font-medium text-cp-text">Simulated model responses</span> — No live LLM calls are made. All model outputs are pre-generated scenarios.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-cp-escalate mt-1.5 shrink-0" />
            <span className="text-body-sm text-cp-text-secondary">
              <span className="font-medium text-cp-text">No external model provider</span> — Connecting to a live model API requires configuration not present in this demo.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-cp-escalate mt-1.5 shrink-0" />
            <span className="text-body-sm text-cp-text-secondary">
              <span className="font-medium text-cp-text">JSON file persistence</span> — Audit records are stored locally in JSON files, not a production database.
            </span>
          </li>
          <li className="flex items-start gap-2">
            <span className="w-1.5 h-1.5 rounded-full bg-cp-escalate mt-1.5 shrink-0" />
            <span className="text-body-sm text-cp-text-secondary">
              <span className="font-medium text-cp-text">Fixed detector set</span> — Detectors are statically configured. Adding new detectors requires code changes.
            </span>
          </li>
        </ul>
      </div>
    </div>
  )
}
