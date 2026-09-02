import { cn, decisionLabel } from '../lib/utils';

interface DecisionBannerProps {
  decision: string;
  policy?: string;
  reason?: string;
  action?: string;
  className?: string;
}

export default function DecisionBanner({ decision, policy, reason, action, className }: DecisionBannerProps) {
  const label = decisionLabel(decision);
  
  const decisionConfig: Record<string, { bg: string; border: string; text: string; accent: string; glow: string }> = {
    allow: { bg: 'bg-cp-allow-soft/30', border: 'border-cp-allow/30', text: 'text-cp-allow', accent: 'bg-cp-allow', glow: 'shadow-[0_0_0_3px_rgba(46,125,87,0.1)]' },
    modify: { bg: 'bg-cp-modify-soft/30', border: 'border-cp-modify/30', text: 'text-cp-modify', accent: 'bg-cp-modify', glow: 'shadow-[0_0_0_3px_rgba(184,92,56,0.1)]' },
    block: { bg: 'bg-cp-block-soft/30', border: 'border-cp-block/30', text: 'text-cp-block', accent: 'bg-cp-block', glow: 'shadow-[0_0_0_3px_rgba(143,48,56,0.1)]' },
    escalate: { bg: 'bg-cp-escalate-soft/30', border: 'border-cp-escalate/30', text: 'text-cp-escalate', accent: 'bg-cp-escalate', glow: 'shadow-[0_0_0_3px_rgba(197,107,62,0.1)]' },
    verify: { bg: 'bg-cp-verify-soft/30', border: 'border-cp-verify/30', text: 'text-cp-verify', accent: 'bg-cp-verify', glow: 'shadow-[0_0_0_3px_rgba(104,70,109,0.1)]' },
  };

  const config = decisionConfig[decision] || { bg: 'bg-cp-unknown-soft/30', border: 'border-cp-unknown/30', text: 'text-cp-unknown', accent: 'bg-cp-unknown', glow: '' };

  return (
    <div className={cn(
      'cp-decision-display border-2',
      config.border,
      config.bg,
      config.glow,
      className
    )}>
      {/* Decision Label */}
      <div className="cp-section-title mb-4 tracking-wider">GOVERNANCE DECISION</div>
      
      {/* Decision Word */}
      <div className={cn(
        'text-decision font-bold tracking-tight mb-4',
        config.text
      )}>
        {label}
      </div>
      
      {/* Decision Details */}
      <div className="space-y-2 text-left max-w-md mx-auto">
        {policy && (
          <div className="flex items-baseline gap-3">
            <span className="cp-label w-16">Policy</span>
            <span className="text-body-sm font-mono text-cp-text">{policy}</span>
          </div>
        )}
        {reason && (
          <div className="flex items-baseline gap-3">
            <span className="cp-label w-16">Reason</span>
            <span className="text-body-sm text-cp-text">{reason}</span>
          </div>
        )}
        {action && (
          <div className="flex items-baseline gap-3">
            <span className="cp-label w-16">Action</span>
            <span className="text-body-sm font-medium text-cp-modify">{action}</span>
          </div>
        )}
      </div>
    </div>
  );
}
