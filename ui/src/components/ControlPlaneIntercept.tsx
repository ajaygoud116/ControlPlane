import { cn } from '../lib/utils';
import DimensionStatus from './DimensionStatus';

interface ControlPlaneInterceptProps {
  findings: {
    performance: { status: string; severity: string; detail: string };
    cost: { status: string; severity: string; detail: string };
    responsibility: { status: string; severity: string; detail: string };
  };
  isAnalyzing?: boolean;
  className?: string;
}

export default function ControlPlaneIntercept({ findings, isAnalyzing, className }: ControlPlaneInterceptProps) {
  const hasFindings = 
    findings.performance.severity === 'critical' || findings.performance.severity === 'warning' ||
    findings.cost.severity === 'critical' || findings.cost.severity === 'warning' ||
    findings.responsibility.severity === 'critical' || findings.responsibility.severity === 'warning';

  return (
    <div className={cn('cp-intercept-gate', className)}>
      {/* Gate Header Bar */}
      <div className={cn(
        'cp-intercept-bar',
        isAnalyzing && 'bg-cp-brand',
        hasFindings && !isAnalyzing && 'bg-cp-accent-dim',
        !isAnalyzing && !hasFindings && 'bg-cp-brand',
      )}>
        <div className="flex items-center gap-2">
          <div className={cn(
            'w-2 h-2 rounded-full',
            isAnalyzing ? 'bg-cp-white animate-pulse-soft' : 'bg-cp-white'
          )} />
          <span className="text-body-sm font-semibold tracking-wide">
            {isAnalyzing ? 'INTERCEPTING' : 'CONTROLPLANE INTERCEPT'}
          </span>
        </div>
        {!isAnalyzing && (
          <span className="text-caption font-mono opacity-70">
            {hasFindings ? 'FINDINGS DETECTED' : 'CLEAR'}
          </span>
        )}
      </div>

      {/* Gate Content */}
      <div className="relative p-4">
        {isAnalyzing ? (
          <div className="flex items-center justify-center gap-3 py-6">
            <div className="w-3 h-3 border-2 border-cp-brand/30 border-t-cp-brand rounded-full animate-spin" />
            <span className="text-body-sm text-cp-text-secondary font-medium">
              Evaluating response against policy...
            </span>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-3">
            <DimensionStatus
              dimension="performance"
              status={findings.performance.status}
              detail={findings.performance.detail}
            />
            <DimensionStatus
              dimension="cost"
              status={findings.cost.status}
              detail={findings.cost.detail}
            />
            <DimensionStatus
              dimension="responsibility"
              status={findings.responsibility.status}
              detail={findings.responsibility.detail}
            />
          </div>
        )}
      </div>
    </div>
  );
}
