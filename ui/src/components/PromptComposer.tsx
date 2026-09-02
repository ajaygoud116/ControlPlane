import { useState, useEffect } from 'react';
import { cn } from '../lib/utils';
import type { DemoScenario } from '../types';

interface PromptComposerProps {
  onSubmit: (prompt: string, options: { policy: string; consequence: string; scenario: string }) => void;
  scenarios: DemoScenario[];
  loading?: boolean;
  disabled?: boolean;
  className?: string;
}

const POLICIES = ['Balanced', 'Strict', 'Lenient'];
const CONSEQUENCES = ['low', 'medium', 'high'];

export default function PromptComposer({ onSubmit, scenarios, loading, disabled, className }: PromptComposerProps) {
  const [selectedScenario, setSelectedScenario] = useState<string>('');
  const [prompt, setPrompt] = useState('');
  const [policy, setPolicy] = useState('Balanced');
  const [consequence, setConsequence] = useState('Medium');

  const activeScenario = scenarios.find(s => s.name === selectedScenario);

  useEffect(() => {
    if (activeScenario) {
      setPrompt(activeScenario.description);
    }
  }, [activeScenario]);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selectedScenario && !loading && !disabled) {
      onSubmit(prompt || activeScenario?.description || '', { policy, consequence, scenario: selectedScenario });
      setPrompt('');
      setSelectedScenario('');
    }
  };

  return (
    <div className={cn('bg-cp-surface border-t border-cp-border', className)}>
      {/* Header Bar */}
      <div className="px-6 py-2 border-b border-cp-border/50 bg-cp-surface-2/30">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-cp-text-muted opacity-50">01</span>
          <span className="text-caption font-medium text-cp-text-secondary uppercase tracking-wider">Execution Request</span>
          <span className="text-caption text-cp-text-muted ml-2">· Deterministic prototype</span>
        </div>
      </div>
      
      {/* Form */}
      <form onSubmit={handleSubmit} className="p-6">
        {/* Scenario Selector */}
        <div className="mb-4">
          <label htmlFor="scenario" className="cp-label block mb-1.5">DEMO SCENARIO</label>
          <select
            id="scenario"
            name="scenario"
            value={selectedScenario}
            onChange={(e) => setSelectedScenario(e.target.value)}
            className="cp-input w-full"
            disabled={loading || disabled}
          >
            <option value="">Select a governed execution scenario...</option>
            {scenarios.map(s => (
              <option key={s.name} value={s.name}>
                {s.label} — {s.description.slice(0, 60)}{s.description.length > 60 ? '...' : ''}
              </option>
            ))}
          </select>
        </div>

        {/* Prompt (auto-populated from scenario) */}
        <div className="mb-4">
          <label htmlFor="prompt" className="cp-label block mb-1.5">PROMPT</label>
          <textarea
            id="prompt"
            name="prompt"
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            placeholder={selectedScenario ? 'Scenario prompt loaded...' : 'Select a scenario above to populate the prompt'}
            className="cp-textarea flex-1 min-h-[60px]"
            disabled={loading || disabled || !selectedScenario}
          />
          {selectedScenario && activeScenario && (
            <div className="flex items-center gap-2 mt-1.5">
              <span className="text-caption text-cp-text-muted">
                Expected decision: <span className="font-medium text-cp-text">{activeScenario.expected_decision}</span>
              </span>
              {activeScenario.dimensions.length > 0 && activeScenario.dimensions[0] !== 'none' && (
                <>
                  <span className="text-cp-text-muted">·</span>
                  <span className="text-caption text-cp-text-muted">
                    Dimensions: {activeScenario.dimensions.join(', ')}
                  </span>
                </>
              )}
            </div>
          )}
        </div>
        
        <div className="flex items-center justify-between gap-4">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <label htmlFor="model" className="cp-label">Model</label>
              <select
                id="model"
                name="model"
                value="demo"
                className="cp-input text-caption py-1 px-2 min-w-[100px]"
                disabled
              >
                <option value="demo">Demo Model</option>
              </select>
            </div>
            
            <div className="w-px h-4 bg-cp-border" />
            
            <div className="flex items-center gap-2">
              <label htmlFor="policy" className="cp-label">Policy</label>
              <select
                id="policy"
                name="policy"
                value={policy}
                onChange={(e) => setPolicy(e.target.value)}
                className="cp-input text-caption py-1 px-2 min-w-[100px]"
                disabled={loading}
              >
                {POLICIES.map(p => (
                  <option key={p} value={p}>{p}</option>
                ))}
              </select>
            </div>
            
            <div className="w-px h-4 bg-cp-border" />
            
            <div className="flex items-center gap-2">
              <label htmlFor="consequence" className="cp-label">Consequence</label>
              <select
                id="consequence"
                name="consequence"
                value={consequence}
                onChange={(e) => setConsequence(e.target.value)}
                className="cp-input text-caption py-1 px-2 min-w-[100px]"
                disabled={loading}
              >
                {CONSEQUENCES.map(c => (
                  <option key={c} value={c}>{c}</option>
                ))}
              </select>
            </div>
          </div>
          
          <button
            type="submit"
            disabled={!selectedScenario || loading || disabled}
            className={cn(
              'cp-btn-primary min-w-[140px]',
              (loading || !selectedScenario) && 'opacity-50 cursor-not-allowed'
            )}
          >
            {loading ? (
              <>
                <span className="w-3 h-3 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                Running...
              </>
            ) : (
              <>
                RUN EXECUTION
                <span className="text-white/60">→</span>
              </>
            )}
          </button>
        </div>
      </form>
    </div>
  );
}
