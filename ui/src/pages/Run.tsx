import { useState, useCallback, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import type { DemoScenario, PolicyInfo } from '../types'
import { cn, getDimensionSummary, explainReason, decisionLabel, decisionText } from '../lib/utils'
import PageHeader from '../components/PageHeader'
import PromptComposer from '../components/PromptComposer'
import ModelOutput from '../components/ModelOutput'
import ControlPlaneIntercept from '../components/ControlPlaneIntercept'
import DecisionBanner from '../components/DecisionBanner'
import ReleasedResponse from '../components/ReleasedResponse'
import EmptyState from '../components/EmptyState'
import DemoBadge from '../components/DemoBadge'

export default function Run() {
  const navigate = useNavigate()

  const [scenarios, setScenarios] = useState<DemoScenario[]>([])
  const [policies, setPolicies] = useState<PolicyInfo[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [result, setResult] = useState<any>(null)
  const [analysisPhase, setAnalysisPhase] = useState<'idle' | 'model' | 'intercept' | 'decision' | 'complete'>('idle')

  useEffect(() => {
    Promise.all([api.listDemoScenarios(), api.listPolicies()])
      .then(([s, p]) => { setScenarios(s); setPolicies(p) })
      .catch(() => {})
  }, [])

  const runPrompt = useCallback(async (prompt: string, options: { policy: string; consequence: string; scenario: string }) => {
    setLoading(true)
    setResult(null)
    setError(null)
    setAnalysisPhase('model')

    try {
      const scenario = options.scenario || scenarios[0]?.name || 'clean'

      await new Promise(r => setTimeout(r, 400))
      setAnalysisPhase('intercept')
      
      const data = await api.runDemo({
        scenario,
        policy: options.policy,
        consequence: options.consequence,
      })
      
      await new Promise(r => setTimeout(r, 300))
      setAnalysisPhase('decision')
      
      await new Promise(r => setTimeout(r, 200))
      setResult(data)
      setAnalysisPhase('complete')
    } catch (err: any) {
      setError(err.message || 'Demo run failed')
      setAnalysisPhase('idle')
    } finally {
      setLoading(false)
    }
  }, [scenarios])

  const terminalDecision = result?.decision ?? null
  const findings = result?.findings ?? []
  const dimensionSummary = getDimensionSummary(findings)
  const finalDecision = result?.decision_history?.[result.decision_history.length - 1]

  return (
    <div className="flex flex-col h-full bg-cp-surface">
      {/* Header */}
      <div className="px-6 py-4 border-b border-cp-border bg-cp-surface">
        <div className="flex items-center justify-between">
          <PageHeader
            eyebrow="CONTROL ROOM"
            title="AI Execution Workspace"
            description="Send a prompt through ControlPlane and observe the governance lifecycle"
            className="mb-0"
          />
          <DemoBadge />
        </div>
      </div>

      {/* Main Content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Center - Execution Workspace */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Workspace Area */}
          <div className="flex-1 overflow-y-auto p-6">
            {!result && !loading && (
              <EmptyState
                icon="✦"
                title="Ready for Execution"
                description="Enter a prompt below to send it through the ControlPlane governance pipeline. Watch as the response is intercepted, analyzed, and governed in real-time."
              />
            )}

            {/* Loading State */}
            {loading && (
              <div className="space-y-4 animate-fade-in">
                <div className="cp-intercept-gate border-2 border-cp-brand/30">
                  <div className="cp-intercept-bar">
                    <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    <span className="text-body-sm font-medium">
                      {analysisPhase === 'model' && 'Requesting model response...'}
                      {analysisPhase === 'intercept' && 'ControlPlane intercepting response...'}
                      {analysisPhase === 'decision' && 'Evaluating policy and making decision...'}
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Execution Pipeline */}
            {result && terminalDecision && (
              <div className="space-y-0 animate-fade-in">
                {/* Pipeline Rail Container */}
                <div className="cp-pipeline-rail cp-pipeline-rail-active">
                  
                  {/* Stage 01: User Prompt */}
                  <div className="cp-stage animate-stage-reveal" style={{ animationDelay: '0ms' }}>
                    <div className="cp-stage-marker cp-stage-marker-complete">✓</div>
                    <div className="cp-panel mb-4">
                      <div className="cp-section-title mb-2">USER PROMPT</div>
                      <p className="text-body text-cp-text">{result.request_text}</p>
                    </div>
                  </div>

                  {/* Flow Arrow */}
                  <div className="cp-flow-arrow cp-flow-arrow-green" />

                  {/* Stage 02: Model Output */}
                  <div className="cp-stage animate-stage-reveal" style={{ animationDelay: '100ms' }}>
                    <div className="cp-stage-marker cp-stage-marker-complete">✓</div>
                    <ModelOutput
                      response={result.response_text}
                      model={result.model}
                      provider={result.provider}
                    />
                  </div>

                  {/* Flow Arrow */}
                  <div className="cp-flow-arrow cp-flow-arrow-green" />

                  {/* Stage 03: ControlPlane Intercept */}
                  <div className="cp-stage animate-stage-reveal" style={{ animationDelay: '200ms' }}>
                    <div className={cn(
                      'cp-stage-marker',
                      analysisPhase !== 'complete' ? 'cp-stage-marker-active' : 'cp-stage-marker-complete'
                    )}>
                      {analysisPhase !== 'complete' ? (
                        <div className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      ) : (
                        '✓'
                      )}
                    </div>
                    <ControlPlaneIntercept
                      findings={dimensionSummary}
                      isAnalyzing={analysisPhase !== 'complete'}
                    />
                  </div>

                  {/* Flow Arrow */}
                  <div className="cp-flow-arrow cp-flow-arrow-green" />

                  {/* Stage 04: Evaluation */}
                  <div className="cp-stage animate-stage-reveal" style={{ animationDelay: '300ms' }}>
                    <div className="cp-stage-marker cp-stage-marker-complete">✓</div>
                    <div className="cp-panel mb-4">
                      <div className="cp-section-title mb-3">EVALUATION</div>
                      <div className="grid grid-cols-3 gap-3">
                        <div className="p-3 bg-cp-surface rounded-md border border-cp-border/50">
                          <div className="cp-section-title mb-1">PERFORMANCE</div>
                          <div className={cn(
                            'text-body-sm font-semibold',
                            dimensionSummary.performance.severity === 'critical' && 'text-cp-block',
                            dimensionSummary.performance.severity === 'warning' && 'text-cp-escalate',
                            dimensionSummary.performance.severity === 'info' && 'text-cp-allow'
                          )}>
                            {dimensionSummary.performance.severity === 'info' ? '✓ CLEAR' : '! FINDING'}
                          </div>
                          <p className="text-caption text-cp-text-muted mt-1">{dimensionSummary.performance.status}</p>
                        </div>
                        <div className="p-3 bg-cp-surface rounded-md border border-cp-border/50">
                          <div className="cp-section-title mb-1">COST</div>
                          <div className={cn(
                            'text-body-sm font-semibold',
                            dimensionSummary.cost.severity === 'critical' && 'text-cp-block',
                            dimensionSummary.cost.severity === 'warning' && 'text-cp-escalate',
                            dimensionSummary.cost.severity === 'info' && 'text-cp-allow'
                          )}>
                            {dimensionSummary.cost.severity === 'info' ? '✓ CLEAR' : '! FINDING'}
                          </div>
                          <p className="text-caption text-cp-text-muted mt-1">{dimensionSummary.cost.status}</p>
                        </div>
                        <div className="p-3 bg-cp-surface rounded-md border border-cp-border/50">
                          <div className="cp-section-title mb-1">RESPONSIBILITY</div>
                          <div className={cn(
                            'text-body-sm font-semibold',
                            dimensionSummary.responsibility.severity === 'critical' && 'text-cp-block',
                            dimensionSummary.responsibility.severity === 'warning' && 'text-cp-escalate',
                            dimensionSummary.responsibility.severity === 'info' && 'text-cp-allow'
                          )}>
                            {dimensionSummary.responsibility.severity === 'info' ? '✓ CLEAR' : '! FINDING'}
                          </div>
                          <p className="text-caption text-cp-text-muted mt-1">{dimensionSummary.responsibility.status}</p>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Flow Arrow */}
                  <div className="cp-flow-arrow cp-flow-arrow-green" />

                  {/* Stage 05: Decision */}
                  <div className="cp-stage animate-stage-reveal" style={{ animationDelay: '400ms' }}>
                    <div className="cp-stage-marker cp-stage-marker-complete">✓</div>
                    <DecisionBanner
                      decision={terminalDecision}
                      policy={result.applied_policy_name || result.policy_snapshot?.name}
                      reason={finalDecision?.reason_codes?.[0] ? explainReason(finalDecision.reason_codes[0]) : undefined}
                    />
                  </div>

                  {/* Flow Arrow */}
                  <div className="cp-flow-arrow cp-flow-arrow-green" />

                  {/* Stage 06: Intervention */}
                  {result.intervention && (
                    <>
                      <div className="cp-stage animate-stage-reveal" style={{ animationDelay: '500ms' }}>
                        <div className="cp-stage-marker cp-stage-marker-complete">✓</div>
                        <div className="cp-panel mb-4 border-l-2 border-l-cp-modify">
                          <div className="cp-section-title mb-1">INTERVENTION</div>
                          <div className="text-body-sm font-medium text-cp-modify">{result.intervention.action}</div>
                        </div>
                      </div>
                      <div className="cp-flow-arrow cp-flow-arrow-green" />
                    </>
                  )}

                  {/* Stage 07: Released Response */}
                  <div className="cp-stage animate-stage-reveal" style={{ animationDelay: '600ms' }}>
                    <div className="cp-stage-marker cp-stage-marker-complete">✓</div>
                    <ReleasedResponse
                      response={result.released_response || result.response_text}
                      intervention={result.intervention?.action}
                      rawResponse={result.response_text}
                    />
                  </div>

                </div>

                {/* Actions */}
                <div className="flex items-center gap-4 pt-6 pl-12">
                  <button
                    onClick={() => navigate(`/run/${result.interaction_id}`)}
                    className="cp-btn-ghost-brand"
                  >
                    VIEW PIPELINE TRACE →
                  </button>
                  <button
                    onClick={() => { setResult(null); setAnalysisPhase('idle') }}
                    className="cp-btn-ghost"
                  >
                    NEW EXECUTION
                  </button>
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
          </div>

          {/* Bottom - Prompt Composer */}
          <PromptComposer
            onSubmit={runPrompt}
            scenarios={scenarios}
            loading={loading}
          />
        </div>

        {/* Right - Inspector Panel */}
        <div className="w-inspector border-l border-cp-border bg-cp-surface overflow-y-auto hidden lg:block">
          <div className="p-4">
            {/* Inspector Header */}
            <div className="flex items-center gap-2 mb-4 pb-3 border-b border-cp-border/50">
              <div className="w-2 h-2 rounded-full bg-cp-brand" />
              <span className="text-[11px] font-mono text-cp-text-secondary uppercase tracking-wider">ControlPlane Inspector</span>
            </div>
            
            {result && terminalDecision ? (
              <div className="space-y-0">
                {/* Status Section */}
                <div className="cp-inspector-section">
                  <div className="cp-inspector-label">STATUS</div>
                  <div className={cn(
                    'text-decision-sm font-bold',
                    decisionText(terminalDecision)
                  )}>
                    {decisionLabel(terminalDecision)}
                  </div>
                </div>

                {/* Dimensions Section */}
                <div className="cp-inspector-section">
                  <div className="cp-inspector-label">EVALUATION</div>
                  
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <span className="text-body-sm text-cp-text-secondary">Performance</span>
                      <span className={cn(
                        'text-body-sm font-medium',
                        dimensionSummary.performance.severity === 'warning' && 'text-cp-escalate',
                        dimensionSummary.performance.severity === 'critical' && 'text-cp-block',
                        dimensionSummary.performance.severity === 'info' && 'text-cp-allow'
                      )}>
                        {dimensionSummary.performance.severity === 'info' ? '✓ CLEAR' : '! FINDING'}
                      </span>
                    </div>
                    
                    <div className="flex items-center justify-between">
                      <span className="text-body-sm text-cp-text-secondary">Cost</span>
                      <span className={cn(
                        'text-body-sm font-medium',
                        dimensionSummary.cost.severity === 'warning' && 'text-cp-escalate',
                        dimensionSummary.cost.severity === 'critical' && 'text-cp-block',
                        dimensionSummary.cost.severity === 'info' && 'text-cp-allow'
                      )}>
                        {dimensionSummary.cost.severity === 'info' ? '✓ CLEAR' : '! FINDING'}
                      </span>
                    </div>
                    
                    <div className="flex items-center justify-between">
                      <span className="text-body-sm text-cp-text-secondary">Responsibility</span>
                      <span className={cn(
                        'text-body-sm font-medium',
                        dimensionSummary.responsibility.severity === 'warning' && 'text-cp-escalate',
                        dimensionSummary.responsibility.severity === 'critical' && 'text-cp-block',
                        dimensionSummary.responsibility.severity === 'info' && 'text-cp-allow'
                      )}>
                        {dimensionSummary.responsibility.severity === 'info' ? '✓ CLEAR' : '! FINDING'}
                      </span>
                    </div>
                  </div>
                </div>

                {/* Policy Section */}
                <div className="cp-inspector-section">
                  <div className="cp-inspector-label">POLICY</div>
                  <p className="text-body-sm font-mono text-cp-text">
                    {result.applied_policy_name || result.policy_snapshot?.name || 'Unknown'}
                  </p>
                </div>

                {/* Findings Section */}
                <div className="cp-inspector-section">
                  <div className="cp-inspector-label">FINDINGS</div>
                  <p className="text-body-sm text-cp-text">
                    {findings.length} finding{findings.length !== 1 ? 's' : ''} detected
                  </p>
                </div>

                {/* Decision Section */}
                <div className="cp-inspector-section">
                  <div className="cp-inspector-label">DECISION</div>
                  <p className="text-body-sm text-cp-text">
                    {decisionLabel(terminalDecision)}
                  </p>
                </div>

                {/* Intervention Section */}
                {result.intervention && (
                  <div className="cp-inspector-section">
                    <div className="cp-inspector-label">INTERVENTION</div>
                    <p className="text-body-sm font-medium text-cp-modify">
                      {result.intervention.action}
                    </p>
                  </div>
                )}
              </div>
            ) : (
              <div className="text-body-sm text-cp-text-muted text-center py-12">
                Run an execution to see live analysis
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
