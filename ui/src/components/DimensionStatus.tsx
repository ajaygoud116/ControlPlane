import { cn, stateLabel, stateSeverity, statusIndicatorClass } from '../lib/utils';

interface DimensionStatusProps {
  dimension: 'performance' | 'cost' | 'responsibility';
  status: string;
  detail?: string;
  className?: string;
}

const DIMENSION_CONFIG = {
  performance: {
    label: 'PERFORMANCE',
    description: 'Correctness, contradictions, evidence',
    icon: '01',
  },
  cost: {
    label: 'COST',
    description: 'Tokens, latency, budget',
    icon: '02',
  },
  responsibility: {
    label: 'RESPONSIBILITY',
    description: 'PII, secrets, unsafe content',
    icon: '03',
  },
};

export default function DimensionStatus({ dimension, status, detail, className }: DimensionStatusProps) {
  const config = DIMENSION_CONFIG[dimension];
  const severity = stateSeverity(status);
  const label = stateLabel(status);
  const indicatorClass = statusIndicatorClass(severity);
  
  const hasFinding = severity === 'critical' || severity === 'warning';
  const isClean = severity === 'info' && (status === 'no_pii_detected' || status === 'responsibility_clean' || status === 'cost_within_budget');
  
  return (
    <div className={cn(
      'p-3 rounded-md border transition-all',
      hasFinding && severity === 'critical' && 'border-cp-block/30 bg-cp-block-soft/20',
      hasFinding && severity === 'warning' && 'border-cp-escalate/30 bg-cp-escalate-soft/20',
      !hasFinding && 'border-cp-border/50 bg-cp-surface',
      className
    )}>
      {/* Dimension Header */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-mono text-cp-text-muted opacity-50">{config.icon}</span>
          <span className="cp-section-title">{config.label}</span>
        </div>
        <div className={cn('status-dot', indicatorClass)} />
      </div>
      
      {/* Status Line */}
      <div className="flex items-center gap-2 mb-1">
        <span className={cn(
          'text-body-sm font-semibold',
          hasFinding && severity === 'critical' && 'text-cp-block',
          hasFinding && severity === 'warning' && 'text-cp-escalate',
          isClean && 'text-cp-allow',
          !hasFinding && !isClean && 'text-cp-text'
        )}>
          {hasFinding ? (
            <span className="flex items-center gap-1.5">
              <span className="text-cp-block">!</span>
              FINDING
            </span>
          ) : isClean ? (
            <span className="flex items-center gap-1.5">
              <span className="text-cp-allow">✓</span>
              CLEAR
            </span>
          ) : (
            label
          )}
        </span>
      </div>
      
      {/* State Label */}
      <p className="text-caption text-cp-text-muted">{label}</p>
      
      {/* Detail */}
      {detail && (
        <p className="text-caption text-cp-text-secondary mt-1.5 line-clamp-2 leading-relaxed">{detail}</p>
      )}
    </div>
  );
}
